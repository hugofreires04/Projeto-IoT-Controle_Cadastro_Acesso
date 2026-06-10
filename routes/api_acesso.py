"""API REST — Controle de acesso e logs (chamado pelo Node-RED / Grafana)."""

from flask import Blueprint, jsonify, request

from db import get_cursor, normalizar_uid

bp = Blueprint("api_acesso", __name__, url_prefix="/api")


@bp.route("/acesso/<uid>", methods=["GET"])
def verificar_acesso(uid):
    uid = normalizar_uid(uid)

    with get_cursor() as cur:
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


@bp.route("/acesso/log", methods=["POST"])
def registrar_acesso():
    dados            = request.get_json(force=True)
    uid_cartao       = normalizar_uid(dados.get("uid_cartao", ""))
    nome_funcionario = dados.get("nome_funcionario", "Desconhecido")
    tipo             = dados.get("tipo", "entrada")
    autorizado       = bool(dados.get("autorizado", False))

    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO logs_acesso (uid_cartao, nome_funcionario, tipo, autorizado)
               VALUES (%s, %s, %s, %s)
               RETURNING data_hora""",
            (uid_cartao, nome_funcionario, tipo, autorizado)
        )
        data_hora = cur.fetchone()["data_hora"]

    return jsonify({"sucesso": True, "data_hora": str(data_hora)}), 201


@bp.route("/logs", methods=["GET"])
def listar_logs():
    with get_cursor() as cur:
        cur.execute(
            """SELECT * FROM logs_acesso
               ORDER BY data_hora DESC
               LIMIT 100"""
        )
        rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/logs/<uid>", methods=["GET"])
def logs_por_uid(uid):
    uid = normalizar_uid(uid)

    with get_cursor() as cur:
        cur.execute(
            """SELECT * FROM logs_acesso
               WHERE uid_cartao = %s
               ORDER BY data_hora DESC
               LIMIT 50""",
            (uid,)
        )
        rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/stats", methods=["GET"])
def estatisticas():
    """Retorna contagem de acessos agrupados por hora (para Grafana)."""
    with get_cursor() as cur:
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
