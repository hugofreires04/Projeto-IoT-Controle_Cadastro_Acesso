"""
Servidor de teste para a página de cadastro de funcionários.
Simula os endpoints do ESP32 sem precisar do hardware.

Uso:
    python test_server.py

Acesse http://localhost:8080/cadastro no browser.

Endpoints disponíveis:
  GET /cadastro              → abre a página de cadastro
  GET /uid                   → retorna o UID pendente (usado pela página via polling)
  GET /modo-admin            → ativa o modo administrador
  GET /simular?uid=4A+2B+3C  → injeta um UID (simula leitura do 2º cartão)
  POST /api/funcionarios     → recebe o cadastro e exibe no terminal
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

PORT = 8080
HTML_PATH = os.path.join(os.path.dirname(__file__), "data", "cadastro_funcionario.html")

pending_uid = ""
setup_mode = False
lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/cadastro":
            self._serve_html()
        elif path == "/uid":
            self._serve_uid()
        elif path == "/modo-admin":
            self._ativar_admin()
        elif path == "/simular":
            uid = params.get("uid", ["AA BB CC DD"])[0]
            self._simular_scan(uid)
        else:
            self._send_text(404, "Endpoint nao encontrado.")

    def do_POST(self):
        if self.path == "/api/funcionarios":
            self._receber_cadastro()
        else:
            self._send_text(404, "Endpoint nao encontrado.")

    # ------------------------------------------------------------------ #

    def _serve_html(self):
        try:
            with open(HTML_PATH, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self._send_text(404, f"Arquivo nao encontrado:\n{HTML_PATH}")

    def _serve_uid(self):
        global pending_uid
        with lock:
            uid = pending_uid
            if pending_uid:
                print(f"  [/uid] UID consumido: {pending_uid}")
                pending_uid = ""
        self._send_json({"uid": uid})

    def _ativar_admin(self):
        global setup_mode
        with lock:
            setup_mode = True
        msg = "setup_mode ativado.\nAgora chame /simular?uid=4A+2B+3C+1D"
        print(f"\n  [/modo-admin] {msg}")
        self._send_text(200, msg)

    def _simular_scan(self, uid):
        global pending_uid, setup_mode
        uid = uid.upper()
        with lock:
            if not setup_mode:
                setup_mode = True
                msg = f"1º cartão simulado ({uid}) → setup_mode ativado.\nAgora chame /simular?uid=XX novamente para o 2º cartão."
                print(f"\n  [/simular] {msg}")
            else:
                pending_uid = uid
                setup_mode = False
                msg = f"2º cartão simulado → pending_uid = {uid}\nAcesse /cadastro — o UID deve aparecer em até 2 segundos."
                print(f"\n  [/simular] {msg}")
        self._send_text(200, msg)

    def _receber_cadastro(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            print("\n" + "=" * 50)
            print("  NOVO CADASTRO RECEBIDO:")
            for k, v in body.items():
                print(f"    {k}: {v}")
            print("=" * 50)
            self._send_json({"ok": True, "mensagem": "Funcionário cadastrado com sucesso (simulação)."})
        except Exception as e:
            self._send_json({"ok": False, "mensagem": str(e)}, status=400)

    # ------------------------------------------------------------------ #

    def _send_text(self, status, text):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Suprime o log de acesso padrão para manter o terminal limpo
        pass


if __name__ == "__main__":
    print("=" * 50)
    print("  Servidor de teste — Cadastro de Funcionários")
    print("=" * 50)
    print(f"\n  Página:  http://localhost:{PORT}/cadastro")
    print(f"\n  Fluxo de teste:")
    print(f"    1. Abra  http://localhost:{PORT}/cadastro  no browser")
    print(f"    2. Acesse http://localhost:{PORT}/simular?uid=4A+2B+3C+1D")
    print(f"       (1ª chamada ativa setup_mode)")
    print(f"    3. Acesse o mesmo link novamente")
    print(f"       (2ª chamada injeta o UID na página)")
    print(f"    4. Preencha nome/cargo e envie — veja o resultado aqui")
    print(f"\n  Ctrl+C para encerrar\n")

    httpd = HTTPServer(("localhost", PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Servidor encerrado.")