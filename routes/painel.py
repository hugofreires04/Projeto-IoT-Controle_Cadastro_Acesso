"""Painel Admin — páginas HTML de cadastro, edição e visualização."""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from db import get_cursor, normalizar_uid

bp = Blueprint("painel", __name__)


@bp.route("/")
def index():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM funcionarios ORDER BY nome ASC")
        funcionarios = cur.fetchall()

        cur.execute(
            """SELECT * FROM logs_acesso
               ORDER BY data_hora DESC
               LIMIT 10"""
        )
        logs = cur.fetchall()

    return render_template("index.html", funcionarios=funcionarios, logs=logs)


@bp.route("/cadastrar", methods=["GET"])
def tela_cadastrar():
    return render_template("cadastrar.html")


@bp.route("/cadastrar", methods=["POST"])
def processar_cadastro():
    nome       = request.form.get("nome", "").strip()
    uid_cartao = normalizar_uid(request.form.get("uid_cartao", ""))
    cargo      = request.form.get("cargo", "").strip()
    ativo      = request.form.get("ativo") == "on"

    if not nome or not uid_cartao:
        flash("Nome e UID do cartão são obrigatórios.", "erro")
        return redirect(url_for(".tela_cadastrar"))

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """INSERT INTO funcionarios (nome, uid_cartao, cargo, ativo)
                   VALUES (%s, %s, %s, %s)""",
                (nome, uid_cartao, cargo, ativo)
            )
        flash(f"Funcionário '{nome}' cadastrado com sucesso!", "sucesso")
    except Exception as e:
        if "unique" in str(e).lower() or "uid_cartao" in str(e).lower():
            flash(f"Erro: UID '{uid_cartao}' já está cadastrado.", "erro")
        else:
            flash("Erro ao cadastrar funcionário. Tente novamente.", "erro")

    return redirect(url_for(".index"))


@bp.route("/editar/<int:id>", methods=["GET"])
def tela_editar(id):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM funcionarios WHERE id = %s", (id,))
        func = cur.fetchone()

    if func is None:
        return redirect(url_for(".index"))
    return render_template("editar.html", func=func)


@bp.route("/editar/<int:id>", methods=["POST"])
def processar_edicao(id):
    nome       = request.form.get("nome", "").strip()
    uid_cartao = normalizar_uid(request.form.get("uid_cartao", ""))
    cargo      = request.form.get("cargo", "").strip()
    ativo      = request.form.get("ativo") == "on"

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """UPDATE funcionarios
                   SET nome=%s, uid_cartao=%s, cargo=%s, ativo=%s, atualizado_em=now()
                   WHERE id=%s""",
                (nome, uid_cartao, cargo, ativo, id)
            )
        flash("Funcionário atualizado com sucesso!", "sucesso")
    except Exception as e:
        if "unique" in str(e).lower() or "uid_cartao" in str(e).lower():
            flash(f"Erro: UID '{uid_cartao}' já está cadastrado.", "erro")
        else:
            flash("Erro ao atualizar funcionário. Tente novamente.", "erro")

    return redirect(url_for(".index"))


@bp.route("/deletar/<int:id>", methods=["POST"])
def deletar_funcionario(id):
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM funcionarios WHERE id = %s", (id,))

    flash("Funcionário removido.", "sucesso")
    return redirect(url_for(".index"))
