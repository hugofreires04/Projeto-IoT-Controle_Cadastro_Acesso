# Prompt — Fixes no Projeto Flask IoT

## Contexto

Projeto de controle de acesso via RFID (ENG4051 — PUC-Rio). Stack: Flask + PostgreSQL/TimescaleDB + Node-RED + MQTT (Mosquitto). O código já está funcionando estruturalmente, mas há bugs e melhorias a aplicar.

---

## Fix 1 — Rota ambígua no Flask (BUG CRÍTICO)

**Problema:** Em `app.py`, a rota `GET /api/acesso/<uid>` pode capturar o path `/api/acesso/registrar`, causando erro 500 quando o Node-RED faz o POST de registro, dependendo da ordem de resolução de rotas do Flask.

**Solução:** Renomear o endpoint de registro de `/api/acesso/registrar` para `/api/acesso/log` em dois lugares:

1. Em `app.py`, alterar o decorator da rota:
```python
# DE:
@app.route("/api/acesso/registrar", methods=["POST"])
def registrar_acesso():

# PARA:
@app.route("/api/acesso/log", methods=["POST"])
def registrar_acesso():
```

2. Em `nodered/flow_acesso.json`, atualizar a URL nos dois nós que referenciam `/api/acesso/registrar`:
- No nó `fn_prepara_registro`: trocar `"http://localhost:5000/api/acesso/registrar"` por `"http://localhost:5000/api/acesso/log"`
- No nó `http_registrar_log`: trocar a URL hardcoded `"http://localhost:5000/api/acesso/registrar"` por `"http://localhost:5000/api/acesso/log"`

3. Em `README.md`, atualizar a tabela de endpoints: trocar `POST /api/acesso/registrar` por `POST /api/acesso/log`.

---

## Fix 2 — Tratamento de UID duplicado no formulário HTML (BUG)

**Problema:** Se o usuário cadastrar um UID já existente via formulário HTML, o Flask lança `psycopg2.errors.UniqueViolation` e retorna erro 500 sem mensagem amigável.

**Solução:** Em `app.py`, na função `processar_cadastro()`, envolver o INSERT em try/except e usar `flash()` para feedback:

```python
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash

# Na função processar_cadastro():
@app.route("/cadastrar", methods=["POST"])
def processar_cadastro():
    nome       = request.form.get("nome", "").strip()
    uid_cartao = normalizar_uid(request.form.get("uid_cartao", ""))
    cargo      = request.form.get("cargo", "").strip()
    ativo      = request.form.get("ativo") == "on"

    if not nome or not uid_cartao:
        flash("Nome e UID do cartão são obrigatórios.", "erro")
        return redirect(url_for("tela_cadastrar"))

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO funcionarios (nome, uid_cartao, cargo, ativo)
               VALUES (%s, %s, %s, %s)""",
            (nome, uid_cartao, cargo, ativo)
        )
        conn.commit()
        flash(f"Funcionário '{nome}' cadastrado com sucesso!", "sucesso")
    except Exception as e:
        conn.rollback()
        if "unique" in str(e).lower() or "uid_cartao" in str(e).lower():
            flash(f"Erro: UID '{uid_cartao}' já está cadastrado.", "erro")
        else:
            flash("Erro ao cadastrar funcionário. Tente novamente.", "erro")
    finally:
        conn.close()

    return redirect(url_for("index"))
```

Aplicar o mesmo padrão em `processar_edicao()` — envolver o UPDATE em try/except com flash de sucesso e erro.

---

## Fix 3 — Flash messages nos templates HTML

**Problema:** O painel não dá feedback visual após ações (cadastrar, editar, deletar).

**Solução:** Em `templates/base.html`, adicionar o bloco de flash messages logo após a tag `<main>`:

```html
<main>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for categoria, mensagem in messages %}
                <div class="flash flash-{{ categoria }}">{{ mensagem }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}

    {% block conteudo %}{% endblock %}
</main>
```

Em `static/style.css`, adicionar o estilo das flash messages:

```css
/* ── Flash messages ────────────────────────────────────────── */

.flash {
    padding: 10px 16px;
    border-radius: 4px;
    margin-bottom: 20px;
    font-size: 14px;
}

.flash-sucesso {
    background: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
}

.flash-erro {
    background: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
}
```

Adicionar também flash de sucesso nas funções `processar_edicao()` e `deletar_funcionario()`:
```python
flash(f"Funcionário atualizado com sucesso!", "sucesso")
flash(f"Funcionário removido.", "sucesso")
```

---

## Fix 4 — Error handler no flow Node-RED (BUG CRÍTICO)

**Problema:** Se o Flask estiver offline quando chegar um evento MQTT, o nó HTTP request falha silenciosamente — o ESP32 nunca recebe resposta e a catraca fica travada.

**Solução:** Adicionar em `nodered/flow_acesso.json` os seguintes nós ao array existente:

```json
{
  "id": "catch_flask_offline",
  "type": "catch",
  "z": "tab_controle_acesso",
  "name": "Erro: Flask offline",
  "scope": ["http_consulta_flask", "http_registrar_log"],
  "uncaught": false,
  "x": 580,
  "y": 220,
  "wires": [["fn_resposta_erro"]]
},
{
  "id": "fn_resposta_erro",
  "type": "function",
  "z": "tab_controle_acesso",
  "name": "Resposta de erro",
  "func": "msg.payload = {\n    autorizado: false,\n    nome: \"Desconhecido\",\n    motivo: \"servidor_offline\"\n};\nreturn msg;",
  "outputs": 1,
  "noerr": 0,
  "x": 800,
  "y": 220,
  "wires": [["mqtt_out_erro"]]
},
{
  "id": "mqtt_out_erro",
  "type": "mqtt out",
  "z": "tab_controle_acesso",
  "name": "catraca/resposta (erro)",
  "topic": "catraca/resposta",
  "qos": "1",
  "retain": false,
  "broker": "broker_mosquitto",
  "x": 1020,
  "y": 220,
  "wires": []
}
```

---

## Fix 5 — Índice no banco para performance

**Problema:** O endpoint `GET /api/logs/<uid>` filtra por `uid_cartao` sem índice, causando full scan na hipertabela.

**Solução:** Adicionar ao final de `database/schema.sql`:

```sql
-- Índice para consultas de log por funcionário
CREATE INDEX IF NOT EXISTS idx_logs_uid_cartao ON logs_acesso (uid_cartao, data_hora DESC);
```

---

## Fix 6 — .gitignore e .env.example (BOAS PRÁTICAS)

**Criar arquivo `.gitignore` na raiz:**

```gitignore
# Variáveis de ambiente (NUNCA commitar)
.env

# Cache Python
__pycache__/
*.pyc
*.pyo
*.pyd

# Ambientes virtuais
venv/
.venv/
env/

# IDEs
.vscode/
.idea/

# Arquivos de sistema
.DS_Store
Thumbs.db
```

**Criar arquivo `.env.example` na raiz:**

```env
# Copie este arquivo para .env e preencha com seus valores reais
# cp .env.example .env

DATABASE_URL=postgresql://SEU_USUARIO:SUA_SENHA@localhost:5432/acesso_rfid
SECRET_KEY=troque-por-uma-chave-longa-e-aleatoria
MQTT_BROKER=localhost
MQTT_PORT=1883
```

---

## Fix 7 — Endpoint /api/stats com time_bucket (MELHORIA — "ir além")

**Adicionar em `app.py`** um endpoint que usa o `time_bucket` do TimescaleDB para agregar acessos por hora — demonstra domínio do conteúdo da Teoria 05:

```python
@app.route("/api/stats", methods=["GET"])
def estatisticas():
    """Retorna contagem de acessos agrupados por hora (para Grafana)."""
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT
                time_bucket('1 hour', data_hora) AS time,
                COUNT(*) AS total,
                SUM(CASE WHEN tipo = 'entrada' THEN 1 ELSE 0 END) AS entradas,
                SUM(CASE WHEN tipo = 'saida'   THEN 1 ELSE 0 END) AS saidas,
                SUM(CASE WHEN autorizado = TRUE THEN 1 ELSE 0 END) AS autorizados,
                SUM(CASE WHEN autorizado = FALSE THEN 1 ELSE 0 END) AS negados
               FROM logs_acesso
               WHERE data_hora >= now() - INTERVAL '24 hours'
               GROUP BY time
               ORDER BY time ASC"""
        )
        rows = cur.fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()
```

Adicionar também na tabela de endpoints do `README.md`:
```
| GET | `/api/stats` | Acessos agrupados por hora nas últimas 24h (para Grafana) |
```

---

## Resumo das alterações

| Arquivo | O que muda |
|---|---|
| `app.py` | Renomeia rota `/registrar` → `/log`; adiciona try/except com flash em cadastro e edição; adiciona endpoint `/api/stats` |
| `nodered/flow_acesso.json` | Atualiza URLs para `/api/acesso/log`; adiciona nós `catch`, `fn_resposta_erro`, `mqtt_out_erro` |
| `database/schema.sql` | Adiciona `CREATE INDEX` para `uid_cartao` |
| `templates/base.html` | Adiciona bloco de flash messages |
| `static/style.css` | Adiciona estilos `.flash`, `.flash-sucesso`, `.flash-erro` |
| `.gitignore` | Criado do zero |
| `.env.example` | Criado do zero |
| `README.md` | Atualiza endpoint `/registrar` → `/log`; adiciona `/api/stats` na tabela |
