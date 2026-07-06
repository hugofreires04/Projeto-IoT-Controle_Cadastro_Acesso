"""routes/auth_routes.py — Autenticação: login, logout e dados do usuário logado.

As senhas nunca são guardadas em texto puro: o banco armazena apenas o hash
bcrypt (com salt embutido), e o login compara via bcrypt.checkpw. O token de
sessão é um UUID gerado pelo próprio PostgreSQL (gen_random_uuid) e expira
após DURACAO_SESSAO_HORAS.
"""

import bcrypt
from flask import Blueprint, jsonify, request

from auth import requer_login
from db import get_cursor

bp = Blueprint("auth_routes", __name__, url_prefix="/api")

DURACAO_SESSAO_HORAS = 8


@bp.route("/login", methods=["POST"])
def login():
    """Confere e-mail/senha e cria uma sessão; devolve token, nível e nome.

    A mensagem de erro é a mesma para "e-mail não existe" e "senha errada",
    para não revelar quais e-mails estão cadastrados (boa prática de segurança).
    """
    dados = request.get_json(force=True) or {}
    email = dados.get("email", "").strip().lower()
    senha = dados.get("senha", "")

    with get_cursor(commit=True) as cur:
        cur.execute("SELECT * FROM a3_usuarios WHERE email = %s", (email,))
        usuario = cur.fetchone()

        if usuario is None or not bcrypt.checkpw(senha.encode(), usuario["senha_hash"].encode()):
            return jsonify({"erro": "Credenciais inválidas"}), 401

        cur.execute(
            f"""INSERT INTO a3_sessoes (id_usuario, nivel_acesso, expira_em)
               VALUES (%s, %s, NOW() + INTERVAL '{DURACAO_SESSAO_HORAS} hours')
               RETURNING token""",
            (usuario["id"], usuario["nivel_acesso"])
        )
        token = cur.fetchone()["token"]

    return jsonify({
        "token": str(token),
        "nivel": usuario["nivel_acesso"],
        "nome": usuario["nome"],
    })


@bp.route("/logout", methods=["POST"])
@requer_login
def logout():
    """Revoga a sessão atual apagando o token do banco (o localStorage é limpo no frontend)."""
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM a3_sessoes WHERE token = %s", (request.token,))
    return "", 200


@bp.route("/me", methods=["GET"])
@requer_login
def me():
    """Dados do usuário logado — usado pelo login.html para validar sessões salvas."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, nome, email, nivel_acesso, id_funcionario FROM a3_usuarios WHERE id = %s",
            (request.usuario["id_usuario"],)
        )
        usuario = cur.fetchone()

    if usuario is None:
        return jsonify({"erro": "Não autorizado"}), 401

    return jsonify(dict(usuario))
