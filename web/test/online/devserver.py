# Test server for the online games: serves the web folder and passes api.php requests to a PHP
# built-in server (which on its own stalls on browsers' kept-alive connections).
#   cd web && MONOPOLY_DATA=/tmp/mono php -S 127.0.0.1:8770 &  python3 test/online/devserver.py . 8771 http://127.0.0.1:8770
import sys, urllib.request, functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
ROOT, PORT, PHP = sys.argv[1], int(sys.argv[2]), sys.argv[3]
class H(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0)); body = self.rfile.read(n)
        req = urllib.request.Request(PHP + self.path, data=body, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req) as r: code, data = r.status, r.read()
        except urllib.error.HTTPError as e: code, data = e.code, e.read()
        self.send_response(code); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(H, directory=ROOT)).serve_forever()
