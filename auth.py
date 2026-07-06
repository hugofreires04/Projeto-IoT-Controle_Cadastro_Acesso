"""auth.py — Decorators de autenticação manual via tabela a3_sessoes.

A autenticação foi implementada "na mão" (sem Flask-Login/JWT) de propósito,
para o funcionamento ficar explícito e didático:

  - O login cria uma linha em a3_sessoes com um token UUID e uma expiração.
  - O frontend manda esse token em toda chamada: "Authorization: Bearer <token>".
  - @requer_login valida o token no banco a cada requisição e anexa os dados
    do usuário em request.usuario para a rota usar.
  - @requer_admin (usado DEPOIS de @requer_login) barra quem não é admin.

Revogar uma sessão = deletar a linha da tabela (é o que o logout faz).
"""

from functools import wraps

from flask import jsonify, request

from db import get_cursor


def requer_login(rota):
    """Exige um token de sessão válido; injeta request.usuario e request.token."""
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
    """Restringe a rota ao nível admin (403 para operadores).

    Deve vir depois de @requer_login, que é quem preenche request.usuario.
    """
    @wraps(rota)
    def decorada(*args, **kwargs):
        if request.usuario["nivel_acesso"] != "admin":
            return jsonify({"erro": "Acesso negado"}), 403
        return rota(*args, **kwargs)

    return decorada
