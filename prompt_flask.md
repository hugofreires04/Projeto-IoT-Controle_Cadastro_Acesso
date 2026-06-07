# Prompt — Servidor Flask: Cadastro de Funcionários IoT

## Contexto do projeto

Estou desenvolvendo um sistema de controle de acesso via RFID para uma empresa, como projeto da disciplina ENG4051 (Projeto Internet das Coisas) da PUC-Rio. A arquitetura é a seguinte:

```
ESP32 (RFID) → MQTT Broker (Mosquitto) → Node-RED → Flask (REST API) → PostgreSQL/TimescaleDB
                                                                ↕
                                                       Painel Admin (HTML)
```

O ESP32 lê cartões RFID e publica eventos MQTT. O Node-RED consome esses eventos, consulta o Flask para validar permissões, registra o acesso e publica a resposta de volta para o ESP32.

---

## O que precisa ser construído

### 1. Banco de dados — PostgreSQL com TimescaleDB

Crie um arquivo `database/schema.sql` com:

**Tabela `funcionarios`:**
- `id` — serial primary key
- `nome` — varchar(100), not null
- `uid_cartao` — varchar(30), unique, not null (ex: "E7 45 D6 19")
- `cargo` — varchar(100)
- `ativo` — boolean, default true (define se tem acesso)
- `criado_em` — timestamp with time zone, default now()
- `atualizado_em` — timestamp with time zone, default now()

**Hipertabela `logs_acesso`** (TimescaleDB):
- `data_hora` — timestamp with time zone, default now(), parte da PK
- `uid_cartao` — varchar(30)
- `nome_funcionario` — varchar(100) (desnormalizado para facilitar consultas)
- `tipo` — varchar(10) — valores: 'entrada' ou 'saida'
- `autorizado` — boolean
- `primary key (data_hora, uid_cartao)`
- Chamar `SELECT create_hypertable('logs_acesso', 'data_hora');` após criar a tabela

Adicionar também dados de exemplo (3 funcionários) para facilitar os testes.

---

### 2. Servidor Flask

Crie a seguinte estrutura de projeto:

```
projeto/
├── app.py
├── config.py
├── database/
│   └── schema.sql
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── cadastrar.html
│   └── editar.html
├── static/
│   └── style.css
├── requirements.txt
└── README.md
```

#### `config.py`
Configurações via variáveis de ambiente com fallback para desenvolvimento local:
- `DATABASE_URL` — string de conexão PostgreSQL
- `SECRET_KEY` — chave secreta do Flask
- `MQTT_BROKER` — endereço do broker (default: localhost)
- `MQTT_PORT` — porta (default: 1883)

#### `app.py` — endpoints REST (JSON)

**Funcionários:**
- `GET /api/funcionarios` — lista todos os funcionários (retorna array JSON)
- `GET /api/funcionarios/<int:id>` — busca funcionário por id
- `POST /api/funcionarios` — cadastra funcionário (corpo JSON: nome, uid_cartao, cargo, ativo)
- `PUT /api/funcionarios/<int:id>` — edita funcionário
- `DELETE /api/funcionarios/<int:id>` — deleta funcionário (retorna 204)

**Controle de acesso (chamado pelo Node-RED):**
- `GET /api/acesso/<uid>` — verifica se o UID tem permissão
  - Retorna `{"autorizado": true, "nome": "João Silva", "cargo": "Analista"}` se encontrado e ativo
  - Retorna `{"autorizado": false, "motivo": "cartao_nao_cadastrado"}` se UID não existe
  - Retorna `{"autorizado": false, "motivo": "funcionario_inativo", "nome": "..."}` se inativo
- `POST /api/acesso/registrar` — registra log de acesso
  - Corpo: `{"uid_cartao": "...", "nome_funcionario": "...", "tipo": "entrada", "autorizado": true}`
  - Retorna `{"sucesso": true, "id": ...}`

**Logs:**
- `GET /api/logs` — retorna os últimos 100 logs de acesso, do mais recente para o mais antigo
- `GET /api/logs/<uid>` — retorna os últimos 50 logs de um funcionário específico

**Painel admin (HTML):**
- `GET /` — página principal com tabela de funcionários e últimos 10 logs
- `GET /cadastrar` — formulário de cadastro
- `POST /cadastrar` — processa cadastro e redireciona para `/`
- `GET /editar/<int:id>` — formulário de edição pré-preenchido
- `POST /editar/<int:id>` — processa edição e redireciona para `/`
- `POST /deletar/<int:id>` — deleta e redireciona para `/`

#### Templates HTML (sem framework CSS externo)

O visual deve ser simples, funcional e limpo — CSS inline ou arquivo `style.css` próprio. O professor valoriza funcionalidade, não estética avançada.

`base.html` — layout base com `<nav>` simples com links para Home e Cadastrar.

`index.html` — tabela de funcionários com colunas: Nome, UID do Cartão, Cargo, Status (Ativo/Inativo), Ações (Editar | Deletar). Abaixo, tabela dos últimos 10 logs com: Data/Hora, Funcionário, Tipo, Autorizado.

`cadastrar.html` e `editar.html` — formulário com campos: Nome, UID do Cartão, Cargo, Ativo (checkbox).

#### `requirements.txt`
```
flask
psycopg2-binary
python-dotenv
```

---

### 3. Fluxo Node-RED

Crie um arquivo `nodered/flow_acesso.json` com um fluxo Node-RED exportável que implemente:

**Flow principal — "Controle de Acesso":**

1. **Nó MQTT in** — tópico: `catraca/acesso`, formato JSON esperado:
   ```json
   {"uid": "E7 45 D6 19", "tipo": "entrada"}
   ```

2. **Nó function** — prepara a URL para consulta:
   ```javascript
   msg.url = "http://localhost:5000/api/acesso/" + msg.payload.uid.replace(/ /g, "%20");
   msg.uid_original = msg.payload.uid;
   msg.tipo = msg.payload.tipo;
   return msg;
   ```

3. **Nó HTTP request** — GET para a URL preparada, retorno como objeto JSON

4. **Nó function** — processa resposta e prepara registro de log:
   ```javascript
   // Prepara payload de resposta para o ESP32
   msg.resposta_esp = {
     autorizado: msg.payload.autorizado,
     nome: msg.payload.nome || "Desconhecido",
     motivo: msg.payload.motivo || ""
   };
   // Prepara registro no banco
   msg.registro = {
     uid_cartao: msg.uid_original,
     nome_funcionario: msg.payload.nome || "Desconhecido",
     tipo: msg.tipo,
     autorizado: msg.payload.autorizado
   };
   return msg;
   ```

5. **Nó MQTT out** — tópico: `catraca/resposta`, publica `msg.resposta_esp`

6. **Nó HTTP request** — POST para `http://localhost:5000/api/acesso/registrar` com `msg.registro` como corpo

**Observação:** O JSON do flow deve ser válido e importável diretamente no Node-RED via Menu > Import > Clipboard.

---

### 4. README.md

Crie um README com:
- Descrição do projeto
- Requisitos (Python 3.10+, PostgreSQL 14+ com TimescaleDB, Node-RED 3+, Mosquitto)
- Instruções de instalação passo a passo:
  1. Criar banco de dados e executar `schema.sql` no Beekeeper Studio
  2. Criar `.env` com as variáveis de configuração
  3. Instalar dependências Python
  4. Rodar o Flask
  5. Importar o flow no Node-RED
- Exemplos de payload MQTT para testar

---

## Observações importantes

- Usar `psycopg2` para conexão com o banco — **não usar ORM** (o professor quer SQL direto, como foi ensinado em aula)
- Todas as queries devem usar **parâmetros parametrizados** (`%s`) para evitar SQL injection
- Usar `connection.commit()` após INSERT/UPDATE/DELETE e fechar cursor com `finally`
- Os endpoints JSON devem retornar `Content-Type: application/json` sempre
- O painel HTML deve funcionar mesmo sem JavaScript (apenas HTML puro + CSS)
- Comentários no código em **português**, já que é um projeto acadêmico brasileiro
- O UID do cartão RFID vem no formato `"E7 45 D6 19"` (bytes separados por espaço, maiúsculas) — normalizar para esse formato ao salvar e ao consultar
