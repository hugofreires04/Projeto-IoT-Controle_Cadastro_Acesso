from flask import Flask, redirect

import config
import mqtt_client
from routes import registrar_rotas

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

registrar_rotas(app)


@app.after_request
def adicionar_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


@app.route("/")
def raiz():
    return redirect("/static/login.html")


# ── Ponto de entrada ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    mqtt_client.start()
    app.run(debug=config.FLASK_DEBUG, host=config.FLASK_HOST, port=config.FLASK_PORT, use_reloader=False)
