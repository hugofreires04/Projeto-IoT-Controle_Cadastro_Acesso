"""config.py — Configurações da aplicação via variáveis de ambiente.

Os valores são lidos do arquivo .env (carregado pelo python-dotenv) ou do
ambiente do sistema; os defaults abaixo servem para desenvolvimento local.
Em produção (Docker/Raspberry Pi), tudo vem do .env — ver .env.example.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Conexão com o PostgreSQL/TimescaleDB (usuário:senha@host:porta/banco)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/acesso_rfid")

# Chave usada pelo Flask para assinar dados de sessão/cookies
SECRET_KEY   = os.getenv("SECRET_KEY", "chave-secreta-dev")

# Endereço do broker MQTT (usado pelo Node-RED; o Flask não fala MQTT direto)
MQTT_BROKER  = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT    = int(os.getenv("MQTT_PORT", "1883"))

# Onde o Flask escuta: 0.0.0.0 = todas as interfaces (acessível na rede local)
FLASK_HOST   = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT   = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG  = os.getenv("FLASK_DEBUG", "true").lower() in ("1", "true", "yes", "on")
