"""API REST — Funcionários (CRUD)."""

from flask import Blueprint, jsonify, request

from db import get_cursor, normalizar_uid

bp = Blueprint("api_funcionarios", __name__, url_prefix="/api/funcionarios")


@bp.route("", methods=["GET"])
def listar_funcionarios():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM funcionarios ORDER BY nome ASC")
        rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/<int:id>", methods=["GET"])
def buscar_funcionario(id):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM funcionarios WHERE id = %s", (id,))
        row = cur.fetchone()

    if row is None:
        return jsonify({"erro": "funcionario_nao_encontrado"}), 404
    return jsonify(dict(row))


@bp.route("", methods=["POST"])
def cadastrar_funcionario_api():
    dados = request.get_json(force=True)
    nome       = dados.get("nome", "").strip()
    uid_cartao = normalizar_uid(dados.get("uid_cartao", ""))
    cargo      = dados.get("cargo", "").strip()
    ativo      = bool(dados.get("ativo", True))

    if not nome or not uid_cartao:
        return jsonify({"erro": "nome e uid_cartao sao obrigatorios"}), 400

    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO funcionarios (nome, uid_cartao, cargo, ativo)
               VALUES (%s, %s, %s, %s)
               RETURNING id""",
            (nome, uid_cartao, cargo, ativo)
        )
        novo_id = cur.fetchone()["id"]

    return jsonify({"sucesso": True, "id": novo_id}), 201


@bp.route("/<int:id>", methods=["PUT"])
def editar_funcionario_api(id):
    dados = request.get_json(force=True)

    with get_cursor(commit=True) as cur:
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

    return jsonify({"sucesso": True})


@bp.route("/<int:id>", methods=["DELETE"])
def deletar_funcionario_api(id):
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM funcionarios WHERE id = %s", (id,))
    return "", 204
