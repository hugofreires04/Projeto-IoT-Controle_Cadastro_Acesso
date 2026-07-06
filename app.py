"""app.py — Ponto de entrada da aplicação Flask.

Projeto IoT — Controle de Cadastro e Acesso via RFID (ENG4051 / PUC-Rio).

Responsabilidades deste arquivo (de propósito, poucas):
  1. Criar a instância do Flask e carregar a SECRET_KEY.
  2. Registrar os blueprints de rotas (ver routes/__init__.py).
  3. Liberar CORS para as chamadas do Node-RED e do painel web.
  4. Redirecionar a raiz (/) para a tela de login.

O painel web é servido como arquivos estáticos (static/*.html) e conversa
com o backend exclusivamente pela API REST /api/*.
"""

from flask import Flask, redirect

import config
from routes import registrar_rotas

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Cada grupo de rotas vive em um blueprint próprio (auth, funcionários,
# cadastros, acessos) — ver o pacote routes/.
registrar_rotas(app)


@app.after_request
def adicionar_cors(response):
    """Adiciona cabeçalhos CORS a todas as respostas.

    Necessário porque o Node-RED (porta 1880) e, em desenvolvimento, o painel
    podem chamar a API a partir de outra origem que não a do Flask (porta 5000).
    """
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


@app.route("/")
def raiz():
    """Acessar http://servidor:5000/ leva direto para a tela de login."""
    return redirect("/static/login.html")


# ── Ponto de entrada ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    # use_reloader=False evita que o Flask suba dois processos em modo debug
    # (o reloader duplicaria conexões com o banco durante o desenvolvimento).
    app.run(debug=config.FLASK_DEBUG, host=config.FLASK_HOST, port=config.FLASK_PORT, use_reloader=False)
