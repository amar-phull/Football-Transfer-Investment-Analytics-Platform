"""Loopback-only preview using the same ranking service as FastAPI."""
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .engine import FEATURES, ROLES, rank, player_names


class Preview(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(Path(__file__).resolve().parents[1]/"frontend"/"dist"),**kwargs)

    def reply(self,data,status=200):
        body = json.dumps(data,allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path=="/api/v1/names":
            return self.reply(player_names())
        if self.path=="/api/v1/roles":
            return self.reply({"profiles":ROLES,"labels":{k:v[0] for k,v in FEATURES.items()}})
        super().do_GET()

    def do_POST(self):
        if self.path!="/api/v1/rankings":
            return self.send_error(404)
        try:
            size = int(self.headers.get("Content-Length","0"))
            if not 0<size<=16384:
                raise ValueError("Invalid body size")
            params = json.loads(self.rfile.read(size))
            if not isinstance(params,dict) or "url" in params:
                raise ValueError("Invalid query")
            result = rank(**params)
        except (ValueError,TypeError,AttributeError) as exc:
            return self.reply({"detail":str(exc)},422)
        self.reply(result)


if __name__=="__main__":
    print("Recruitment desk at http://127.0.0.1:8000",flush=True)
    ThreadingHTTPServer(("127.0.0.1",8000),Preview).serve_forever()
