#!/usr/bin/env python3

import http.server
import argparse
import subprocess
import os

DESCRIPTION = "Server for repos"
repos_root = os.path.normpath(f"{os.path.dirname(__file__)}/..")

content_types = {"css": "text/css", "html": "text/html", "json":
                 "application/json", "js": "text/javascript"}

def get_args():
    p = argparse.ArgumentParser(description=DESCRIPTION)
    p.add_argument("--port", "-p", type=int, help="Port to listen on", default=5447)
    p.add_argument("--host", help="Host to listen on", default="0.0.0.0")
    p.add_argument("--allowed-origins", help="Comma separated list of allowed origins")
    args = p.parse_args()
    if args.allowed_origins:
        args.allowed_origins = args.allowed_origins.split(",")
    else:
        args.allowed_origins = []
    return args

class MyServer(http.server.BaseHTTPRequestHandler):
    def allow_origin(self):
        if "*" in args.allowed_origins:
            return True
        if self.headers.get('Sec-Fetch-Site', "") == "same-origin":
            return True
        else:
            print(f"Header 'Sec-Fetch-Site' is not present or is not or does not have value 'same-origin'")
        if 'Origin' not in self.headers:
            print(f"Refusing because: Origin not in self.headers: \n\033[36m{str(self.headers).strip()}\033[0m")
            self.send_response(403)
            return False

        if self.headers['Origin'] not in args.allowed_origins:
            print(f"Refusing because origin: {self.headers['Origin']} not in allowed origins: {args.allowed_origins}")
            self.send_response(403)
            return False
        return True

    def serve_viewer(self):
        path=self.path.replace("..", "NOPE").replace("~", "Ah Ah Ah")
        path = path[len("/repos-server/"):]
        self.send_response(200)
        ext = path.rsplit('.', 1)[-1]
        self.send_header('Content-Type', content_types[ext])
        self.end_headers()
        fullpath = f"{repos_root}/share/repos/html/{path}"
        if os.path.isfile(fullpath):
            self.wfile.write(open(fullpath, 'rb').read())
        else:
            print(f"Requested file '{path}' not found")

    def do_OPTIONS(self):
        """Assume that requests with method GET are CORS preflight requests"""
        print(f"Got an OPTIONS request")
        if not self.allow_origin():
            return

        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'X-PINGOTHER, Content-Type')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def do_GET(self):
        if self.path in ["/repos-server", "/repos-server/", "/"]:
            self.send_response(301)
            self.send_header("Location", "/repos-server/viewer/repos.html")
            self.end_headers()
            return
        # print(f"path = {self.path}")
        if self.path.startswith("/repos-server/viewer"):
            self.serve_viewer()
            return

        if not self.allow_origin():
            return

        if self.path == "/repos-server/repos-data":
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            subprocess.run(
                ["repos", "-j", "20", "-output-format", "json", "-branch"],
                stdout=self.wfile
            )
            return

        self.send_response(500)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<H1>Unknown end point')


try:
    args = get_args()
    server = http.server.HTTPServer((args.host, args.port), MyServer)
    print(f"Server listening on address : \033[1;33m{args.host}\033[0m, port \033[1;34m{args.port}\033[0m")
    server.serve_forever()
except KeyboardInterrupt:
    quit(130)
