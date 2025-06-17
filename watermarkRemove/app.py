from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
from typing import List
from watermark_remover import remove_watermark_single
import cv2
import numpy as np
import zipfile
import shutil
import tempfile

app = FastAPI()

# 允许跨域，方便本地前端调试
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务
app.mount("/static", StaticFiles(directory="static"), name="static")

MASKS_DIR = "masks"
os.makedirs(MASKS_DIR, exist_ok=True)

# 1. 获取5个预设蒙版（假数据）
@app.get("/masks")
def get_masks():
    # 假数据，实际应读取masks目录
    masks = [
        {"type": "vertical", "name": "纵向", "thumb": "/static/mask_vertical.png"},
        {"type": "horizontal", "name": "横向", "thumb": "/static/mask_horizontal.png"},
        {"type": "square", "name": "正方形", "thumb": "/static/mask_square.png"},
        {"type": "panorama_h", "name": "全景横向", "thumb": "/static/mask_panorama_h.png"},
        {"type": "panorama_v", "name": "全景纵向", "thumb": "/static/mask_panorama_v.png"},
        {"type": "custom1", "name": "自定义1", "thumb": "/static/mask_custom1.png"},
        {"type": "custom2", "name": "自定义2", "thumb": "/static/mask_custom2.png"},
        {"type": "custom3", "name": "自定义3", "thumb": "/static/mask_custom3.png"},
        {"type": "custom4", "name": "自定义4", "thumb": "/static/mask_custom4.png"},
        {"type": "custom5", "name": "自定义5", "thumb": "/static/mask_custom5.png"},
    ]
    return {"masks": masks}

# 2. 更新/自定义某个蒙版
@app.post("/update_mask")
def update_mask(mask_type: str = Form(...), file: UploadFile = File(...)):
    save_path = os.path.join(MASKS_DIR, f"mask_{mask_type}.png")
    with open(save_path, "wb") as f:
        f.write(file.file.read())
    return {"msg": "蒙版已更新", "path": save_path}

# 3. 单组图片处理（占位实现）
@app.post("/process_single")
def process_single(
    high: UploadFile = File(...),
    low: UploadFile = File(...),
    mask_type: str = Form(...)
):
    # 读取上传的图片为 numpy 数组
    high_bytes = high.file.read()
    low_bytes = low.file.read()
    high_arr = np.frombuffer(high_bytes, np.uint8)
    low_arr = np.frombuffer(low_bytes, np.uint8)
    high_img = cv2.imdecode(high_arr, cv2.IMREAD_COLOR)
    low_img = cv2.imdecode(low_arr, cv2.IMREAD_COLOR)

    if high_img is None or low_img is None:
        return JSONResponse({"error": "图片解码失败"}, status_code=400)

    # 读取对应的蒙版
    mask_path = os.path.join(MASKS_DIR, f"mask_{mask_type}.png")
    if not os.path.exists(mask_path):
        return JSONResponse({"error": f"未找到蒙版: {mask_path}"}, status_code=400)
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return JSONResponse({"error": f"无法读取蒙版: {mask_path}"}, status_code=400)

    # 显式适配尺寸
    if high_img.shape != low_img.shape:
        low_img = cv2.resize(low_img, (high_img.shape[1], high_img.shape[0]))
    if mask.shape[:2] != high_img.shape[:2]:
        mask = cv2.resize(mask, (high_img.shape[1], high_img.shape[0]))

    try:
        result = remove_watermark_single(high_img, low_img, mask)
    except Exception as e:
        return JSONResponse({"error": f"处理失败: {str(e)}"}, status_code=500)
    temp_path = "temp_result.jpg"
    cv2.imwrite(temp_path, result)
    # 使用原高质量图片的文件名
    original_filename = high.filename if high.filename else "result.jpg"
    return FileResponse(temp_path, media_type="image/jpeg", filename=original_filename)

# 4. 批量处理（占位实现）
@app.post("/process_batch")
def process_batch(
    high_zip: UploadFile = File(...),
    low_zip: UploadFile = File(...),
    mask_type: str = Form(...)
):
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    high_dir = os.path.join(temp_dir, "high")
    low_dir = os.path.join(temp_dir, "low")
    result_dir = os.path.join(temp_dir, "result")
    os.makedirs(high_dir, exist_ok=True)
    os.makedirs(low_dir, exist_ok=True)
    os.makedirs(result_dir, exist_ok=True)

    # 保存并解压zip
    high_zip_path = os.path.join(temp_dir, "high.zip")
    low_zip_path = os.path.join(temp_dir, "low.zip")
    with open(high_zip_path, "wb") as f:
        f.write(high_zip.file.read())
    with open(low_zip_path, "wb") as f:
        f.write(low_zip.file.read())
    with zipfile.ZipFile(high_zip_path, 'r') as zip_ref:
        zip_ref.extractall(high_dir)
    with zipfile.ZipFile(low_zip_path, 'r') as zip_ref:
        zip_ref.extractall(low_dir)

    # 读取 mask
    mask_path = os.path.join(MASKS_DIR, f"mask_{mask_type}.png")
    if not os.path.exists(mask_path):
        shutil.rmtree(temp_dir)
        return JSONResponse({"error": f"未找到蒙版: {mask_path}"}, status_code=400)
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        shutil.rmtree(temp_dir)
        return JSONResponse({"error": f"无法读取蒙版: {mask_path}"}, status_code=400)

    # 遍历高质量图片，按原文件名处理
    high_files = [f for f in os.listdir(high_dir) if os.path.isfile(os.path.join(high_dir, f))]
    for fname in high_files:
        high_path = os.path.join(high_dir, fname)
        low_path = os.path.join(low_dir, fname)
        if not os.path.exists(low_path):
            continue  # 跳过没有对应低质量图片的文件
        high_img = cv2.imread(high_path)
        low_img = cv2.imread(low_path)
        if high_img is None or low_img is None:
            continue
        # 尺寸适配
        if high_img.shape != low_img.shape:
            low_img = cv2.resize(low_img, (high_img.shape[1], high_img.shape[0]))
        if mask.shape[:2] != high_img.shape[:2]:
            mask_resized = cv2.resize(mask, (high_img.shape[1], high_img.shape[0]))
        else:
            mask_resized = mask
        try:
            result = remove_watermark_single(high_img, low_img, mask_resized)
            cv2.imwrite(os.path.join(result_dir, fname), result)
        except Exception as e:
            continue

    # 打包结果
    temp_zip = os.path.join(temp_dir, "temp_result.zip")
    with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for fname in os.listdir(result_dir):
            fpath = os.path.join(result_dir, fname)
            zipf.write(fpath, fname)

    # 返回并清理
    response = FileResponse(temp_zip, media_type="application/zip", filename="result.zip")
    # 用后台线程延迟删除临时目录
    import threading
    def cleanup():
        import time
        time.sleep(3)
        shutil.rmtree(temp_dir)
    threading.Thread(target=cleanup, daemon=True).start()
    return response 