# Sistema de Controle de Acesso via RFID

Projeto da disciplina **ENG4051 — Projeto Internet das Coisas (PUC-Rio)**.

Controle de cadastro e acesso de funcionários via cartão RFID com catraca física, com login e permissões (admin/operador) no painel web.

## Arquitetura

```
ESP32 (RFID) → MQTT Broker → Node-RED → Flask (REST API) → PostgreSQL/TimescaleDB
                                                  ↕
                                         Painel Web (login + permissões)
```

- O fluxo de **acesso da catraca** (`a3/catraca/entrada` → `a3/catraca/resposta`) é mediado pelo Node-RED, chamando `GET /api/acesso/<uid>` e `POST /api/acesso/log` no Flask. A resposta publicada para o ESP é `{"nome": "...", "autorizado": bool, "isAdmin": bool}` — `isAdmin` indica que o dono do cartão tem conta admin no painel, e avisa o firmware para entrar em modo cadastro (a próxima leitura de cartão vai para `a3/cadastros` em vez de `a3/catraca/entrada`).
- O **cadastro de funcionário** é feito manualmente pelo admin no painel: o cartão já é entregue fisicamente à pessoa, e o admin digita o UID na aba "Cadastrar" do `admin.html` — ou usa o UID capturado automaticamente via `a3/cadastros` (banner "Cartão novo lido na catraca", quando um admin entra em modo cadastro na catraca física). O Flask não se conecta diretamente ao broker MQTT — só o Node-RED fala com o broker.

## Estrutura do projeto

```
app.py                       → cria a app Flask e registra as rotas
config.py                    → configurações via variáveis de ambiente
db.py                        → conexão com o banco e normalização do UID
auth.py                      → decorators requer_login / requer_admin (sessões manuais)
setup_admin.py                → gera o hash bcrypt e cria/atualiza o usuário admin inicial
routes/
├── auth_routes.py           → /api/login, /api/logout, /api/me
├── funcionarios.py          → /api/funcionarios, /api/funcionarios/<id>, /api/funcionarios/<id>/cartoes/<id>
├── cadastros.py              → /api/areas (CRUD), /api/usuarios (CRUD), /api/cadastros/uid-pendente
└── acessos.py                → /api/acessos, /api/acessos/exportar, /api/acesso/<uid>, /api/acesso/log
static/
├── login.html, admin.html, operador.html
├── js/auth.js                 → autenticação (token no localStorage)
├── js/acessos.js              → componente de tabela de acessos (filtros/paginação/CSV)
├── js/admin.js                → abas do painel admin, listagem de funcionários, cadastro manual
└── style.css
database/schema.sql            → schema original (TimescaleDB)
migrations/002_login.sql       → evolui o schema: a3_cartoes_rfid, a3_areas, a3_permissoes, a3_usuarios, a3_sessoes, a3_registros_acesso
nodered/flow_acesso.json        → fluxo Node-RED do controle de acesso da catraca
```

## Requisitos

- Python 3.10+
- PostgreSQL 14+ com extensão **TimescaleDB**
- Node-RED 3+ (fluxo da catraca)

## Instalação passo a passo

### 1. Criar o banco de dados e executar os scripts SQL

```sql
CREATE DATABASE acesso_rfid;
```

Conecte ao banco `acesso_rfid` e execute, **nesta ordem**:

1. `database/schema.sql` — schema original (funcionários + histórico de acesso)
2. `migrations/002_login.sql` — evolui o schema: separa cartões RFID do funcionário, adiciona áreas, permissões por área, usuários/sessões de login e o novo `registros_acesso` (com motivo de negação detalhado)
3. `migrations/003_rename_a3.sql` — renomeia as tabelas existentes para o prefixo `a3_`
4. `migrations/004_uids_pendentes.sql` — cria `a3_uids_pendentes`, usada pelo fluxo de cadastro via `a3/cadastros`

### 2. Criar o arquivo `.env`

```bash
cp .env.example .env
```

Preencha:

```env
DATABASE_URL=postgresql://SEU_USUARIO:SUA_SENHA@SEU_HOST:5432/SEU_BANCO
SECRET_KEY=uma-chave-secreta-qualquer

FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=true

MQTT_BROKER=SEU_BROKER
MQTT_PORT=8883
MQTT_USER=SEU_USUARIO_MQTT
MQTT_PASSWORD=SUA_SENHA_MQTT
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

#### Alternativa: rodar com Docker

Com o `.env` já preenchido (passo 2), basta:

```bash
docker compose up --build
```

Isso constrói a imagem (Python 3.12 + dependências do `requirements.txt`) e sobe o container do Flask lendo as variáveis do `.env`. O painel fica disponível em `http://localhost:5000`. Para rodar em background, use `docker compose up --build -d` e acompanhe os logs com `docker compose logs -f`.

Para criar o usuário admin inicial dentro do container:

```bash
docker compose exec app python setup_admin.py
```

Para parar:

```bash
docker compose down
```

> O PostgreSQL/TimescaleDB e o broker MQTT são serviços remotos (ver `DATABASE_URL`/`MQTT_*` no `.env`) — o `docker-compose.yml` sobe apenas o container da aplicação Flask, não bancos ou brokers locais.

### 6. Importar o fluxo no Node-RED

1. Abra o Node-RED (`http://localhost:1880`)
2. Menu (≡) → **Import** → **Clipboard**
3. Cole o conteúdo do arquivo `nodered/flow_acesso.json`
4. Clique em **Import** e depois em **Deploy**

## Login e permissões

- **admin**: acessa `/static/admin.html` — abas de Acessos (todos), Funcionários (com filtros por nome/cargo/status e ativar/desativar funcionário ou cartão individualmente), Cadastrar (formulário manual), Lugares (CRUD de áreas) e Usuários (CRUD de usuários do sistema).
- **operador**: acessa `/static/operador.html` — vê apenas o próprio histórico de acessos (o backend força o filtro pelo `id_funcionario` vinculado ao usuário).

O token de sessão é salvo no `localStorage` e enviado em todo fetch como `Authorization: Bearer <token>`. Sessões expiram 8h após o login (tabela `a3_sessoes`).

## Cadastro de funcionário

Só o admin cadastra (aba "Cadastrar" em `admin.html`). O fluxo é manual: o admin digita o UID diretamente no formulário (junto com nome, cargo, nível de acesso opcional e áreas permitidas) e envia `POST /api/funcionarios`. Não há geração de QR Code.

O UID pode vir de duas formas:
1. **Digitado à mão** — o cartão já foi entregue fisicamente à pessoa e o admin digita o UID impresso/anotado.
2. **Lido na catraca em modo cadastro** — o admin passa o próprio cartão na catraca (`GET /api/acesso/<uid>` retorna `isAdmin=true`), o firmware entra em modo cadastro e a leitura seguinte (do cartão da nova pessoa) é publicada em `a3/cadastros`. O Node-RED repassa para `POST /api/cadastros/uid-pendente`, que fica disponível em `GET /api/cadastros/uid-pendente` e aparece como banner "Cartão novo lido na catraca" na aba Cadastrar, com os botões **Usar este UID** (preenche o campo) e **Descartar**. O registro pendente é apagado automaticamente quando o cadastro é concluído com esse UID, e expira sozinho após **5 minutos** (`TTL_MINUTOS_UID_PENDENTE` em `routes/cadastros.py`) para não aparecer "fantasma" pro próximo admin caso ninguém complete ou descarte o cadastro.

## Endpoints da API REST

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| POST | `/api/login` | — | Autentica e cria uma sessão (token válido por 8h) |
| POST | `/api/logout` | login | Encerra a sessão atual |
| GET | `/api/me` | login | Dados do usuário logado |
| POST | `/api/funcionarios` | admin | Cadastra funcionário + cartão + permissões (e usuário, se `nivel_acesso` informado) |
| GET | `/api/funcionarios` | admin | Lista funcionários com seus cartões e permissões por área; aceita filtros `nome`, `cargo`, `status` (`ativo`/`inativo`) |
| PUT | `/api/funcionarios/<id>` | admin | Ativa/desativa o funcionário (`{"ativo": bool}`) |
| PUT | `/api/funcionarios/<id>/cartoes/<id_cartao>` | admin | Ativa/desativa um cartão específico |
| GET | `/api/areas` | login | Lista todas as áreas/lugares |
| POST | `/api/areas` | admin | Cria um lugar (`{"nome": "...", "descricao": "..."}`) |
| PUT | `/api/areas/<id>` | admin | Edita um lugar |
| DELETE | `/api/areas/<id>` | admin | Remove um lugar (remove em cascata as permissões associadas) |
| GET | `/api/usuarios` | admin | Lista usuários do sistema com o funcionário vinculado |
| POST | `/api/usuarios` | admin | Cria um usuário (`{"nome", "email", "senha", "nivel_acesso", "id_funcionario"}`) |
| PUT | `/api/usuarios/<id>` | admin | Atualiza `nivel_acesso` e/ou redefine a `senha` |
| DELETE | `/api/usuarios/<id>` | admin | Remove um usuário (exceto o próprio usuário logado) |
| GET | `/api/acessos` | login | Lista paginada de acessos, com filtros (`funcionario_id`, `area_id`, `resultado`, `data_inicio`, `data_fim`, `page`, `limit`); operador só vê o próprio histórico |
| GET | `/api/acessos/exportar` | login | Mesmos filtros, retorna CSV |
| GET | `/api/acesso/<uid>` | — | Consultado pelo Node-RED a cada leitura na catraca; responde `{"nome", "autorizado", "isAdmin", "cargo"}` |
| POST | `/api/acesso/log` | — | Registra o resultado de uma leitura (chamado pelo Node-RED) |
| POST | `/api/cadastros/uid-pendente` | — | Registra um UID lido em modo cadastro (chamado pelo Node-RED ao receber `a3/cadastros`) |
| GET | `/api/cadastros/uid-pendente` | admin | Retorna o UID pendente mais recente (ou `null`), para a aba Cadastrar |
| DELETE | `/api/cadastros/uid-pendente/<id>` | admin | Descarta um UID pendente sem cadastrar |

## Exemplo de payload MQTT (catraca)

Publique no tópico `a3/catraca/entrada` para simular uma leitura na catraca (fluxo mediado pelo Node-RED):

```json
{ "uid": "E7 45 D6 19", "tipo": "entrada" }
```

O Node-RED responde em `a3/catraca/resposta`:

```json
{ "nome": "João Silva", "autorizado": true, "isAdmin": false }
```

Se `isAdmin` vier `true`, o firmware deve entrar em modo cadastro e publicar a próxima leitura de cartão em `a3/cadastros`:

```json
{ "uid": "AA BB CC DD" }
```
