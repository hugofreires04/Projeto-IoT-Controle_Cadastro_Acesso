"""Cadastro de lugares (áreas), usuários do sistema e fila de UIDs pendentes — CRUD pelo admin."""

import bcrypt
from flask import Blueprint, jsonify, request

from auth import requer_admin, requer_login
from db import get_cursor, normalizar_uid

bp = Blueprint("cadastros", __name__, url_prefix="/api")


# ── Áreas / lugares ───────────────────────────────────────────────────────

@bp.route("/areas", methods=["GET"])
@requer_login
def listar_areas():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM a3_areas ORDER BY nome ASC")
        areas = cur.fetchall()
    return jsonify([dict(a) for a in areas])


@bp.route("/areas", methods=["POST"])
@requer_login
@requer_admin
def criar_area():
    dados = request.get_json(force=True) or {}
    nome = dados.get("nome", "").strip()
    descricao = dados.get("descricao", "").strip()

    if not nome:
        return jsonify({"erro": "nome é obrigatório"}), 400

    with get_cursor(commit=True) as cur:
        cur.execute("SELECT 1 FROM a3_areas WHERE nome = %s", (nome,))
        if cur.fetchone() is not None:
            return jsonify({"erro": "Já existe um lugar com esse nome"}), 409

        cur.execute(
            "INSERT INTO a3_areas (nome, descricao) VALUES (%s, %s) RETURNING *",
            (nome, descricao or None)
        )
        area = dict(cur.fetchone())

    return jsonify(area), 201


@bp.route("/areas/<int:id_area>", methods=["PUT"])
@requer_login
@requer_admin
def editar_area(id_area):
    dados = request.get_json(force=True) or {}
    nome = dados.get("nome", "").strip()
    descricao = dados.get("descricao", "").strip()

    if not nome:
        return jsonify({"erro": "nome é obrigatório"}), 400

    with get_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE a3_areas SET nome = %s, descricao = %s WHERE id = %s",
            (nome, descricao or None, id_area)
        )
        if cur.rowcount == 0:
            return jsonify({"erro": "Lugar não encontrado"}), 404

    return jsonify({"sucesso": True})


@bp.route("/areas/<int:id_area>", methods=["DELETE"])
@requer_login
@requer_admin
def remover_area(id_area):
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM a3_areas WHERE id = %s", (id_area,))
        if cur.rowcount == 0:
            return jsonify({"erro": "Lugar não encontrado"}), 404

    return jsonify({"sucesso": True})


# ── Usuários do sistema (login no painel) ─────────────────────────────────

@bp.route("/usuarios", methods=["GET"])
@requer_login
@requer_admin
def listar_usuarios():
    with get_cursor() as cur:
        cur.execute(
            """SELECT u.id, u.nome, u.email, u.nivel_acesso, u.id_funcionario,
                      f.nome AS funcionario_nome, u.criado_em
               FROM a3_usuarios u
               LEFT JOIN a3_funcionarios f ON f.id = u.id_funcionario
               ORDER BY u.nome ASC"""
        )
        usuarios = cur.fetchall()

    resultado = []
    for u in usuarios:
        u = dict(u)
        u["criado_em"] = u["criado_em"].isoformat()
        resultado.append(u)

    return jsonify(resultado)


@bp.route("/usuarios", methods=["POST"])
@requer_login
@requer_admin
def criar_usuario():
    dados = request.get_json(force=True) or {}
    nome = dados.get("nome", "").strip()
    email = dados.get("email", "").strip().lower()
    senha = dados.get("senha", "")
    nivel_acesso = dados.get("nivel_acesso", "")
    id_funcionario = dados.get("id_funcionario") or None

    if not nome or not email or not senha or nivel_acesso not in ("admin", "operador"):
        return jsonify({"erro": "nome, email, senha e nivel_acesso (admin/operador) são obrigatórios"}), 400

    senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()

    with get_cursor(commit=True) as cur:
        cur.execute("SELECT 1 FROM a3_usuarios WHERE email = %s", (email,))
        if cur.fetchone() is not None:
            return jsonify({"erro": "Já existe um usuário com esse e-mail"}), 409

        cur.execute(
            """INSERT INTO a3_usuarios (nome, email, senha_hash, nivel_acesso, id_funcionario)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING id, nome, email, nivel_acesso, id_funcionario, criado_em""",
            (nome, email, senha_hash, nivel_acesso, id_funcionario)
        )
        usuario = dict(cur.fetchone())

    usuario["criado_em"] = usuario["criado_em"].isoformat()
    return jsonify(usuario), 201


@bp.route("/usuarios/<int:id_usuario>", methods=["PUT"])
@requer_login
@requer_admin
def editar_usuario(id_usuario):
    dados = request.get_json(force=True) or {}
    nivel_acesso = dados.get("nivel_acesso")
    senha = dados.get("senha")

    campos = []
    params = []
    if nivel_acesso:
        if nivel_acesso not in ("admin", "operador"):
            return jsonify({"erro": "nivel_acesso inválido"}), 400
        campos.append("nivel_acesso = %s")
        params.append(nivel_acesso)
    if senha:
        campos.append("senha_hash = %s")
        params.append(bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode())

    if not campos:
        return jsonify({"erro": "Nada para atualizar"}), 400

    params.append(id_usuario)

    with get_cursor(commit=True) as cur:
        cur.execute(f"UPDATE a3_usuarios SET {', '.join(campos)} WHERE id = %s", params)
        if cur.rowcount == 0:
            return jsonify({"erro": "Usuário não encontrado"}), 404

    return jsonify({"sucesso": True})


@bp.route("/usuarios/<int:id_usuario>", methods=["DELETE"])
@requer_login
@requer_admin
def remover_usuario(id_usuario):
    if id_usuario == request.usuario["id_usuario"]:
        return jsonify({"erro": "Não é possível remover o próprio usuário"}), 400

    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM a3_usuarios WHERE id = %s", (id_usuario,))
        if cur.rowcount == 0:
            return jsonify({"erro": "Usuário não encontrado"}), 404

    return jsonify({"sucesso": True})


# ── UIDs pendentes de cadastro (lidos pela catraca em modo admin) ─────────

@bp.route("/cadastros/uid-pendente", methods=["POST"])
def receber_uid_pendente():
    """Chamado pelo Node-RED ao receber uma leitura no tópico MQTT a3/cadastros.

    Sem @requer_login: é uma chamada máquina-a-máquina do Node-RED, no mesmo
    padrão de /api/acesso/log e /api/acesso/<uid>.
    """
    dados = request.get_json(force=True) or {}
    uid = normalizar_uid(dados.get("uid", ""))
    if not uid:
        return jsonify({"erro": "uid é obrigatório"}), 400

    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO a3_uids_pendentes (uid) VALUES (%s) RETURNING id, uid, recebido_em",
            (uid,)
        )
        pendente = dict(cur.fetchone())

    pendente["recebido_em"] = pendente["recebido_em"].isoformat()
    return jsonify(pendente), 201


@bp.route("/cadastros/uid-pendente", methods=["GET"])
@requer_login
@requer_admin
def consultar_uid_pendente():
    """Retorna o UID mais recente ainda não usado/descartado (ou null), para a aba Cadastrar."""
    with get_cursor() as cur:
        cur.execute("SELECT id, uid, recebido_em FROM a3_uids_pendentes ORDER BY recebido_em DESC LIMIT 1")
        pendente = cur.fetchone()

    if pendente is None:
        return jsonify(None)

    pendente = dict(pendente)
    pendente["recebido_em"] = pendente["recebido_em"].isoformat()
    return jsonify(pendente)


@bp.route("/cadastros/uid-pendente/<int:id_pendente>", methods=["DELETE"])
@requer_login
@requer_admin
def descartar_uid_pendente(id_pendente):
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM a3_uids_pendentes WHERE id = %s", (id_pendente,))
        if cur.rowcount == 0:
            return jsonify({"erro": "UID pendente não encontrado"}), 404

    return jsonify({"sucesso": True})
