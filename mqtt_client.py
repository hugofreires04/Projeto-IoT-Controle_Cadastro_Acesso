"""Cliente MQTT (paho-mqtt) com TLS — fluxo de cadastro de cartão RFID via QR Code.

Roda em thread de background (loop_start), separado do fluxo de acesso da
catraca que já é mediado pelo Node-RED. Aqui o Flask conversa direto com o
broker apenas para os tópicos rfid/cadastro/*.
"""

import base64
import json
import ssl
from io import BytesIO

import paho.mqtt.client as mqtt
import qrcode

import config
from db import get_cursor, normalizar_uid

TOPICO_CADASTRO_NOVO = "rfid/cadastro/novo"
TOPICO_CADASTRO_QRCODE = "rfid/cadastro/qrcode"
TOPICO_CADASTRO_ERRO = "rfid/cadastro/erro"
TOPICO_CADASTRO_CONCLUIDO = "rfid/cadastro/concluido"

_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)


def publicar(topico, payload: dict):
    _client.publish(topico, json.dumps(payload))


def _uid_ja_cadastrado(uid: str) -> bool:
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM cartoes_rfid WHERE uid = %s", (uid,))
        return cur.fetchone() is not None


def _gerar_qrcode_base64(uid: str) -> str:
    url = f"http://{config.LOCAL_IP}:{config.FLASK_PORT}/cadastro?uid={uid}"
    imagem = qrcode.make(url)

    buffer = BytesIO()
    imagem.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def _ao_receber_cadastro_novo(payload: dict):
    uid = normalizar_uid(payload.get("uid", ""))
    if not uid:
        return

    if _uid_ja_cadastrado(uid):
        publicar(TOPICO_CADASTRO_ERRO, {"erro": "UID já cadastrado", "uid": uid})
        return

    qrcode_base64 = _gerar_qrcode_base64(uid)
    publicar(TOPICO_CADASTRO_QRCODE, {"uid": uid, "qrcode_base64": qrcode_base64})


def _on_connect(client, userdata, flags, reason_code, properties):
    client.subscribe(TOPICO_CADASTRO_NOVO)


def _on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return

    if msg.topic == TOPICO_CADASTRO_NOVO:
        _ao_receber_cadastro_novo(payload)


def start():
    _client.on_connect = _on_connect
    _client.on_message = _on_message

    if config.MQTT_USER and config.MQTT_PASSWORD:
        _client.username_pw_set(config.MQTT_USER, config.MQTT_PASSWORD)

    if config.MQTT_USE_TLS:
        _client.tls_set(cert_reqs=ssl.CERT_NONE)
        _client.tls_insecure_set(True)

    _client.connect(config.MQTT_BROKER, config.MQTT_PORT, keepalive=60)
    _client.loop_start()
