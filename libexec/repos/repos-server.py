#!/usr/bin/env python3

import http.server
import argparse
import subprocess

DESCRIPTION = "Server for repos"

def get_args():
    p = argparse.ArgumentParser(description=DESCRIPTION)
    p.add_argument("--port", "-p", type=int, help="Port to listen on", default=5447)
    p.add_argument("--host", help="Host to listen on", default="0.0.0.0")
    return p.parse_args()

class MyServer(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Assume that requests with method GET are CORS preflight requests"""
        if 'Origin' not in self.headers or self.headers['Origin'] != "https://philippe.carphin.ca":
            self.send_response(403)
            return

        response_headers['Access-Control-Allow-Origin'] = self.headers['Origin']
        response_headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
        response_headers['Access-Control-Allow-Headers'] = 'X-PINGOTHER, Content-Type'
        response_headers['Access-Control-Max-Age'] = '86400'

    def do_GET(self):
        if 'Origin' not in self.headers:
            self.send_response(403)
            return
        else:
            origin = self.headers['Origin']
            if self.headers['Origin'] != "https://philippe-carphin.ca":
                self.send_response(403)
                return

        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        j = subprocess.run(["./repos", "-j", "20", "-output-format", "json"], stdout=self.wfile)

args = get_args()

server = http.server.HTTPServer((args.host, args.port), MyServer)

print(f"Server listening on address : \033[1;33m{args.host}\033[0m, port \033[1;34m{args.port}\033[0m")

try:
    server.serve_forever()
except KeyboardInterrupt:
    quit(130)
