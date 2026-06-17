"""Decorators de autenticação manual via tabela a3_sessoes (sem Flask-Login/JWT)."""

from functools import wraps

from flask import jsonify, request

from db import get_cursor


def requer_login(rota):
    @wraps(rota)
    def decorada(*args, **kwargs):
        cabecalho = request.headers.get("Authorization", "")
        if not cabecalho.startswith("Bearer "):
            return jsonify({"erro": "Não autorizado"}), 401

        token = cabecalho[len("Bearer "):].strip()

        with get_cursor() as cur:
            cur.execute(
                """SELECT id_usuario, nivel_acesso FROM a3_sessoes
                   WHERE token = %s AND expira_em > NOW()""",
                (token,)
            )
            sessao = cur.fetchone()

        if sessao is None:
            return jsonify({"erro": "Não autorizado"}), 401

        request.usuario = {
            "id_usuario": sessao["id_usuario"],
            "nivel_acesso": sessao["nivel_acesso"],
        }
        request.token = token
        return rota(*args, **kwargs)

    return decorada


def requer_admin(rota):
    @wraps(rota)
    def decorada(*args, **kwargs):
        if request.usuario["nivel_acesso"] != "admin":
            return jsonify({"erro": "Acesso negado"}), 403
        return rota(*args, **kwargs)

    return decorada
