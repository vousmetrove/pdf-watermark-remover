"""
PDF Watermark Remover — Standalone Web App
==========================================
Double-click to run. Uses Python's built-in http.server (no Flask needed).
"""
import os, sys, uuid, threading, webbrowser, html, json, shutil, tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

import fitz, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(HERE, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)
jobs = {}
PORT = 5000
MAX_MB = 200

HTML_PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PDF 去水印工具</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#1a1a2e;color:#eee;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#16213e;border-radius:16px;padding:40px;max-width:520px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,.4)}
h1{font-size:24px;margin-bottom:8px;color:#e94560}
.sub{font-size:13px;color:#889;margin-bottom:28px}
.zone{border:2px dashed #334;border-radius:12px;padding:40px 20px;text-align:center;cursor:pointer;transition:.2s;margin-bottom:20px}
.zone:hover,.zone.drag{border-color:#e94560;background:rgba(233,69,96,.05)}
.zone p{font-size:15px;color:#aab}
.zone .icon{font-size:40px;margin-bottom:10px}
input[type=file]{display:none}
.row{display:flex;gap:12px;margin-bottom:14px;flex-wrap:wrap}
.row label{flex:1;min-width:100px}
.row label span{display:block;font-size:12px;color:#889;margin-bottom:4px}
.row input{width:100%;padding:8px 10px;border:1px solid #334;border-radius:8px;background:#0f3460;color:#eee;font-size:14px}
.btn{display:block;width:100%;padding:12px;border:none;border-radius:10px;font-size:16px;font-weight:600;cursor:pointer;transition:.2s}
.btn-go{background:#e94560;color:#fff;margin-top:8px}
.btn-go:hover{background:#c73652}
.btn-go:disabled{opacity:.5;cursor:not-allowed}
.btn-dl{background:#0f3460;color:#e94560;text-decoration:none;text-align:center;margin-top:8px;display:none}
.status{margin-top:16px;padding:12px;border-radius:8px;font-size:13px;display:none}
.status.info{background:rgba(233,69,96,.1);color:#e94560;display:block}
.status.ok{background:rgba(0,200,100,.1);color:#0c8;display:block}
.status.err{background:rgba(255,100,100,.1);color:#f66;display:block}
.bar{height:4px;background:#334;border-radius:2px;margin-top:10px;overflow:hidden;display:none}
.bar div{height:100%;background:#e94560;width:0%;transition:width .3s}
.footer{margin-top:24px;font-size:11px;color:#556;text-align:center}
</style>
</head>
<body>
<div class="card">
<h1>PDF 去水印</h1>
<p class="sub">上传扫描版PDF，自动去除浅色水印并增强清晰度</p>

<div class="zone" id="dropZone" onclick="document.getElementById('fileInput').click()">
  <div class="icon"></div><p>点击选择PDF文件，或拖拽到此处</p>
</div>
<input type="file" id="fileInput" accept=".pdf">

<div class="row">
  <label><span>水印阈值 (180-250)</span><input type="number" id="threshold" value="230" min="180" max="250"></label>
  <label><span>输出DPI (150-400)</span><input type="number" id="dpi" value="250" min="150" max="400"></label>
  <label><span>增强系数 (1.0-1.3)</span><input type="number" id="boost" value="1.10" min="1.0" max="1.30" step="0.05"></label>
</div>

<button class="btn btn-go" id="btnGo" disabled onclick="process()">开始处理</button>
<a class="btn btn-dl" id="btnDl" href="#" download>下载无水印PDF</a>

<div class="bar" id="progressBar"><div id="progressFill"></div></div>
<div class="status" id="status"></div>
<p class="footer">纯本地处理，文件不会上传到任何服务器</p>
</div>
<script>
const zone=document.getElementById('dropZone'),fi=document.getElementById('fileInput'),
  btnGo=document.getElementById('btnGo'),btnDl=document.getElementById('btnDl'),
  status=document.getElementById('status'),bar=document.getElementById('progressBar'),
  fill=document.getElementById('progressFill');
let file=null;
fi.addEventListener('change',()=>{if(fi.files.length){file=fi.files[0];zone.querySelector('p').textContent=file.name;btnGo.disabled=false}});
zone.addEventListener('dragover',e=>{e.preventDefault();zone.classList.add('drag')});
zone.addEventListener('dragleave',()=>zone.classList.remove('drag'));
zone.addEventListener('drop',e=>{e.preventDefault();zone.classList.remove('drag');if(e.dataTransfer.files.length){file=e.dataTransfer.files[0];fi.files=e.dataTransfer.files;zone.querySelector('p').textContent=file.name;btnGo.disabled=false}});
function setStatus(c,m){status.className='status '+c;status.textContent=m}
async function process(){if(!file)return;btnGo.disabled=true;btnDl.style.display='none';bar.style.display='block';fill.style.width='0%';setStatus('info','上传中...');const fd=new FormData();fd.append('file',file);fd.append('threshold',document.getElementById('threshold').value);fd.append('dpi',document.getElementById('dpi').value);fd.append('boost',document.getElementById('boost').value);try{const r=await fetch('/upload',{method:'POST',body:fd});const d=await r.json();if(!r.ok)throw new Error(d.error);poll(d.job_id)}catch(e){setStatus('err','失败: '+e.message);btnGo.disabled=false}}
function poll(id){fetch('/status/'+id).then(r=>r.json()).then(d=>{if(d.status==='done'){fill.style.width='100%';setStatus('ok','完成!');bar.style.display='none';btnDl.href='/download/'+id;btnDl.style.display='block';btnGo.disabled=false}else if(d.status==='error'){setStatus('err',d.msg);bar.style.display='none';btnGo.disabled=false}else{fill.style.width=(d.progress||0)+'%';setStatus('info','处理中... '+d.current+'/'+d.total);setTimeout(()=>poll(id),800)}}).catch(e=>{setStatus('err','查询失败');btnGo.disabled=false})}
</script>
</body>
</html>"""


def remove_watermark(src, dst, threshold=230, dpi=250, boost=1.10, on_progress=None):
    doc = fitz.open(src)
    out = fitz.open()
    for i, page in enumerate(doc):
        if on_progress:
            on_progress(i + 1, len(doc))
        pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB)
        arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n).astype(np.float32)
        arr[arr.min(axis=2) > threshold] = [255, 255, 255]
        arr = np.clip(arr / threshold * 255 * boost, 0, 255).astype(np.uint8)
        new_pix = fitz.Pixmap(fitz.csRGB, pix.w, pix.h, arr.tobytes(), False)
        p = out.new_page(width=page.rect.width, height=page.rect.height)
        p.insert_image(p.rect, pixmap=new_pix)
    out.save(dst, garbage=4, deflate=True)
    doc.close(); out.close()
    return dst


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ct="text/html;charset=utf-8"):
        if isinstance(body, str): body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/":
            return self._send(200, HTML_PAGE)
        if p.startswith("/status/"):
            jid = p.split("/")[-1]
            j = jobs.get(jid, {"status": "error", "msg": "Not found"})
            return self._send(200, json.dumps(j), "application/json")
        if p.startswith("/download/"):
            jid = p.split("/")[-1]
            j = jobs.get(jid)
            if not j or j["status"] != "done":
                return self._send(404, "Not found")
            return self._send_file(j["file"], "clean.pdf")
        self._send(404, "Not found")

    def do_POST(self):
        if self.path != "/upload":
            return self._send(404, "Not found")
        ct = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_MB * 1024 * 1024:
            return self._send(413, json.dumps({"error": "File too large"}), "application/json")

        boundary = ct.split("boundary=")[1].encode() if "boundary=" in ct else b""
        body = self.rfile.read(length)
        parts = body.split(b"--" + boundary)
        file_data = None
        params = {}
        for part in parts:
            if b"filename=" in part:
                hdr, _, data = part.partition(b"\r\n\r\n")
                file_data = data.rsplit(b"\r\n", 1)[0]
            elif b"name=" in part:
                hdr, _, data = part.partition(b"\r\n\r\n")
                val = data.rsplit(b"\r\n", 1)[0].decode()
                if b'name="threshold"' in hdr: params["threshold"] = val
                if b'name="dpi"' in hdr: params["dpi"] = val
                if b'name="boost"' in hdr: params["boost"] = val

        if not file_data:
            return self._send(400, json.dumps({"error": "No file"}), "application/json")

        jid = uuid.uuid4().hex[:12]
        src = os.path.join(tempfile.gettempdir(), f"wm_{jid}.pdf")
        dst = os.path.join(OUTPUT_DIR, f"{jid}.pdf")
        with open(src, "wb") as f:
            f.write(file_data)

        thr = int(params.get("threshold", 230))
        dpi = int(params.get("dpi", 250))
        boost = float(params.get("boost", 1.10))
        jobs[jid] = {"status": "processing", "file": None, "msg": "", "progress": 0, "current": 0, "total": 0}

        def worker():
            try:
                def progress(cur, tot):
                    jobs[jid]["progress"] = int(cur / tot * 100)
                    jobs[jid]["current"] = cur
                    jobs[jid]["total"] = tot
                remove_watermark(src, dst, threshold=thr, dpi=dpi, boost=boost, on_progress=progress)
                jobs[jid]["status"] = "done"
                jobs[jid]["file"] = dst
                os.remove(src)
            except Exception as e:
                jobs[jid]["status"] = "error"
                jobs[jid]["msg"] = str(e)

        threading.Thread(target=worker, daemon=True).start()
        self._send(200, json.dumps({"job_id": jid}), "application/json")

    def _send_file(self, path, name):
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"PDF Watermark Remover — http://127.0.0.1:{PORT}")
    webbrowser.open(f"http://127.0.0.1:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
