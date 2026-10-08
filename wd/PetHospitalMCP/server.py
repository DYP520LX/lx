# 宠物医院 MCP（MVP）：只提供 list_pets。Streamable HTTP，同时兼容旧版握手和 2026-07-28 无握手。
import json, time, uuid, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 8081
API = "http://127.0.0.1:8080/api/v1/pets"
NAME, NEW = "pet-hospital", "2026-07-28"
FIELDS = ["q", "name", "ownerName", "ownerPhone", "species", "doctor", "disease", "status", "min", "max", "sortBy", "order", "page", "pageSize"]
SESSIONS = set()
TOOL = {
    "name": "list_pets",
    "description": "查询宠物列表（过滤、排序、分页），对应 GET /api/v1/pets",
    "inputSchema": {
        "type": "object",
        "properties": {
            "q": {"type": "string", "description": "关键字"},
            "name": {"type": "string"},
            "ownerName": {"type": "string"},
            "ownerPhone": {"type": "string"},
            "species": {"type": "string", "description": "如 犬、猫"},
            "doctor": {"type": "string"},
            "disease": {"type": "string"},
            "status": {"type": "string"},
            "min": {"type": "number", "description": "费用下限"},
            "max": {"type": "number", "description": "费用上限"},
            "sortBy": {"type": "string", "description": "如 totalCost"},
            "order": {"type": "string", "description": "asc 或 desc"},
            "page": {"type": "integer"},
            "pageSize": {"type": "integer"},
        },
    },
}


def is_new(version):
    return bool(version) and version >= NEW


def list_pets(args):
    query = {k: args[k] for k in FIELDS if args.get(k) not in (None, "")}
    url = API + ("?" + urllib.parse.urlencode(query) if query else "")
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_tool(name, args):
    if name != "list_pets":
        raise ValueError("未知工具: " + name)
    return list_pets(args or {})


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        print("[%s] %s" % (NAME, fmt % args))

    def _origin_bad(self):
        origin = self.headers.get("Origin")
        if not origin:
            return False
        return urllib.parse.urlparse(origin).hostname not in ("127.0.0.1", "localhost")

    def _version(self, body):
        header = self.headers.get("MCP-Protocol-Version")
        if header:
            return header.strip()
        meta = ((body or {}).get("params") or {}).get("_meta") or {}
        return meta.get("io.modelcontextprotocol/protocolVersion") or ""

    def _send(self, code, payload=None, headers=None, sse=False):
        if payload is None:
            self.send_response(code)
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        if sse:
            data = b"event: message\ndata: " + raw + b"\n\n"
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _rpc(self, id_, result=None, error=None, code=200, headers=None, sse=False):
        body = {"jsonrpc": "2.0", "id": id_}
        body["error" if error else "result"] = error or result
        self._send(code, body, headers, sse)

    def _mismatch(self, id_, message):
        self._rpc(id_, error={"code": -32020, "message": message}, code=400)

    def do_GET(self):
        if urllib.parse.urlparse(self.path).path not in ("/mcp", "/"):
            self._send(404, {"error": "not found"})
            return
        if self._origin_bad():
            self._send(403, {"error": "origin"})
            return
        if is_new(self._version(None)):
            self._send(405, headers={"Allow": "POST"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            while True:
                self.wfile.write(b": ping\n\n")
                self.wfile.flush()
                time.sleep(15)
        except Exception:
            return

    def do_DELETE(self):
        if is_new(self._version(None)):
            self._send(405, headers={"Allow": "POST"})
            return
        SESSIONS.discard(self.headers.get("Mcp-Session-Id"))
        self._send(200)

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path not in ("/mcp", "/"):
            self._send(404, {"error": "not found"})
            return
        if self._origin_bad():
            self._send(403, {"error": "origin"})
            return
        accept = self.headers.get("Accept") or "application/json, text/event-stream"
        if "application/json" not in accept and "text/event-stream" not in accept:
            self._send(406, {"error": "accept"})
            return
        sse = "text/event-stream" in accept and "application/json" not in accept
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode("utf-8"))
        except Exception:
            self._rpc(None, error={"code": -32700, "message": "parse error"}, code=400)
            return
        method = body.get("method")
        rpc_id = body.get("id")
        params = body.get("params") or {}
        version = self._version(body)
        new = is_new(version)
        if new:
            header_method = self.headers.get("Mcp-Method")
            if header_method != method:
                self._mismatch(rpc_id, "Mcp-Method 与请求体不一致或缺失")
                return
            if method == "tools/call" and self.headers.get("Mcp-Name") != (params.get("name") or ""):
                self._mismatch(rpc_id, "Mcp-Name 与 params.name 不一致或缺失")
                return
        else:
            sid = self.headers.get("Mcp-Session-Id")
            if sid and sid not in SESSIONS:
                self._send(404, {"error": "unknown session"})
                return
        if method and method.startswith("notifications/"):
            self._send(202)
            return
        if method == "initialize":
            sid = str(uuid.uuid4())
            SESSIONS.add(sid)
            client_ver = params.get("protocolVersion") or "2025-03-26"
            self._rpc(rpc_id, {
                "protocolVersion": client_ver,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": NAME, "version": "0.1.0"},
            }, headers={"Mcp-Session-Id": sid}, sse=sse)
            return
        if method == "server/discover":
            self._rpc(rpc_id, {
                "protocolVersions": ["2025-03-26", "2025-11-25", "2026-07-28"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": NAME, "version": "0.1.0"},
                "tools": [TOOL],
            }, sse=sse)
            return
        if method == "ping":
            self._rpc(rpc_id, {}, sse=sse)
            return
        if method == "tools/list":
            self._rpc(rpc_id, {"tools": [TOOL]}, sse=sse)
            return
        if method == "tools/call":
            try:
                data = call_tool(params.get("name"), params.get("arguments") or {})
                self._rpc(rpc_id, {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}], "isError": False}, sse=sse)
            except Exception as exc:
                self._rpc(rpc_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True}, sse=sse)
            return
        self._rpc(rpc_id, error={"code": -32601, "message": "method not found"}, code=400 if new else 200)


if __name__ == "__main__":
    print("pet-hospital MCP http://%s:%s/mcp  ->  %s" % (HOST, PORT, API))
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
