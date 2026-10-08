# 给 AnythingLLM 第一个工作区上传文件并完成向量嵌入。打开 http://127.0.0.1:8083/
import json, re, uuid, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST, PORT = "127.0.0.1", 8083
CFG = Path(r"D:\学习\wd\Playground\anythingllm.json")
PAGE = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


def load_cfg():
    data = json.loads(CFG.read_text(encoding="utf-8"))
    return data.get("baseUrl", "http://127.0.0.1:3001").rstrip("/"), data.get("apiKey", "")


def api_json(url, key, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="GET" if payload is None else "POST")
    req.add_header("Authorization", "Bearer " + key)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def upload(base, key, filename, content, slug):
    boundary = "----wd" + uuid.uuid4().hex
    body = (
        ("--" + boundary + "\r\n").encode()
        + f'Content-Disposition: form-data; name="addToWorkspaces"\r\n\r\n{slug}\r\n'.encode()
        + ("--" + boundary + "\r\n").encode()
        + f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
        + b"Content-Type: application/octet-stream\r\n\r\n"
        + content
        + b"\r\n--"
        + boundary.encode()
        + b"--\r\n"
    )
    req = urllib.request.Request(base + "/api/v1/document/upload", data=body, method="POST")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_form(content_type, body):
    match = re.search(r'boundary=(?:"([^"]+)"|([^;]+))', content_type or "")
    if not match:
        raise ValueError("不是 multipart 表单")
    boundary = (match.group(1) or match.group(2)).encode()
    found = {}
    for chunk in body.split(b"--" + boundary):
        if b"Content-Disposition" not in chunk:
            continue
        head, _, data = chunk.partition(b"\r\n\r\n")
        data = data[:-2] if data.endswith(b"\r\n") else data
        text = head.decode("utf-8", "replace")
        name = re.search(r'name="([^"]+)"', text)
        filename = re.search(r'filename="([^"]*)"', text)
        if not name:
            continue
        found[name.group(1)] = {"filename": filename.group(1) if filename else "", "data": data}
    return found


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[webpage] " + (fmt % args))

    def _json(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if urllib.parse.urlparse(self.path).path != "/":
            self.send_error(404)
            return
        raw = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != "/upload":
            self.send_error(404)
            return
        try:
            form = parse_form(self.headers.get("Content-Type"), self.rfile.read(int(self.headers.get("Content-Length") or 0)))
            base, saved = load_cfg()
            key = ((form.get("apiKey") or {}).get("data") or b"").decode().strip() or saved
            item = form.get("file") or {}
            if not key:
                raise RuntimeError("请填写 API Key，或写入 Playground\\anythingllm.json")
            if not item.get("data"):
                raise RuntimeError("请选择文件")
            listed = api_json(base + "/api/v1/workspaces", key)
            workspaces = listed.get("workspaces") or []
            if not workspaces:
                raise RuntimeError("没有工作区")
            slug = workspaces[0].get("slug")
            uploaded = upload(base, key, item.get("filename") or "upload.txt", item["data"], slug)
            docs = uploaded.get("documents") or []
            location = (docs[0] or {}).get("location") if docs else ""
            embedded = None
            if location:
                embedded = api_json(base + "/api/v1/workspace/" + urllib.parse.quote(slug) + "/update-embeddings", key, {"adds": [location]})
            self._json(200, {"ok": True, "workspace": slug, "upload": uploaded, "embeddings": embedded})
        except Exception as exc:
            detail = exc.read().decode("utf-8", "replace") if hasattr(exc, "read") else str(exc)
            self._json(400, {"ok": False, "error": detail})


if __name__ == "__main__":
    print("upload page http://%s:%s/" % (HOST, PORT))
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
