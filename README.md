# Sistema de Controle de Acesso via RFID

Projeto da disciplina **ENG4051 — Projeto Internet das Coisas (PUC-Rio)**.

Controle de cadastro e acesso de funcionários via cartão RFID com catraca física.

## Arquitetura

```
ESP32 (RFID) → MQTT Broker (Mosquitto) → Node-RED → Flask (REST API) → PostgreSQL/TimescaleDB
                                                              ↕
                                                     Painel Admin (HTML)
```

## Estrutura do projeto

```
app.py                       → cria a app Flask e registra as rotas (ponto de entrada)
config.py                    → configurações via variáveis de ambiente
db.py                        → conexão com o banco e normalização do UID
routes/
├── api_funcionarios.py      → API REST de funcionários (CRUD)
├── api_acesso.py            → API REST de controle de acesso, logs e stats
└── painel.py                → painel admin (HTML)
templates/                    → páginas HTML (Jinja2)
static/style.css              → estilos do painel admin
database/schema.sql           → schema do banco (TimescaleDB)
```

## Requisitos

- Python 3.10+
- PostgreSQL 14+ com extensão **TimescaleDB**
- Node-RED 3+
- Mosquitto (MQTT broker)

## Instalação passo a passo

### 1. Criar o banco de dados e executar o schema

No Beekeeper Studio (ou psql), crie o banco e execute o arquivo de schema:

```sql
CREATE DATABASE acesso_rfid;
```

Conecte ao banco `acesso_rfid` e execute o conteúdo de `database/schema.sql`.

### 2. Criar o arquivo `.env`

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```env
DATABASE_URL=postgresql://SEU_USUARIO:SUA_SENHA@localhost:5432/acesso_rfid
SECRET_KEY=uma-chave-secreta-qualquer
MQTT_BROKER=localhost
MQTT_PORT=1883

FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=true
```

### 3. Instalar dependências Python

```bash
pip install -r requirements.txt
```

### 4. Rodar o servidor Flask

```bash
python app.py
```

O painel admin estará disponível em: `http://localhost:5000`

### 5. Importar o fluxo no Node-RED

1. Abra o Node-RED (`http://localhost:1880`)
2. Menu (≡) → **Import** → **Clipboard**
3. Cole o conteúdo do arquivo `nodered/flow_acesso.json`
4. Clique em **Import** e depois em **Deploy**

## Endpoints da API REST

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/funcionarios` | Lista todos os funcionários |
| GET | `/api/funcionarios/<id>` | Busca funcionário por ID |
| POST | `/api/funcionarios` | Cadastra novo funcionário |
| PUT | `/api/funcionarios/<id>` | Edita funcionário |
| DELETE | `/api/funcionarios/<id>` | Deleta funcionário |
| GET | `/api/acesso/<uid>` | Verifica permissão pelo UID do cartão |
| POST | `/api/acesso/log` | Registra log de acesso |
| GET | `/api/logs` | Últimos 100 logs de acesso |
| GET | `/api/logs/<uid>` | Últimos 50 logs de um funcionário |
| GET | `/api/stats` | Acessos agrupados por hora nas últimas 24h (para Grafana) |

## Exemplos de payload MQTT para testar

Publique no tópico `catraca/acesso` para simular uma leitura de cartão:

```json
{ "uid": "E7 45 D6 19", "tipo": "entrada" }
```

```json
{ "uid": "A3 BC 12 F0", "tipo": "saida" }
```

```json
{ "uid": "00 00 00 00", "tipo": "entrada" }
```

O Node-RED responderá no tópico `catraca/resposta` com:

```json
{ "autorizado": true, "nome": "João Silva", "motivo": "" }
```

ou

```json
{ "autorizado": false, "nome": "Desconhecido", "motivo": "cartao_nao_cadastrado" }
```
