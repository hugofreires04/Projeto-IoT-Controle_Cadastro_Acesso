"""routes/acessos.py — Registros de acesso: consulta pelo painel + integração com a catraca.

Dois grupos de rotas convivem aqui:

  Consumidas pelo PAINEL WEB (exigem login):
    GET /api/acessos               → lista paginada com filtros e totalizadores
    GET /api/acessos/estatisticas  → resumo do dashboard (admin)
    GET /api/acessos/exportar      → mesmos filtros da lista, em CSV

  Consumidas pelo NODE-RED (máquina-a-máquina, sem login):
    GET  /api/acesso/<uid>  → decide se libera a catraca para o cartão lido
    POST /api/acesso/log    → grava o resultado da leitura em a3_registros_acesso

O contrato JSON das rotas do Node-RED é mantido igual ao da Task 1 para não
exigir mudanças no fluxo (nodered/flow_acesso.json) nem no firmware do ESP32.
"""

import csv
import io
from datetime import date, timedelta

from flask import Blueprint, Response, current_app, jsonify, request

from auth import requer_admin, requer_login
from db import get_cursor, normalizar_uid

bp = Blueprint("acessos", __name__, url_prefix="/api")

RESULTADOS_VALIDOS = (
    "liberado",
    "negado_sem_permissao",
    "negado_inativo",
    "negado_desconhecido",
)


def _classificar_uid(uid):
    """Verifica o estado atual de um cartão e retorna (resultado, id_funcionario, nome, cargo, is_admin).

    is_admin indica se o funcionário dono do cartão tem uma conta em a3_usuarios
    com nivel_acesso='admin' — usado pelo ESP para entrar em modo de cadastro
    (próxima leitura de cartão vai para o tópico a3/cadastros). Só é considerado
    quando o acesso é liberado; em qualquer negação vem sempre False.
    """
    with get_cursor() as cur:
        cur.execute(
            """SELECT c.ativo AS cartao_ativo, f.id AS id_funcionario, f.nome, f.cargo,
                      f.ativo AS funcionario_ativo,
                      EXISTS (
                          SELECT 1 FROM a3_usuarios u
                          WHERE u.id_funcionario = f.id AND u.nivel_acesso = 'admin'
                      ) AS is_admin
               FROM a3_cartoes_rfid c
               LEFT JOIN a3_funcionarios f ON f.id = c.id_funcionario
               WHERE c.uid = %s""",
            (uid,)
        )
        cartao = cur.fetchone()

    if cartao is None:
        return "negado_desconhecido", None, None, None, False
    if not cartao["cartao_ativo"] or not cartao["funcionario_ativo"]:
        return "negado_inativo", cartao["id_funcionario"], cartao["nome"], cartao["cargo"], False
    return "liberado", cartao["id_funcionario"], cartao["nome"], cartao["cargo"], bool(cartao["is_admin"])


@bp.route("/acesso/<uid>", methods=["GET"])
def verificar_acesso(uid):
    """Consultado pelo Node-RED a cada leitura de cartão na catraca.

    Sempre responde JSON, mesmo em erro: o nó HTTP do Node-RED espera o corpo
    como objeto (ret=obj) e quebra com "JSON parse error" se receber a página
    HTML de erro/debug do Flask.
    """
    try:
        uid = normalizar_uid(uid)
        resultado, _, nome, cargo, is_admin = _classificar_uid(uid)
        autorizado = resultado == "liberado"
    except Exception:
        current_app.logger.exception("Falha ao verificar acesso para uid=%r", uid)
        return jsonify({"nome": "Desconhecido", "autorizado": False, "isAdmin": False, "cargo": None}), 500

    return jsonify({
        "nome": nome or "Desconhecido",
        "autorizado": autorizado,
        "isAdmin": is_admin,
        "cargo": cargo,
    })


@bp.route("/acesso/log", methods=["POST"])
def registrar_acesso():
    """Registra o resultado de uma leitura, chamado pelo Node-RED após a verificação.

    Sempre responde JSON, mesmo em erro, pelo mesmo motivo de verificar_acesso.
    """
    dados = request.get_json(force=True) or {}
    uid = normalizar_uid(dados.get("uid_cartao", ""))

    try:
        resultado, id_funcionario, _, _, _ = _classificar_uid(uid)

        with get_cursor(commit=True) as cur:
            cur.execute(
                """INSERT INTO a3_registros_acesso (uid, id_funcionario, resultado)
                   VALUES (%s, %s, %s)
                   RETURNING id, data_hora""",
                (uid, id_funcionario, resultado)
            )
            registro = cur.fetchone()
    except Exception:
        current_app.logger.exception("Falha ao registrar acesso para uid=%r", uid)
        return jsonify({"sucesso": False, "motivo": "erro_interno"}), 500

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
    """Lista paginada de acessos com filtros + totalizadores por resultado.

    Além da página pedida, devolve o total geral e a contagem por resultado
    (liberados/negados/desconhecidos) calculada sobre TODOS os registros que
    casam com o filtro — é o que alimenta o totalizador acima da tabela.
    """
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


@bp.route("/acessos/estatisticas", methods=["GET"])
@requer_login
@requer_admin
def estatisticas_acessos():
    """Resumo para o dashboard do painel admin.

    Retorna os totais do dia atual, contagens gerais (funcionários ativos,
    lugares) e a série dos últimos 7 dias agregada por dia/resultado. A
    agregação diária usa time_bucket(), função do TimescaleDB otimizada para
    janelamento temporal em hipertabelas (mesma técnica usada no Grafana).
    """
    with get_cursor() as cur:
        # Totais de hoje, quebrados por resultado.
        cur.execute(
            """SELECT resultado, COUNT(*) AS total
               FROM a3_registros_acesso
               WHERE data_hora >= CURRENT_DATE
               GROUP BY resultado"""
        )
        hoje = {linha["resultado"]: linha["total"] for linha in cur.fetchall()}

        # Série diária dos últimos 7 dias (hoje incluído), por resultado.
        cur.execute(
            """SELECT time_bucket('1 day', data_hora) AS dia, resultado, COUNT(*) AS total
               FROM a3_registros_acesso
               WHERE data_hora >= CURRENT_DATE - INTERVAL '6 days'
               GROUP BY dia, resultado
               ORDER BY dia ASC"""
        )
        por_dia = cur.fetchall()

        cur.execute("SELECT COUNT(*) AS total FROM a3_funcionarios WHERE ativo")
        funcionarios_ativos = cur.fetchone()["total"]

        cur.execute("SELECT COUNT(*) AS total FROM a3_areas")
        total_areas = cur.fetchone()["total"]

    # Reorganiza a série em um dicionário {data: {liberados, negados, desconhecidos}}
    # para depois preencher os dias sem registro com zeros (o GROUP BY só devolve
    # dias que têm pelo menos uma linha, mas o gráfico precisa dos 7 dias).
    serie = {}
    for linha in por_dia:
        dia = linha["dia"].date().isoformat()
        ponto = serie.setdefault(dia, {"liberados": 0, "negados": 0, "desconhecidos": 0})
        if linha["resultado"] == "liberado":
            ponto["liberados"] += linha["total"]
        elif linha["resultado"] == "negado_desconhecido":
            ponto["desconhecidos"] += linha["total"]
        else:  # negado_sem_permissao / negado_inativo
            ponto["negados"] += linha["total"]

    ultimos_7_dias = []
    for i in range(6, -1, -1):
        dia = (date.today() - timedelta(days=i)).isoformat()
        ponto = serie.get(dia, {"liberados": 0, "negados": 0, "desconhecidos": 0})
        ultimos_7_dias.append({"dia": dia, **ponto})

    negados_hoje = hoje.get("negado_sem_permissao", 0) + hoje.get("negado_inativo", 0)
    desconhecidos_hoje = hoje.get("negado_desconhecido", 0)

    return jsonify({
        "hoje": {
            "total": hoje.get("liberado", 0) + negados_hoje + desconhecidos_hoje,
            "liberados": hoje.get("liberado", 0),
            "negados": negados_hoje,
            "desconhecidos": desconhecidos_hoje,
        },
        "funcionarios_ativos": funcionarios_ativos,
        "total_areas": total_areas,
        "ultimos_7_dias": ultimos_7_dias,
    })


@bp.route("/acessos/exportar", methods=["GET"])
@requer_login
def exportar_acessos():
    """Exporta os acessos em CSV com os mesmos filtros da listagem (sem paginação)."""
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
