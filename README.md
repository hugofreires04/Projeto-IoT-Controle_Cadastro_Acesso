# Sistema de Controle de Acesso via RFID

Projeto da disciplina **ENG4051 — Projeto Internet das Coisas (PUC-Rio)**.

Controle de cadastro e acesso de funcionários via cartão RFID com catraca física, login com permissões (admin/operador) e cadastro de funcionário via QR Code gerado a partir da leitura do cartão.

## Arquitetura

```
ESP32 (RFID) → MQTT Broker (TLS) → Node-RED → Flask (REST API) → PostgreSQL/TimescaleDB
                     │                                  ↕
                     │                         Painel Web (login + permissões)
                     └── rfid/cadastro/* ──────────────→ Flask (paho-mqtt direto)
```

- O fluxo de **acesso da catraca** (`catraca/acesso` → `catraca/resposta`) continua mediado pelo Node-RED, chamando `GET /api/acesso/<uid>` e `POST /api/acesso/log` no Flask.
- O fluxo de **cadastro de novo cartão** (`rfid/cadastro/*`) é tratado pelo próprio Flask, que se conecta direto ao broker MQTT (TLS) via `paho-mqtt` em uma thread de background.

## Estrutura do projeto

```
app.py                       → cria a app Flask, registra rotas e inicia a thread MQTT
config.py                    → configurações via variáveis de ambiente
db.py                        → conexão com o banco e normalização do UID
auth.py                      → decorators requer_login / requer_admin (sessões manuais)
mqtt_client.py                → cliente paho-mqtt (TLS) do fluxo de cadastro via QR Code
setup_admin.py                → gera o hash bcrypt e cria/atualiza o usuário admin inicial
routes/
├── auth_routes.py           → /api/login, /api/logout, /api/me
├── funcionarios.py          → /api/funcionarios, /api/funcionarios/<id>/cartoes/<id>, /api/areas
├── acessos.py                → /api/acessos, /api/acessos/exportar, /api/acesso/<uid>, /api/acesso/log
└── cadastro.py                → /cadastro (serve static/cadastro.html)
static/
├── login.html, admin.html, operador.html, cadastro.html
├── js/auth.js                 → autenticação (token no localStorage)
├── js/acessos.js              → componente de tabela de acessos (filtros/paginação/CSV)
├── js/admin.js                → abas do painel admin, listagem de funcionários, cadastro manual
└── style.css
database/schema.sql            → schema original (TimescaleDB)
migrations/002_login.sql       → evolui o schema: cartoes_rfid, areas, permissoes, usuarios, sessoes, registros_acesso
nodered/flow_acesso.json        → fluxo Node-RED do controle de acesso da catraca
```

## Requisitos

- Python 3.10+
- PostgreSQL 14+ com extensão **TimescaleDB**
- Node-RED 3+ (fluxo da catraca)
- Broker MQTT com TLS (ex.: `mqtt.janks.dev.br:8883`)

## Instalação passo a passo

### 1. Criar o banco de dados e executar os scripts SQL

```sql
CREATE DATABASE acesso_rfid;
```

Conecte ao banco `acesso_rfid` e execute, **nesta ordem**:

1. `database/schema.sql` — schema original (funcionários + histórico de acesso)
2. `migrations/002_login.sql` — evolui o schema: separa cartões RFID do funcionário, adiciona áreas, permissões por área, usuários/sessões de login e o novo `registros_acesso` (com motivo de negação detalhado)

### 2. Criar o arquivo `.env`

```bash
cp .env.example .env
```

Preencha:

```env
DATABASE_URL=postgresql://SEU_USUARIO:SUA_SENHA@localhost:5432/acesso_rfid
SECRET_KEY=uma-chave-secreta-qualquer

MQTT_BROKER=mqtt.janks.dev.br
MQTT_PORT=8883
MQTT_USE_TLS=true
MQTT_USER=
MQTT_PASSWORD=

FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=true

# Deixe em branco para descobrir automaticamente via socket.gethostbyname()
LOCAL_IP=
```

### 3. Instalar dependências Python

```bash
pip install -r requirements.txt
```

### 4. Criar o usuário admin inicial

A migration grava um usuário admin com um hash placeholder (inválido). Rode o script abaixo para gerar o hash bcrypt real:

```bash
python setup_admin.py            # cria admin@sistema.com com senha "admin123"
python setup_admin.py outrasenha # ou com uma senha customizada
```

### 5. Rodar o servidor Flask

```bash
python app.py
```

O painel estará disponível em `http://localhost:5000` (redireciona para `/static/login.html`).

### 6. Importar o fluxo no Node-RED

1. Abra o Node-RED (`http://localhost:1880`)
2. Menu (≡) → **Import** → **Clipboard**
3. Cole o conteúdo do arquivo `nodered/flow_acesso.json`
4. Clique em **Import** e depois em **Deploy**

## Login e permissões

- **admin**: acessa `/static/admin.html` — abas de Acessos (todos), Funcionários (com ativar/desativar cartão) e Cadastrar (formulário manual).
- **operador**: acessa `/static/operador.html` — vê apenas o próprio histórico de acessos (o backend força o filtro pelo `id_funcionario` vinculado ao usuário).

O token de sessão é salvo no `localStorage` e enviado em todo fetch como `Authorization: Bearer <token>`. Sessões expiram 8h após o login (tabela `sessoes`).

## Fluxo de cadastro via cartão RFID + QR Code

1. O leitor RFID publica em `rfid/cadastro/novo`: `{"uid": "XXXX", "id_leitor": "leitor_01"}`
2. O Flask verifica se o UID já existe em `cartoes_rfid`:
   - Se sim → publica em `rfid/cadastro/erro`: `{"erro": "UID já cadastrado", "uid": "XXXX"}`
   - Se não → gera um QR Code apontando para `http://{LOCAL_IP}:5000/cadastro?uid=XXXX` e publica em `rfid/cadastro/qrcode`: `{"uid": "XXXX", "qrcode_base64": "..."}`
3. Um admin já logado escaneia o QR Code, preenche nome/cargo/áreas em `/cadastro` e submete `POST /api/funcionarios`
4. Ao concluir o cadastro, o Flask publica em `rfid/cadastro/concluido`: `{"uid": "XXXX", "nome": "..."}`

## Endpoints da API REST

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| POST | `/api/login` | — | Autentica e cria uma sessão (token válido por 8h) |
| POST | `/api/logout` | login | Encerra a sessão atual |
| GET | `/api/me` | login | Dados do usuário logado |
| POST | `/api/funcionarios` | admin | Cadastra funcionário + cartão + permissões (e usuário, se `nivel_acesso` informado) |
| GET | `/api/funcionarios` | admin | Lista funcionários com seus cartões e permissões por área |
| PUT | `/api/funcionarios/<id>/cartoes/<id_cartao>` | admin | Ativa/desativa um cartão |
| GET | `/api/areas` | login | Lista todas as áreas |
| GET | `/api/acessos` | login | Lista paginada de acessos, com filtros (`funcionario_id`, `area_id`, `resultado`, `data_inicio`, `data_fim`, `page`, `limit`); operador só vê o próprio histórico |
| GET | `/api/acessos/exportar` | login | Mesmos filtros, retorna CSV |
| GET | `/api/acesso/<uid>` | — | Consultado pelo Node-RED a cada leitura na catraca |
| POST | `/api/acesso/log` | — | Registra o resultado de uma leitura (chamado pelo Node-RED) |

## Exemplos de payload MQTT

Catraca (fluxo existente, mediado pelo Node-RED), publique em `catraca/acesso`:

```json
{ "uid": "E7 45 D6 19", "tipo": "entrada" }
```

Cadastro de novo cartão (fluxo novo, Flask consome direto), publique em `rfid/cadastro/novo`:

```json
{ "uid": "AA BB CC DD", "id_leitor": "leitor_01" }
```
