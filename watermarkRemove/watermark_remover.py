import cv2
import numpy as np
import argparse
import os
import glob
from tqdm import tqdm

def remove_watermark_single(high_quality_img, low_quality_img, mask, output_path=None):
    """
    处理单张图片的水印替换
    
    参数:
        high_quality_img: 高质量带水印图片
        low_quality_img: 低质量无水印图片
        mask: 水印蒙版
        output_path: 输出图片路径(可选)
    """
    # 确保两张图片尺寸相同
    if high_quality_img.shape != low_quality_img.shape:
        low_quality_img = cv2.resize(low_quality_img, (high_quality_img.shape[1], high_quality_img.shape[0]))
    
    # 应用蒙版进行图像融合
    # 将蒙版转换为3通道以便与图像进行操作
    mask_3channel = cv2.merge([mask, mask, mask])
    mask_3channel = mask_3channel / 255.0
    
    # 结合两张图片
    result = high_quality_img * (1 - mask_3channel) + low_quality_img * mask_3channel
    result = result.astype(np.uint8)
    
    # 保存结果
    if output_path:
        cv2.imwrite(output_path, result)
    
    return result

def create_mask_interactively(high_quality_img):
    """
    交互式创建水印蒙版，支持多区域选择
    """
    mask = np.zeros(high_quality_img.shape[:2], dtype=np.uint8)
    
    # 创建交互式窗口来手动选择水印区域
    window_name = "选择水印区域 (按'c'添加区域，'r'重置当前选择，'q'完成所有选择)"
    cv2.namedWindow(window_name)
    
    # 用于显示的图像副本
    display_img = high_quality_img.copy()
    
    drawing = False
    start_x, start_y = -1, -1  # 起始点
    end_x, end_y = -1, -1      # 结束点
    
    def draw_rectangle(event, x, y, flags, param):
        nonlocal start_x, start_y, end_x, end_y, drawing, display_img
        
        if event == cv2.EVENT_LBUTTONDOWN:
            drawing = True
            start_x, start_y = x, y
            end_x, end_y = x, y
            
        elif event == cv2.EVENT_MOUSEMOVE and drawing:
            end_x, end_y = x, y
            # 更新显示图像
            temp_img = high_quality_img.copy()
            # 显示已经选择的区域
            overlay = temp_img.copy()
            mask_indices = np.where(mask == 255)
            if len(mask_indices[0]) > 0:
                overlay[mask_indices] = (0, 255, 0)
            cv2.addWeighted(overlay, 0.3, temp_img, 0.7, 0, temp_img)
            # 绘制当前选择的矩形
            cv2.rectangle(temp_img, (start_x, start_y), (end_x, end_y), (0, 255, 0), 2)
            display_img = temp_img
            
        elif event == cv2.EVENT_LBUTTONUP:
            drawing = False
            end_x, end_y = x, y
            # 更新显示图像
            temp_img = high_quality_img.copy()
            overlay = temp_img.copy()
            mask_indices = np.where(mask == 255)
            if len(mask_indices[0]) > 0:
                overlay[mask_indices] = (0, 255, 0)
            cv2.addWeighted(overlay, 0.3, temp_img, 0.7, 0, temp_img)
            # 绘制当前选择的矩形
            cv2.rectangle(temp_img, (start_x, start_y), (end_x, end_y), (0, 255, 0), 2)
            display_img = temp_img
    
    cv2.setMouseCallback(window_name, draw_rectangle)
    
    while True:
        cv2.imshow(window_name, display_img)
        k = cv2.waitKey(1) & 0xFF
        
        if k == ord('c'):  # 确认添加当前区域
            if start_x != -1 and start_y != -1 and end_x != -1 and end_y != -1:
                # 计算矩形的左上角和右下角坐标
                x1, y1 = min(start_x, end_x), min(start_y, end_y)
                x2, y2 = max(start_x, end_x), max(start_y, end_y)
                
                # 确保有效区域
                if x1 != x2 and y1 != y2:
                    # 更新蒙版
                    mask[y1:y2, x1:x2] = 255
                    
                    print(f"已添加水印区域: ({x1}, {y1}) - ({x2}, {y2})")
                    
                    # 更新显示图像
                    temp_img = high_quality_img.copy()
                    overlay = temp_img.copy()
                    mask_indices = np.where(mask == 255)
                    if len(mask_indices[0]) > 0:
                        overlay[mask_indices] = (0, 255, 0)
                    cv2.addWeighted(overlay, 0.3, temp_img, 0.7, 0, temp_img)
                    display_img = temp_img
                    
                    # 重置选择坐标
                    start_x, start_y = -1, -1
                    end_x, end_y = -1, -1
                else:
                    print("警告：选择的区域太小，请重新选择")
            else:
                print("请先选择一个区域")
        
        elif k == ord('r'):  # 重置当前选择
            start_x, start_y = -1, -1
            end_x, end_y = -1, -1
            drawing = False
            # 恢复原始图像加已选区域
            temp_img = high_quality_img.copy()
            overlay = temp_img.copy()
            mask_indices = np.where(mask == 255)
            if len(mask_indices[0]) > 0:
                overlay[mask_indices] = (0, 255, 0)
            cv2.addWeighted(overlay, 0.3, temp_img, 0.7, 0, temp_img)
            display_img = temp_img
            
        elif k == ord('q'):  # 完成所有选择
            # 检查是否有选择的区域
            if np.any(mask):
                break
            else:
                print("请至少选择一个水印区域")
    
    cv2.destroyAllWindows()
    return mask

def remove_watermark(high_quality_path, low_quality_path, mask_path=None, output_path="result.jpg"):
    """
    将高质量带水印图片中的水印部分替换为低质量无水印图片的对应部分
    
    参数:
        high_quality_path: 高质量带水印图片路径
        low_quality_path: 低质量无水印图片路径
        mask_path: 水印蒙版图片路径(可选)，如果不提供需要手动创建
        output_path: 输出图片路径
    """
    # 读取图片
    high_quality_img = cv2.imread(high_quality_path)
    low_quality_img = cv2.imread(low_quality_path)
    
    if high_quality_img is None or low_quality_img is None:
        print(f"错误：无法读取图片 {high_quality_path} 或 {low_quality_path}")
        return None
    
    # 如果没有提供蒙版，则需要创建一个
    if mask_path is None:
        print("未提供水印蒙版，将创建交互式蒙版工具")
        mask = create_mask_interactively(high_quality_img)
    else:
        # 读取蒙版图片
        mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        if mask is None:
            print(f"错误：无法读取蒙版图片 {mask_path}")
            return None
        if mask.shape[:2] != high_quality_img.shape[:2]:
            mask = cv2.resize(mask, (high_quality_img.shape[1], high_quality_img.shape[0]))
    
    # 处理图片
    result = remove_watermark_single(high_quality_img, low_quality_img, mask, output_path)
    
    print(f"处理完成，结果已保存至 {output_path}")
    
    # 显示结果
    cv2.imshow("处理结果", result)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    return result, mask

def batch_process_images(high_quality_dir, low_quality_dir, output_dir, mask=None, mask_path=None, sample_image=None):
    """
    批量处理两个文件夹中的图片
    
    参数:
        high_quality_dir: 高质量带水印图片文件夹
        low_quality_dir: 低质量无水印图片文件夹
        output_dir: 输出文件夹
        mask: 水印蒙版(如果已经创建)
        mask_path: 水印蒙版图片路径(可选)
        sample_image: 用于创建蒙版的样例图片路径(可选)
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取高质量图片文件列表
    high_quality_files = sorted(glob.glob(os.path.join(high_quality_dir, "*.*")))
    low_quality_files = sorted(glob.glob(os.path.join(low_quality_dir, "*.*")))
    
    # 确保文件数量匹配
    if len(high_quality_files) != len(low_quality_files):
        print(f"警告：高质量图片({len(high_quality_files)}张)和低质量图片({len(low_quality_files)}张)数量不匹配")
        min_count = min(len(high_quality_files), len(low_quality_files))
        high_quality_files = high_quality_files[:min_count]
        low_quality_files = low_quality_files[:min_count]
    
    # 检查是否有图片可处理
    if not high_quality_files:
        print("错误：未找到图片文件")
        return
    
    # 如果没有提供蒙版，则需要创建一个
    if mask is None and mask_path is None:
        # 使用样例图片或第一张图片创建蒙版
        sample_path = sample_image if sample_image else high_quality_files[0]
        print(f"使用样例图片 {sample_path} 创建蒙版")
        sample_img = cv2.imread(sample_path)
        
        if sample_img is None:
            print(f"错误：无法读取样例图片 {sample_path}")
            return
        
        print("请在样例图片上选择水印区域...")
        mask = create_mask_interactively(sample_img)
        
        # 保存蒙版以备将来使用
        mask_save_path = os.path.join(output_dir, "watermark_mask.png")
        cv2.imwrite(mask_save_path, mask)
        print(f"已保存水印蒙版至 {mask_save_path}")
    elif mask_path:
        # 读取蒙版图片
        mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        if mask is None:
            print(f"错误：无法读取蒙版图片 {mask_path}")
            return
    
    # 开始批量处理
    print(f"开始处理 {len(high_quality_files)} 组图片...")
    for i, (high_path, low_path) in enumerate(tqdm(zip(high_quality_files, low_quality_files), total=len(high_quality_files))):
        # 构建输出文件路径
        filename = os.path.basename(high_path)
        output_path = os.path.join(output_dir, filename)
        
        # 读取图片
        high_img = cv2.imread(high_path)
        low_img = cv2.imread(low_path)
        
        if high_img is None or low_img is None:
            print(f"跳过：无法读取图片 {high_path} 或 {low_path}")
            continue
        
        # 调整蒙版大小以匹配当前图片
        if mask.shape[:2] != high_img.shape[:2]:
            current_mask = cv2.resize(mask, (high_img.shape[1], high_img.shape[0]))
        else:
            current_mask = mask
        
        # 处理图片
        try:
            remove_watermark_single(high_img, low_img, current_mask, output_path)
        except Exception as e:
            print(f"处理图片 {high_path} 时出错: {str(e)}")
    
    print(f"批量处理完成！所有结果已保存至 {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="图片水印替换工具")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--single", action="store_true", help="处理单张图片")
    group.add_argument("--batch", action="store_true", help="批量处理文件夹中的图片")
    
    # 单张图片处理参数
    parser.add_argument("--high", help="高质量带水印图片路径")
    parser.add_argument("--low", help="低质量无水印图片路径")
    parser.add_argument("--output", default="result.jpg", help="输出图片路径")
    
    # 批量处理参数
    parser.add_argument("--high-dir", help="高质量带水印图片文件夹")
    parser.add_argument("--low-dir", help="低质量无水印图片文件夹")
    parser.add_argument("--output-dir", help="输出文件夹")
    parser.add_argument("--sample", help="用于创建蒙版的样例图片路径")
    
    # 通用参数
    parser.add_argument("--mask", help="水印蒙版图片路径(可选)")
    
    args = parser.parse_args()
    
    if args.single:
        if not args.high or not args.low:
            parser.error("单张处理模式需要 --high 和 --low 参数")
        
        # 处理单张图片
        result, mask = remove_watermark(args.high, args.low, args.mask, args.output)
        
    elif args.batch:
        if not args.high_dir or not args.low_dir or not args.output_dir:
            parser.error("批量处理模式需要 --high-dir, --low-dir 和 --output-dir 参数")
        
        # 批量处理图片
        batch_process_images(args.high_dir, args.low_dir, args.output_dir, 
                            mask_path=args.mask, sample_image=args.sample) 