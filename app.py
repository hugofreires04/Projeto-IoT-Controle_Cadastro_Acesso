from flask import Flask

import config
from routes import registrar_rotas

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

registrar_rotas(app)


# ── Ponto de entrada ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=config.FLASK_DEBUG, host=config.FLASK_HOST, port=config.FLASK_PORT)
