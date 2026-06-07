from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
import psycopg2
import psycopg2.extras
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY


# ── Conexão com o banco ──────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(config.DATABASE_URL)


# ── Utilitário: normaliza UID para formato "XX XX XX XX" maiúsculo ───────────

def normalizar_uid(uid: str) -> str:
    uid = uid.strip().upper()
    # aceita tanto "E745D619" quanto "E7 45 D6 19"
    partes = uid.split()
    if len(partes) == 1 and len(uid) % 2 == 0:
        partes = [uid[i:i+2] for i in range(0, len(uid), 2)]
    return " ".join(partes)


# ════════════════════════════════════════════════════════════════════════════
# API REST — Funcionários
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/funcionarios", methods=["GET"])
def listar_funcionarios():
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM funcionarios ORDER BY nome ASC")
        rows = cur.fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/api/funcionarios/<int:id>", methods=["GET"])
def buscar_funcionario(id):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM funcionarios WHERE id = %s", (id,))
        row = cur.fetchone()
        if row is None:
            return jsonify({"erro": "funcionario_nao_encontrado"}), 404
        return jsonify(dict(row))
    finally:
        conn.close()


@app.route("/api/funcionarios", methods=["POST"])
def cadastrar_funcionario_api():
    dados = request.get_json(force=True)
    nome       = dados.get("nome", "").strip()
    uid_cartao = normalizar_uid(dados.get("uid_cartao", ""))
    cargo      = dados.get("cargo", "").strip()
    ativo      = bool(dados.get("ativo", True))

    if not nome or not uid_cartao:
        return jsonify({"erro": "nome e uid_cartao sao obrigatorios"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO funcionarios (nome, uid_cartao, cargo, ativo)
               VALUES (%s, %s, %s, %s)
               RETURNING id""",
            (nome, uid_cartao, cargo, ativo)
        )
        novo_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"sucesso": True, "id": novo_id}), 201
    finally:
        conn.close()


@app.route("/api/funcionarios/<int:id>", methods=["PUT"])
def editar_funcionario_api(id):
    dados = request.get_json(force=True)
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM funcionarios WHERE id = %s", (id,))
        atual = cur.fetchone()
        if atual is None:
            return jsonify({"erro": "funcionario_nao_encontrado"}), 404

        nome       = dados.get("nome",       atual["nome"])
        uid_cartao = normalizar_uid(dados.get("uid_cartao", atual["uid_cartao"]))
        cargo      = dados.get("cargo",      atual["cargo"])
        ativo      = bool(dados.get("ativo", atual["ativo"]))

        cur.execute(
            """UPDATE funcionarios
               SET nome=%s, uid_cartao=%s, cargo=%s, ativo=%s, atualizado_em=now()
               WHERE id=%s""",
            (nome, uid_cartao, cargo, ativo, id)
        )
        conn.commit()
        return jsonify({"sucesso": True})
    finally:
        conn.close()


@app.route("/api/funcionarios/<int:id>", methods=["DELETE"])
def deletar_funcionario_api(id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM funcionarios WHERE id = %s", (id,))
        conn.commit()
        return "", 204
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════════
# API REST — Controle de acesso (chamado pelo Node-RED)
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/acesso/<uid>", methods=["GET"])
def verificar_acesso(uid):
    uid = normalizar_uid(uid)
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT nome, cargo, ativo FROM funcionarios WHERE uid_cartao = %s",
            (uid,)
        )
        func = cur.fetchone()

        if func is None:
            return jsonify({"autorizado": False, "motivo": "cartao_nao_cadastrado"})

        if not func["ativo"]:
            return jsonify({"autorizado": False, "motivo": "funcionario_inativo", "nome": func["nome"]})

        return jsonify({"autorizado": True, "nome": func["nome"], "cargo": func["cargo"]})
    finally:
        conn.close()


@app.route("/api/acesso/log", methods=["POST"])
def registrar_acesso():
    dados = request.get_json(force=True)
    uid_cartao       = normalizar_uid(dados.get("uid_cartao", ""))
    nome_funcionario = dados.get("nome_funcionario", "Desconhecido")
    tipo             = dados.get("tipo", "entrada")
    autorizado       = bool(dados.get("autorizado", False))

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO logs_acesso (uid_cartao, nome_funcionario, tipo, autorizado)
               VALUES (%s, %s, %s, %s)
               RETURNING data_hora""",
            (uid_cartao, nome_funcionario, tipo, autorizado)
        )
        data_hora = cur.fetchone()[0]
        conn.commit()
        return jsonify({"sucesso": True, "data_hora": str(data_hora)}), 201
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════════
# API REST — Logs
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/logs", methods=["GET"])
def listar_logs():
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT * FROM logs_acesso
               ORDER BY data_hora DESC
               LIMIT 100"""
        )
        rows = cur.fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/api/logs/<uid>", methods=["GET"])
def logs_por_uid(uid):
    uid = normalizar_uid(uid)
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT * FROM logs_acesso
               WHERE uid_cartao = %s
               ORDER BY data_hora DESC
               LIMIT 50""",
            (uid,)
        )
        rows = cur.fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


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


# ════════════════════════════════════════════════════════════════════════════
# Painel Admin — HTML
# ════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM funcionarios ORDER BY nome ASC")
        funcionarios = cur.fetchall()

        cur.execute(
            """SELECT * FROM logs_acesso
               ORDER BY data_hora DESC
               LIMIT 10"""
        )
        logs = cur.fetchall()
        return render_template("index.html", funcionarios=funcionarios, logs=logs)
    finally:
        conn.close()


@app.route("/cadastrar", methods=["GET"])
def tela_cadastrar():
    return render_template("cadastrar.html")


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


@app.route("/editar/<int:id>", methods=["GET"])
def tela_editar(id):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM funcionarios WHERE id = %s", (id,))
        func = cur.fetchone()
        if func is None:
            return redirect(url_for("index"))
        return render_template("editar.html", func=func)
    finally:
        conn.close()


@app.route("/editar/<int:id>", methods=["POST"])
def processar_edicao(id):
    nome       = request.form.get("nome", "").strip()
    uid_cartao = normalizar_uid(request.form.get("uid_cartao", ""))
    cargo      = request.form.get("cargo", "").strip()
    ativo      = request.form.get("ativo") == "on"

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE funcionarios
               SET nome=%s, uid_cartao=%s, cargo=%s, ativo=%s, atualizado_em=now()
               WHERE id=%s""",
            (nome, uid_cartao, cargo, ativo, id)
        )
        conn.commit()
        flash(f"Funcionário atualizado com sucesso!", "sucesso")
    except Exception as e:
        conn.rollback()
        if "unique" in str(e).lower() or "uid_cartao" in str(e).lower():
            flash(f"Erro: UID '{uid_cartao}' já está cadastrado.", "erro")
        else:
            flash("Erro ao atualizar funcionário. Tente novamente.", "erro")
    finally:
        conn.close()

    return redirect(url_for("index"))


@app.route("/deletar/<int:id>", methods=["POST"])
def deletar_funcionario(id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM funcionarios WHERE id = %s", (id,))
        conn.commit()
        flash(f"Funcionário removido.", "sucesso")
    finally:
        conn.close()

    return redirect(url_for("index"))


# ── Ponto de entrada ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
