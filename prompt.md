# Task 2 — Login com permissões + cadastro via RFID + lista de acessos

## Contexto do projeto
Sistema de controle de acesso por RFID para uma empresa fictícia.
Stack: Flask (Python) + PostgreSQL + MQTT (broker externo com TLS) + HTML/JS puro no frontend.
O Flask roda no PC local (Windows/WSL) e deve ser acessível na rede local via 0.0.0.0:5000.
O broker MQTT é mqtt.janks.dev.br:8883 com TLS (sem autenticação por certificado cliente,
apenas TLS padrão via ssl.PROTOCOL_TLS).

## Estado atual
- Projeto Flask já existe com estrutura básica
- Banco PostgreSQL já tem tabelas criadas:
  - funcionarios (id, nome, cargo, ativo)
  - cartoes_rfid (id, uid, id_funcionario, ativo)
  - areas (id, nome, descricao)
  - permissoes (id_cartao, id_area)
  - registros_acesso (id, uid, id_funcionario, id_area, resultado, data_hora)

## O que precisa ser implementado nesta task

### 1. Novas tabelas no banco (criar migration SQL)
Criar arquivo `migrations/002_login.sql` com:

```sql
CREATE TABLE IF NOT EXISTS usuarios (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(100) NOT NULL,
  email VARCHAR(100) UNIQUE NOT NULL,
  senha_hash VARCHAR(255) NOT NULL,
  nivel_acesso VARCHAR(20) NOT NULL CHECK (nivel_acesso IN ('admin', 'operador')),
  id_funcionario INT REFERENCES funcionarios(id) ON DELETE SET NULL,
  criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessoes (
  token UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  id_usuario INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  nivel_acesso VARCHAR(20) NOT NULL,
  criado_em TIMESTAMP DEFAULT NOW(),
  expira_em TIMESTAMP NOT NULL
);

-- Alterar registros_acesso para distinguir tipos de negação
ALTER TABLE registros_acesso
  DROP COLUMN IF EXISTS resultado,
  ADD COLUMN resultado VARCHAR(30) NOT NULL DEFAULT 'negado_desconhecido'
    CHECK (resultado IN (
      'liberado',
      'negado_sem_permissao',
      'negado_inativo',
      'negado_desconhecido'
    ));

-- Seed: criar usuário admin padrão (senha: admin123)
INSERT INTO usuarios (nome, email, senha_hash, nivel_acesso)
VALUES (
  'Administrador',
  'admin@sistema.com',
  '$2b$12$PLACEHOLDER_HASH',  -- substituir pelo hash real gerado no passo de setup
  'admin'
) ON CONFLICT (email) DO NOTHING;
```

### 2. Backend Flask — novos arquivos e rotas

Instalar dependências (adicionar ao requirements.txt):
- flask
- psycopg2-binary
- bcrypt
- paho-mqtt
- qrcode[pil]
- python-dotenv

Criar `.env` na raiz (se não existir):
DB_URL=postgresql://usuario:senha@localhost:5432/nome_do_banco

MQTT_HOST=mqtt.janks.dev.br

MQTT_PORT=8883

MQTT_USE_TLS=true

FLASK_HOST=0.0.0.0

FLASK_PORT=5000

LOCAL_IP=DESCOBRIR_AUTOMATICAMENTE  # usar socket.gethostbyname(socket.gethostname())

SECRET_KEY=chave-secreta-trocar-em-producao

#### 2.1 auth.py — decorators de autenticação
Criar `auth.py` com dois decorators:

`@requer_login`
- Lê header `Authorization: Bearer <token>`
- Consulta tabela sessoes WHERE token = ? AND expira_em > NOW()
- Se inválido: retorna JSON {"erro": "Não autorizado"}, 401
- Se válido: injeta `request.usuario = {id_usuario, nivel_acesso}` e chama a rota

`@requer_admin`
- Deve ser usado APÓS @requer_login
- Verifica se request.usuario['nivel_acesso'] == 'admin'
- Se não: retorna JSON {"erro": "Acesso negado"}, 403

#### 2.2 Rotas de autenticação

`POST /api/login`
- Body: {"email": "...", "senha": "..."}
- SELECT na tabela usuarios WHERE email = ?
- Verificar senha com bcrypt.checkpw()
- Se ok: INSERT em sessoes com expira_em = NOW() + 8 horas, retornar {"token": "...", "nivel": "...", "nome": "..."}
- Se falhar: {"erro": "Credenciais inválidas"}, 401

`POST /api/logout`
- Requer @requer_login
- DELETE FROM sessoes WHERE token = ?
- Retorna 200

`GET /api/me`
- Requer @requer_login
- Retorna dados do usuário logado (sem senha_hash)

#### 2.3 Fluxo de cadastro via cartão RFID

Criar thread MQTT em background (usar paho-mqtt com loop_start(), NÃO loop_forever()).
Conectar ao broker com TLS:
```python
import ssl
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.tls_insecure_set(True)
```

Subscrever em: `rfid/cadastro/novo`

Ao receber mensagem no tópico rfid/cadastro/novo:
- Payload esperado: {"uid": "XXXX", "id_leitor": "leitor_01"}
- Verificar se uid já existe em cartoes_rfid
  - Se sim: publicar em `rfid/cadastro/erro` com {"erro": "UID já cadastrado", "uid": "XXXX"}
  - Se não: gerar QR Code
- Gerar QR Code:
  - URL: f"http://{LOCAL_IP}:5000/cadastro?uid={uid}"
  - Usar biblioteca qrcode, gerar imagem PIL
  - Converter para base64: base64.b64encode(buffer.getvalue()).decode()
  - Publicar em `rfid/cadastro/qrcode` com {"uid": uid, "qrcode_base64": "..."}

`GET /cadastro`
- Serve o arquivo static/cadastro.html
- (O UID vem via query param ?uid=XXXX, tratado pelo JS)

`POST /api/funcionarios`
- Requer @requer_login e @requer_admin
- Body: {"uid": "...", "nome": "...", "cargo": "...", "nivel_acesso": "operador", "areas": [1, 2]}
- Validar campos obrigatórios
- Transação:
  1. INSERT INTO funcionarios (nome, cargo, ativo) VALUES (?, ?, true)
  2. INSERT INTO cartoes_rfid (uid, id_funcionario, ativo) VALUES (?, id_gerado, true)
  3. Para cada area em areas: INSERT INTO permissoes (id_cartao, id_area) VALUES (id_cartao_gerado, area)
  4. Se nivel_acesso fornecido: INSERT INTO usuarios (nome, email, senha_hash, nivel_acesso, id_funcionario)
     - email padrão: nome_sem_espacos@sistema.com
     - senha padrão: primeiros 8 chars do uid
- Após sucesso: publicar em `rfid/cadastro/concluido` com {"uid": uid, "nome": nome}
- Retornar 201 com o funcionário criado completo

#### 2.4 Lista de acessos com filtros

`GET /api/acessos`
- Requer @requer_login
- Query params opcionais: funcionario_id, area_id, resultado, data_inicio, data_fim, page (default 1), limit (default 20)
- Se nivel == 'operador': forçar WHERE id_funcionario = id do usuário logado (ignorar filtro funcionario_id do request)
- Query com LEFT JOIN em funcionarios e areas
- Retornar: {"registros": [...], "total": N, "pagina": N, "paginas": N}
- Cada registro: {id, uid, funcionario (nome ou null), cargo, area, resultado, data_hora formatada em ISO}

`GET /api/acessos/exportar`
- Mesmos filtros e mesma lógica de permissão do endpoint acima
- Retornar CSV com header Content-Disposition: attachment; filename="acessos_{data_hoje}.csv"
- Colunas: ID, UID, Funcionário, Cargo, Área, Resultado, Data/Hora

`GET /api/areas`
- Requer @requer_login
- Retorna lista de todas as áreas (para popular dropdowns)

`GET /api/funcionarios`
- Requer @requer_login e @requer_admin
- Retorna lista de funcionários com cartões e permissões

### 3. Frontend — HTML/JS puro em /static

#### 3.1 login.html
- Campos: email + senha
- Ao submeter: fetch POST /api/login
- Salvar token e nivel no localStorage
- Redirecionar: admin → /static/admin.html, operador → /static/operador.html
- Se já tem token no localStorage ao abrir: tentar GET /api/me e redirecionar se válido
- Mensagem de erro inline (não usar alert())

#### 3.2 admin.html
- Verificar token no localStorage ao carregar; se ausente redirecionar para login.html
- Navegação por abas sem recarregar página:
  - Aba "Acessos": tabela com filtros (ver abaixo)
  - Aba "Funcionários": listagem com botões ativar/desativar cartão
  - Aba "Cadastrar": formulário manual de cadastro
- Header com nome do usuário e botão Sair (chama POST /api/logout + limpa localStorage)
- Todo fetch deve incluir header: Authorization: Bearer {token do localStorage}

#### 3.3 operador.html
- Mesma verificação de token
- Mostra apenas próprio histórico de acessos (GET /api/acessos sem filtros extras — backend filtra)
- Não mostrar filtro de funcionário

#### 3.4 cadastro.html
- Ler uid do query param ?uid=XXXX via URLSearchParams
- Campo UID já preenchido e readonly
- Campos: nome completo, cargo, nível de acesso (select: admin/operador), áreas (checkboxes carregados via GET /api/areas)
- Submeter via POST /api/funcionarios com token do localStorage
- Mostrar mensagem de sucesso ou erro após resposta

#### 3.5 Componente de tabela de acessos (reutilizado em admin e operador)
- Filtros em linha: dropdown funcionário (só admin), dropdown área, inputs de data início/fim, badges clicáveis de resultado (Todos / Liberado / Negado sem permissão / Negado inativo / Negado desconhecido)
- Botão "Aplicar filtros" dispara fetch com query params montados
- Totalizador acima da tabela: "X liberados · Y negados · Z desconhecidos"
- Tabela com colunas: Funcionário, Área, Resultado (badge colorido), Data/Hora
- Paginação simples: botões Anterior / Próximo com indicador "Página X de Y"
- Botão "Exportar CSV" chama /api/acessos/exportar com os mesmos filtros ativos

### 4. Rota raiz e organização de arquivos
/

├── app.py               # inicialização Flask + registro de blueprints + start MQTT thread

├── auth.py              # decorators requer_login e requer_admin

├── db.py                # conexão PostgreSQL (pool simples com psycopg2)

├── mqtt_client.py       # configuração paho-mqtt com TLS, loop_start, handlers

├── routes/

│   ├── auth_routes.py   # /api/login, /api/logout, /api/me

│   ├── funcionarios.py  # /api/funcionarios, /api/areas

│   ├── acessos.py       # /api/acessos, /api/acessos/exportar

│   └── cadastro.py      # /cadastro, /api/cadastro via RFID

├── static/

│   ├── login.html

│   ├── admin.html

│   ├── operador.html

│   └── cadastro.html

└── migrations/

└── 002_login.sql

### 5. app.py — ponto de entrada

```python
# estrutura esperada:
# - carregar .env
# - inicializar pool de conexão com banco
# - registrar blueprints de rotas
# - iniciar thread MQTT (mqtt_client.start()) com use_reloader=False
# - app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
```

### 6. Restrições e observações importantes

- NÃO usar Flask-Login, Flask-JWT ou qualquer extensão de autenticação — implementar manualmente com a tabela sessoes
- NÃO usar SQLAlchemy — usar psycopg2 direto com queries SQL explícitas
- O MQTT usa TLS com cert_reqs=ssl.CERT_NONE (broker do professor sem certificado cliente)
- O Flask deve rodar com use_reloader=False para evitar duplicação da thread MQTT
- Descobrir o IP local automaticamente com socket.gethostbyname(socket.gethostname()) e usar na geração do QR Code
- Senhas armazenadas SEMPRE com bcrypt — nunca em texto puro
- Criar um script setup_admin.py separado que gera o hash bcrypt da senha e faz o INSERT do admin inicial
- Todo endpoint deve retornar JSON com Content-Type: application/json
- CORS: adicionar header Access-Control-Allow-Origin: * nas respostas (ou usar flask-cors)

### 7. Entregáveis esperados ao final

1. Login funcionando com redirecionamento correto por nível
2. Admin cadastrando funcionário via formulário manual
3. Fluxo RFID: publicar em rfid/cadastro/novo via MQTTx → Flask gera QR Code → publicar em rfid/cadastro/qrcode (verificar payload no MQTTx)
4. Lista de acessos com todos os filtros combinados funcionando
5. Exportação CSV abrindo corretamente
6. Operador vendo apenas próprio histórico
