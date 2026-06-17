"""Página de cadastro acessada via QR Code gerado no fluxo MQTT de cadastro."""

from flask import Blueprint, send_from_directory

bp = Blueprint("cadastro", __name__)


@bp.route("/cadastro", methods=["GET"])
def tela_cadastro():
    return send_from_directory("static", "cadastro.html")
