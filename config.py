import os
import socket
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL  = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/acesso_rfid")
SECRET_KEY    = os.getenv("SECRET_KEY", "chave-secreta-dev")
MQTT_BROKER   = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT     = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USE_TLS  = os.getenv("MQTT_USE_TLS", "false").lower() in ("1", "true", "yes", "on")
MQTT_USER     = os.getenv("MQTT_USER") or None
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD") or None

FLASK_HOST   = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT   = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG  = os.getenv("FLASK_DEBUG", "true").lower() in ("1", "true", "yes", "on")

LOCAL_IP = os.getenv("LOCAL_IP") or socket.gethostbyname(socket.gethostname())
