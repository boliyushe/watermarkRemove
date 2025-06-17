document.addEventListener('DOMContentLoaded', function() {
    // 1. 加载蒙版选项（下拉框+缩略图）
    let maskTypeToThumb = {};
    let maskTypeToName = {};
    fetch('/masks').then(r => r.json()).then(data => {
        const maskSelect = document.getElementById('mask-select-dropdown');
        const maskThumb = document.getElementById('mask-thumb-img');
        maskSelect.innerHTML = '';
        data.masks.forEach((mask, idx) => {
            const opt = document.createElement('option');
            opt.value = mask.type;
            opt.textContent = mask.name;
            maskSelect.appendChild(opt);
            maskTypeToThumb[mask.type] = mask.thumb;
            maskTypeToName[mask.type] = mask.name;
        });
        // 默认显示第一个缩略图
        maskThumb.src = data.masks[0].thumb;
    });
    document.getElementById('mask-select-dropdown').onchange = function() {
        const maskThumb = document.getElementById('mask-thumb-img');
        const type = this.value;
        if (maskTypeToThumb[type]) maskThumb.src = maskTypeToThumb[type];
    };

    // 2. 处理模式切换（下拉框）
    document.getElementById('mode-select').onchange = function() {
        if (this.value === 'single') {
            document.getElementById('single-upload').style.display = '';
            document.getElementById('batch-upload').style.display = 'none';
        } else {
            document.getElementById('single-upload').style.display = 'none';
            document.getElementById('batch-upload').style.display = '';
        }
    };

    // 3. 处理按钮
    document.getElementById('process-btn').onclick = async function() {
        const maskType = document.getElementById('mask-select-dropdown').value;
        const mode = document.getElementById('mode-select').value;
        const resultSection = document.getElementById('result-section');
        resultSection.innerHTML = '处理中...';

        if (mode === 'single') {
            const highFile = document.getElementById('high-img').files[0];
            const lowFile = document.getElementById('low-img').files[0];
            if (!highFile || !lowFile) { alert('请上传两张图片'); resultSection.innerHTML = ''; return; }
            const formData = new FormData();
            formData.append('high', highFile);
            formData.append('low', lowFile);
            formData.append('mask_type', maskType);

            fetch('/process_single', { method: 'POST', body: formData })
                .then(resp => {
                    if (!resp.ok) throw new Error('处理失败');
                    // 解析 Content-Disposition 获取文件名
                    const disposition = resp.headers.get('Content-Disposition');
                    let filename = 'result.jpg';
                    if (disposition) {
                        const match = disposition.match(/filename=\"?([^\";]+)\"?/i);
                        if (match && match[1]) {
                            filename = decodeURIComponent(match[1]);
                        }
                    }
                    return resp.blob().then(blob => ({ blob, filename }));
                })
                .then(({ blob, filename }) => {
                    const url = URL.createObjectURL(blob);
                    resultSection.innerHTML = `<img src="${url}" style="max-width:100%;border-radius:8px;">` +
                        `<a id="download-link" href="#" class="download-btn">下载图片</a>`;
                    document.getElementById('download-link').onclick = function(e) {
                        e.preventDefault();
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = filename;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        setTimeout(() => URL.revokeObjectURL(url), 2000);
                    };
                })
                .catch(err => {
                    resultSection.innerHTML = '处理失败';
                });
        } else {
            const highFiles = document.getElementById('high-folder').files;
            const lowFiles = document.getElementById('low-folder').files;
            if (!highFiles.length || !lowFiles.length) { alert('请上传两个文件夹'); resultSection.innerHTML = ''; return; }
            resultSection.innerHTML = '正在打包文件夹，请稍候...';

            // 打包高画质
            const highZip = new JSZip();
            for (let file of highFiles) {
                // 只保留文件名（不带文件夹结构）
                highZip.file(file.name, file);
            }
            // 打包低画质
            const lowZip = new JSZip();
            for (let file of lowFiles) {
                lowZip.file(file.name, file);
            }
            Promise.all([
                highZip.generateAsync({type: 'blob'}),
                lowZip.generateAsync({type: 'blob'})
            ]).then(([highZipBlob, lowZipBlob]) => {
                const formData = new FormData();
                formData.append('high_zip', highZipBlob, 'high.zip');
                formData.append('low_zip', lowZipBlob, 'low.zip');
                formData.append('mask_type', maskType);
                fetch('/process_batch', { method: 'POST', body: formData })
                    .then(resp => resp.blob())
                    .then(blob => {
                        const url = URL.createObjectURL(blob);
                        resultSection.innerHTML = `<a href="${url}" download="result.zip" class="download-btn">下载结果zip</a>`;
                    });
            });
        }
    };

    // 4. 添加或调整蒙版
    document.getElementById('edit-mask-btn').onclick = function() {
        // 动态获取所有蒙版类型
        fetch('/masks').then(r => r.json()).then(data => {
            const maskTypes = data.masks.map(m => ({type: m.type, name: m.name}));
            let html = '<div id="mask-upload-modal" style="position:fixed;left:0;top:0;width:100vw;height:100vh;background:rgba(0,0,0,0.3);z-index:999;display:flex;align-items:center;justify-content:center;">';
            html += '<div style="background:#fff;padding:24px 32px;border-radius:8px;min-width:340px;max-width:90vw;max-height:90vh;overflow-y:auto;">';
            html += '<h3>自定义蒙版</h3>';
            html += '<div style="display:flex;gap:12px;margin-bottom:16px;">';
            html += '<button id="tab-upload" class="tab-btn tab-active">上传蒙版</button>';
            html += '<button id="tab-create" class="tab-btn">制作蒙版</button>';
            html += '</div>';
            html += '<div id="tab-content-upload">';
            html += '<select id="mask-type-select">';
            maskTypes.forEach(m => html += `<option value="${m.type}">${m.name}</option>`);
            html += '</select><br><br>';
            html += '<input type="file" id="mask-file" accept="image/*"><br><br>';
            html += '<button id="mask-upload-btn">上传</button> <button id="mask-cancel-btn">取消</button>';
            html += '</div>';
            html += '<div id="tab-content-create" style="display:none;text-align:center;padding:24px 0;">';
            html += '<div class="mask-maker-section">';
            html += '<input type="file" id="mask-maker-img" accept="image/*"><br><br>';
            html += '<label>保存为蒙版类型：<select id="mask-maker-type">';
            maskTypes.forEach(m => html += `<option value="${m.type}">${m.name}</option>`);
            html += '</select></label><br>';
            html += '<canvas id="mask-maker-canvas" style="display:none;max-width:15vw;max-height:10vh;"></canvas>';
            html += '<div class="mask-maker-btns" style="display:none;">' +
                '<button id="mask-maker-undo">撤销</button>' +
                '<button id="mask-maker-reset">重置</button>' +
                '<button id="mask-maker-finish">完成并预览蒙版</button>' +
                '<button id="mask-maker-finish-download">完成并直接下载</button>' +
            '</div>';
            html += '<div id="mask-maker-upload" style="display:none;">' +
                '<img id="mask-preview" style="max-width:100%;"><br>' +
                '<button id="mask-maker-download-btn">下载蒙版</button> ' +
                '<button id="mask-maker-upload-btn">上传为蒙版</button>' +
            '</div>';
            html += '</div>';
            html += '<button id="mask-cancel-btn2">关闭</button>';
            html += '</div>';
            document.body.insertAdjacentHTML('beforeend', html);
            // 选项卡切换
            document.getElementById('tab-upload').onclick = function() {
                document.getElementById('tab-upload').classList.add('tab-active');
                document.getElementById('tab-create').classList.remove('tab-active');
                document.getElementById('tab-content-upload').style.display = '';
                document.getElementById('tab-content-create').style.display = 'none';
            };
            document.getElementById('tab-create').onclick = function() {
                document.getElementById('tab-upload').classList.remove('tab-active');
                document.getElementById('tab-create').classList.add('tab-active');
                document.getElementById('tab-content-upload').style.display = 'none';
                document.getElementById('tab-content-create').style.display = '';
            };
            // 关闭按钮
            document.getElementById('mask-cancel-btn').onclick = function() {
                document.getElementById('mask-upload-modal').remove();
            };
            document.getElementById('mask-cancel-btn2').onclick = function() {
                document.getElementById('mask-upload-modal').remove();
            };
            // 上传按钮
            document.getElementById('mask-upload-btn').onclick = async function() {
                const type = document.getElementById('mask-type-select').value;
                const file = document.getElementById('mask-file').files[0];
                if (!file) { alert('请选择图片'); return; }
                const formData = new FormData();
                formData.append('mask_type', type);
                formData.append('file', file);
                const resp = await fetch('/update_mask', { method: 'POST', body: formData });
                if (resp.ok) {
                    alert('蒙版上传成功！');
                    document.getElementById('mask-upload-modal').remove();
                    location.reload();
                } else {
                    alert('上传失败');
                }
            };
            // --- mask-maker 交互 ---
            let img = null;
            let rects = [];
            let drawing = false;
            let startX = 0, startY = 0, endX = 0, endY = 0;
            let maskDataUrl = null;
            const imgInput = document.getElementById('mask-maker-img');
            const canvas = document.getElementById('mask-maker-canvas');
            const btns = document.querySelector('.mask-maker-btns');
            const uploadDiv = document.getElementById('mask-maker-upload');
            const maskPreview = document.getElementById('mask-preview');
            let ctx = null;
            imgInput.onchange = function(e) {
                const file = e.target.files[0];
                if (!file) return;
                const reader = new FileReader();
                reader.onload = function(ev) {
                    img = new window.Image();
                    img.onload = function() {
                        canvas.width = img.width;
                        canvas.height = img.height;
                        // 显示自适应：最大宽90vw，高70vh，宽高auto，比例不变
                        canvas.style.maxWidth = '90vw';
                        canvas.style.maxHeight = '70vh';
                        canvas.style.width = 'auto';
                        canvas.style.height = 'auto';
                        canvas.style.display = '';
                        btns.style.display = 'flex';
                        uploadDiv.style.display = 'none';
                        maskPreview.src = '';
                        rects = [];
                        drawAll();
                    };
                    img.src = ev.target.result;
                };
                reader.readAsDataURL(file);
            };
            function drawAll() {
                ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                if (img) ctx.drawImage(img, 0, 0);
                // 已选区域高亮
                ctx.save();
                ctx.globalAlpha = 0.35;
                ctx.fillStyle = '#00ff00';
                rects.forEach(r => ctx.fillRect(r.x, r.y, r.w, r.h));
                ctx.restore();
                // 边框
                ctx.save();
                ctx.strokeStyle = '#00ff00';
                ctx.lineWidth = 2;
                rects.forEach(r => ctx.strokeRect(r.x, r.y, r.w, r.h));
                ctx.restore();
                // 当前绘制
                if (drawing) {
                    ctx.save();
                    ctx.strokeStyle = '#ff0';
                    ctx.lineWidth = 2;
                    ctx.strokeRect(startX, startY, endX - startX, endY - startY);
                    ctx.restore();
                }
            }
            // 鼠标事件坐标映射
            canvas.onmousedown = function(e) {
                if (!img) return;
                drawing = true;
                const rect = canvas.getBoundingClientRect();
                startX = Math.round((e.clientX - rect.left) * canvas.width / rect.width);
                startY = Math.round((e.clientY - rect.top) * canvas.height / rect.height);
                endX = startX;
                endY = startY;
            };
            canvas.onmousemove = function(e) {
                if (!drawing) return;
                const rect = canvas.getBoundingClientRect();
                endX = Math.round((e.clientX - rect.left) * canvas.width / rect.width);
                endY = Math.round((e.clientY - rect.top) * canvas.height / rect.height);
                drawAll();
            };
            canvas.onmouseup = function(e) {
                if (!drawing) return;
                drawing = false;
                const x1 = Math.max(0, Math.min(startX, endX));
                const y1 = Math.max(0, Math.min(startY, endY));
                const x2 = Math.min(canvas.width, Math.max(startX, endX));
                const y2 = Math.min(canvas.height, Math.max(startY, endY));
                if (Math.abs(x2 - x1) > 5 && Math.abs(y2 - y1) > 5) {
                    rects.push({x: x1, y: y1, w: x2 - x1, h: y2 - y1});
                }
                drawAll();
            };
            // 撤销
            document.getElementById('mask-maker-undo').onclick = function() {
                rects.pop();
                drawAll();
            };
            // 重置
            document.getElementById('mask-maker-reset').onclick = function() {
                rects = [];
                drawAll();
            };
            // 完成并预览
            document.getElementById('mask-maker-finish').onclick = function() {
                if (!img) return;
                // 生成黑白蒙版
                const maskCanvas = document.createElement('canvas');
                maskCanvas.width = canvas.width;
                maskCanvas.height = canvas.height;
                const mctx = maskCanvas.getContext('2d');
                mctx.fillStyle = '#000';
                mctx.fillRect(0, 0, maskCanvas.width, maskCanvas.height);
                mctx.fillStyle = '#fff';
                rects.forEach(r => mctx.fillRect(r.x, r.y, r.w, r.h));
                maskDataUrl = maskCanvas.toDataURL('image/png');
                maskPreview.src = maskDataUrl;
                maskPreview.style.maxWidth = '400px';
                maskPreview.style.maxHeight = '300px';
                uploadDiv.style.display = '';
            };
            // 完成并直接下载
            document.getElementById('mask-maker-finish-download').onclick = function() {
                if (!img) return;
                // 生成黑白蒙版
                const maskCanvas = document.createElement('canvas');
                maskCanvas.width = canvas.width;
                maskCanvas.height = canvas.height;
                const mctx = maskCanvas.getContext('2d');
                mctx.fillStyle = '#000';
                mctx.fillRect(0, 0, maskCanvas.width, maskCanvas.height);
                mctx.fillStyle = '#fff';
                rects.forEach(r => mctx.fillRect(r.x, r.y, r.w, r.h));
                const maskDataUrl = maskCanvas.toDataURL('image/png');
                let type = document.getElementById('mask-maker-type').value;
                let name = 'mask_' + type + '.png';
                const a = document.createElement('a');
                a.href = maskDataUrl;
                a.download = name;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            };
            // 下载蒙版
            document.getElementById('mask-maker-download-btn').onclick = function() {
                if (!maskDataUrl) { alert('请先完成并预览蒙版'); return; }
                let type = document.getElementById('mask-maker-type').value;
                let name = 'mask_' + type + '.png';
                const a = document.createElement('a');
                a.href = maskDataUrl;
                a.download = name;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            };
            // 上传为蒙版
            document.getElementById('mask-maker-upload-btn').onclick = async function() {
                if (!maskDataUrl) { alert('请先完成并预览蒙版'); return; }
                // 选择类型
                let type = document.getElementById('mask-maker-type').value;
                if (!type) return;
                const blob = dataURLtoBlob(maskDataUrl);
                const formData = new FormData();
                formData.append('mask_type', type);
                formData.append('file', blob, 'mask.png');
                const resp = await fetch('/update_mask', { method: 'POST', body: formData });
                if (resp.ok) {
                    alert('蒙版上传成功！');
                    document.getElementById('mask-upload-modal').remove();
                    location.reload();
                } else {
                    alert('上传失败');
                }
            };
            function dataURLtoBlob(dataurl) {
                var arr = dataurl.split(','), mime = arr[0].match(/:(.*?);/)[1],
                    bstr = atob(arr[1]), n = bstr.length, u8arr = new Uint8Array(n);
                while(n--){
                    u8arr[n] = bstr.charCodeAt(n);
                }
                return new Blob([u8arr], {type:mime});
            }
        });
    };
}); 