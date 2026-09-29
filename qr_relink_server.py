#!/usr/bin/env python3
import base64, json, re, pathlib, http.server, urllib.request, urllib.error, threading, time

ENV = pathlib.Path('/root/evolution-whatsapp-agent/.env')
KEY = re.search(r'^AUTHENTICATION_API_KEY=(.*)$', ENV.read_text(), re.M).group(1).strip().strip('"\'')
BASE = 'http://127.0.0.1:8085'
INST = 'flavia-atendimento'
PORT = 8090

def req(method, path):
    r = urllib.request.Request(BASE + path, headers={'apikey': KEY}, method=method)
    with urllib.request.urlopen(r, timeout=20) as resp:
        return json.loads(resp.read().decode())

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith('/status'):
            try:
                st = req('GET', f'/instance/connectionState/{INST}')
                state = (st.get('instance') or {}).get('state', 'unknown')
            except Exception as e:
                state = f'erro:{e}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'state': state}).encode())
        elif self.path.startswith('/qr.png'):
            try:
                j = req('GET', f'/instance/connect/{INST}')
                b64 = j.get('base64') or ''
                png = base64.b64decode(b64.split(',')[-1]) if b64 else b''
            except Exception:
                png = b''
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(png)
        else:
            html = """<html><head><meta charset='utf-8'><title>Reconectar WhatsApp - flavia-atendimento</title></head>
<body style='font-family:sans-serif;text-align:center;padding:40px'>
<h2>Reconectar WhatsApp (Carlos)</h2>
<p>1. Abra o WhatsApp no celular do numero (21) 99401-0976<br>
2. Configuracoes -> Aparelhos conectados -> Conectar aparelho<br>
3. Aponte a camera para o QR abaixo</p>
<img id='qr' src='/qr.png?x=0' style='width:280px;height:280px;border:1px solid #ccc'>
<p id='status'>status: carregando...</p>
<script>
function refresh(){
  document.getElementById('qr').src='/qr.png?x='+Date.now();
  fetch('/status').then(r=>r.json()).then(j=>{
    document.getElementById('status').innerText='status: '+j.state+(j.state=='open'?' -- Conectado!':'');
  });
}
setInterval(refresh, 4000);
refresh();
</script>
</body></html>"""
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode())

if __name__ == '__main__':
    srv = http.server.HTTPServer(('127.0.0.1', PORT), Handler)
    print(f'serving on {PORT}')
    srv.serve_forever()
