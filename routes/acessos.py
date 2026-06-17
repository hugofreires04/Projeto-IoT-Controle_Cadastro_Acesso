"""Lista de acessos (com filtros/paginação/CSV) + endpoints legados da catraca.

Os endpoints GET /api/acesso/<uid> e POST /api/acesso/log são consumidos pelo
fluxo Node-RED já existente (nodered/flow_acesso.json) — o contrato JSON é
mantido igual ao da Task 1 para não exigir mudanças no Node-RED/ESP32, mas
agora gravam em a3_registros_acesso (resultado) em vez de a3_logs_acesso (autorizado).
"""

import csv
import io
from datetime import date

from flask import Blueprint, Response, jsonify, request

from auth import requer_login
from db import get_cursor, normalizar_uid

bp = Blueprint("acessos", __name__, url_prefix="/api")

RESULTADOS_VALIDOS = (
    "liberado",
    "negado_sem_permissao",
    "negado_inativo",
    "negado_desconhecido",
)


def _classificar_uid(uid):
    """Verifica o estado atual de um cartão e retorna (resultado, id_funcionario, nome, cargo)."""
    with get_cursor() as cur:
        cur.execute(
            """SELECT c.ativo AS cartao_ativo, f.id AS id_funcionario, f.nome, f.cargo,
                      f.ativo AS funcionario_ativo
               FROM a3_cartoes_rfid c
               LEFT JOIN a3_funcionarios f ON f.id = c.id_funcionario
               WHERE c.uid = %s""",
            (uid,)
        )
        cartao = cur.fetchone()

    if cartao is None:
        return "negado_desconhecido", None, None, None
    if not cartao["cartao_ativo"] or not cartao["funcionario_ativo"]:
        return "negado_inativo", cartao["id_funcionario"], cartao["nome"], cartao["cargo"]
    return "liberado", cartao["id_funcionario"], cartao["nome"], cartao["cargo"]


@bp.route("/acesso/<uid>", methods=["GET"])
def verificar_acesso(uid):
    """Consultado pelo Node-RED a cada leitura de cartão na catraca."""
    uid = normalizar_uid(uid)
    resultado, _, nome, cargo = _classificar_uid(uid)
    autorizado = resultado == "liberado"

    return jsonify({
        "autorizado": autorizado,
        "nome": nome or "Desconhecido",
        "cargo": cargo,
        "motivo": "" if autorizado else resultado,
    })


@bp.route("/acesso/log", methods=["POST"])
def registrar_acesso():
    """Registra o resultado de uma leitura, chamado pelo Node-RED após a verificação."""
    dados = request.get_json(force=True) or {}
    uid = normalizar_uid(dados.get("uid_cartao", ""))

    resultado, id_funcionario, _, _ = _classificar_uid(uid)

    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO a3_registros_acesso (uid, id_funcionario, resultado)
               VALUES (%s, %s, %s)
               RETURNING id, data_hora""",
            (uid, id_funcionario, resultado)
        )
        registro = cur.fetchone()

    return jsonify({"sucesso": True, "id": registro["id"], "data_hora": registro["data_hora"].isoformat()}), 201


def _montar_filtros():
    """Lê os query params e monta a cláusula WHERE + parâmetros, aplicando a regra de operador."""
    condicoes = ["1=1"]
    params = []

    if request.usuario["nivel_acesso"] == "operador":
        with get_cursor() as cur:
            cur.execute("SELECT id_funcionario FROM a3_usuarios WHERE id = %s", (request.usuario["id_usuario"],))
            linha = cur.fetchone()
        condicoes.append("r.id_funcionario = %s")
        params.append(linha["id_funcionario"] if linha else None)
    else:
        funcionario_id = request.args.get("funcionario_id")
        if funcionario_id:
            condicoes.append("r.id_funcionario = %s")
            params.append(funcionario_id)

    area_id = request.args.get("area_id")
    if area_id:
        condicoes.append("r.id_area = %s")
        params.append(area_id)

    resultado = request.args.get("resultado")
    if resultado in RESULTADOS_VALIDOS:
        condicoes.append("r.resultado = %s")
        params.append(resultado)

    data_inicio = request.args.get("data_inicio")
    if data_inicio:
        condicoes.append("r.data_hora >= %s")
        params.append(data_inicio)

    data_fim = request.args.get("data_fim")
    if data_fim:
        condicoes.append("r.data_hora <= %s")
        params.append(data_fim)

    return " AND ".join(condicoes), params


_SELECT_BASE = """
    SELECT r.id, r.uid, f.nome AS funcionario, f.cargo, a.nome AS area, r.resultado, r.data_hora
    FROM a3_registros_acesso r
    LEFT JOIN a3_funcionarios f ON f.id = r.id_funcionario
    LEFT JOIN a3_areas a ON a.id = r.id_area
"""


@bp.route("/acessos", methods=["GET"])
@requer_login
def listar_acessos():
    where, params = _montar_filtros()

    page = max(int(request.args.get("page", 1)), 1)
    limit = max(int(request.args.get("limit", 20)), 1)
    offset = (page - 1) * limit

    with get_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM a3_registros_acesso r WHERE {where}", params)
        total = cur.fetchone()["total"]

        cur.execute(
            f"""SELECT r.resultado, COUNT(*) AS total FROM a3_registros_acesso r
                WHERE {where} GROUP BY r.resultado""",
            params
        )
        contagem_por_resultado = {linha["resultado"]: linha["total"] for linha in cur.fetchall()}

        cur.execute(
            f"{_SELECT_BASE} WHERE {where} ORDER BY r.data_hora DESC LIMIT %s OFFSET %s",
            params + [limit, offset]
        )
        registros = cur.fetchall()

    paginas = max((total + limit - 1) // limit, 1)

    return jsonify({
        "registros": [
            {
                "id": r["id"],
                "uid": r["uid"],
                "funcionario": r["funcionario"],
                "cargo": r["cargo"],
                "area": r["area"],
                "resultado": r["resultado"],
                "data_hora": r["data_hora"].isoformat(),
            }
            for r in registros
        ],
        "total": total,
        "pagina": page,
        "paginas": paginas,
        "totais": {
            "liberados": contagem_por_resultado.get("liberado", 0),
            "negados": (
                contagem_por_resultado.get("negado_sem_permissao", 0)
                + contagem_por_resultado.get("negado_inativo", 0)
            ),
            "desconhecidos": contagem_por_resultado.get("negado_desconhecido", 0),
        },
    })


@bp.route("/acessos/exportar", methods=["GET"])
@requer_login
def exportar_acessos():
    where, params = _montar_filtros()

    with get_cursor() as cur:
        cur.execute(f"{_SELECT_BASE} WHERE {where} ORDER BY r.data_hora DESC", params)
        registros = cur.fetchall()

    saida = io.StringIO()
    writer = csv.writer(saida)
    writer.writerow(["ID", "UID", "Funcionário", "Cargo", "Área", "Resultado", "Data/Hora"])
    for r in registros:
        writer.writerow([
            r["id"], r["uid"], r["funcionario"] or "", r["cargo"] or "",
            r["area"] or "", r["resultado"], r["data_hora"].isoformat(),
        ])

    nome_arquivo = f"acessos_{date.today().isoformat()}.csv"
    return Response(
        saida.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'}
    )
