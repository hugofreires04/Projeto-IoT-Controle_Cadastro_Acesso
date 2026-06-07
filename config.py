import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/acesso_rfid")
SECRET_KEY   = os.getenv("SECRET_KEY", "chave-secreta-dev")
MQTT_BROKER  = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT    = int(os.getenv("MQTT_PORT", "1883"))
