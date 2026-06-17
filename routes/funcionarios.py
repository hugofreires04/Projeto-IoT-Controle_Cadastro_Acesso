"""Funcionários — cadastro manual (pelo admin) e áreas."""

import bcrypt
from flask import Blueprint, jsonify, request

from auth import requer_admin, requer_login
from db import get_cursor, normalizar_uid

bp = Blueprint("funcionarios", __name__, url_prefix="/api")


def _email_padrao(nome: str) -> str:
    return nome.strip().lower().replace(" ", "") + "@sistema.com"


@bp.route("/funcionarios", methods=["POST"])
@requer_login
@requer_admin
def cadastrar_funcionario():
    dados = request.get_json(force=True) or {}
    uid = normalizar_uid(dados.get("uid", ""))
    nome = dados.get("nome", "").strip()
    cargo = dados.get("cargo", "").strip()
    nivel_acesso = dados.get("nivel_acesso")
    areas = dados.get("areas", [])

    if not uid or not nome:
        return jsonify({"erro": "uid e nome são obrigatórios"}), 400

    with get_cursor(commit=True) as cur:
        cur.execute("SELECT 1 FROM cartoes_rfid WHERE uid = %s", (uid,))
        if cur.fetchone() is not None:
            return jsonify({"erro": "UID já cadastrado"}), 409

        cur.execute(
            """INSERT INTO funcionarios (nome, cargo, ativo)
               VALUES (%s, %s, true) RETURNING id""",
            (nome, cargo)
        )
        id_funcionario = cur.fetchone()["id"]

        cur.execute(
            """INSERT INTO cartoes_rfid (uid, id_funcionario, ativo)
               VALUES (%s, %s, true) RETURNING id""",
            (uid, id_funcionario)
        )
        id_cartao = cur.fetchone()["id"]

        for id_area in areas:
            cur.execute(
                "INSERT INTO permissoes (id_cartao, id_area) VALUES (%s, %s)",
                (id_cartao, id_area)
            )

        senha_gerada = None
        if nivel_acesso:
            email = _email_padrao(nome)
            senha_gerada = uid.replace(" ", "")[:8]
            senha_hash = bcrypt.hashpw(senha_gerada.encode(), bcrypt.gensalt()).decode()
            cur.execute(
                """INSERT INTO usuarios (nome, email, senha_hash, nivel_acesso, id_funcionario)
                   VALUES (%s, %s, %s, %s, %s)""",
                (nome, email, senha_hash, nivel_acesso, id_funcionario)
            )

        cur.execute("SELECT * FROM funcionarios WHERE id = %s", (id_funcionario,))
        funcionario = dict(cur.fetchone())

    funcionario["uid"] = uid
    funcionario["areas"] = areas
    if senha_gerada:
        funcionario["usuario_criado"] = {"senha_inicial": senha_gerada}

    return jsonify(funcionario), 201


@bp.route("/funcionarios", methods=["GET"])
@requer_login
@requer_admin
def listar_funcionarios():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM funcionarios ORDER BY nome ASC")
        funcionarios = [dict(f) for f in cur.fetchall()]

        for funcionario in funcionarios:
            cur.execute(
                "SELECT id, uid, ativo FROM cartoes_rfid WHERE id_funcionario = %s",
                (funcionario["id"],)
            )
            cartoes = [dict(c) for c in cur.fetchall()]

            for cartao in cartoes:
                cur.execute(
                    """SELECT a.id, a.nome FROM permissoes p
                       JOIN areas a ON a.id = p.id_area
                       WHERE p.id_cartao = %s""",
                    (cartao["id"],)
                )
                cartao["areas"] = [dict(a) for a in cur.fetchall()]

            funcionario["cartoes"] = cartoes

    return jsonify(funcionarios)


@bp.route("/funcionarios/<int:id_funcionario>/cartoes/<int:id_cartao>", methods=["PUT"])
@requer_login
@requer_admin
def alterar_status_cartao(id_funcionario, id_cartao):
    dados = request.get_json(force=True) or {}
    ativo = bool(dados.get("ativo", True))

    with get_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE cartoes_rfid SET ativo = %s WHERE id = %s AND id_funcionario = %s",
            (ativo, id_cartao, id_funcionario)
        )
        if cur.rowcount == 0:
            return jsonify({"erro": "Cartão não encontrado"}), 404

    return jsonify({"sucesso": True})


@bp.route("/areas", methods=["GET"])
@requer_login
def listar_areas():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM areas ORDER BY nome ASC")
        areas = cur.fetchall()
    return jsonify([dict(a) for a in areas])
