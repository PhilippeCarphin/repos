#!/usr/bin/env python3

import http.server
import argparse
import subprocess

DESCRIPTION = "Server for repos"

def get_args():
    p = argparse.ArgumentParser(description=DESCRIPTION)
    p.add_argument("--port", "-p", type=int, help="Port to listen on", default=5447)
    p.add_argument("--host", help="Host to listen on", default="0.0.0.0")
    p.add_argument("--allowed-origins", help="Comma separated list of allowed origins")
    args = p.parse_args()
    if args.allowed_origins:
        args.allowed_origins = args.allowed_origins.split(",")
    return args

class MyServer(http.server.BaseHTTPRequestHandler):
    def allow_origin(self):
        if self.headers.get('Sec-Fetch-Site', "") == "same-origin":
            return True
        else:
            print(f"Header 'Sec-Fetch-Site' is not present or is not or does not have value 'same-origin'")
        if 'Origin' not in self.headers:
            print(f"Refusing because: Origin not in self.headers: \n\033[36m{str(self.headers).strip()}\033[0m")
            self.send_response(403)
            return False
        if args.allowed_origins and self.headers['Origin'] not in args.allowed_origins:
            print(f"Refusing because origin: {self.headers['Origin']} not in allowed origins: {args.allowed_origins}")
            self.send_response(403)
            return False
        return True

    def do_OPTIONS(self):
        """Assume that requests with method GET are CORS preflight requests"""
        if not self.allow_origin():
            return

        response_headers['Access-Control-Allow-Origin'] = self.headers['Origin']
        response_headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
        response_headers['Access-Control-Allow-Headers'] = 'X-PINGOTHER, Content-Type'
        response_headers['Access-Control-Max-Age'] = '86400'

    def do_GET(self):
        if not self.allow_origin():
            return
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        subprocess.run(["repos", "-j", "20", "-output-format", "json"], stdout=self.wfile)


try:
    args = get_args()
    server = http.server.HTTPServer((args.host, args.port), MyServer)
    print(f"Server listening on address : \033[1;33m{args.host}\033[0m, port \033[1;34m{args.port}\033[0m")
    server.serve_forever()
except KeyboardInterrupt:
    quit(130)
