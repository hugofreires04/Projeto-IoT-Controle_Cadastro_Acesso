// Componente de tabela de acessos, reutilizado em admin.html e operador.html.
// Espera os elementos com os IDs/classes abaixo já presentes na página:
//   #filtro-area, #filtro-funcionario (opcional), #filtro-data-inicio, #filtro-data-fim,
//   .badge-filtro[data-resultado], #btn-aplicar-filtros, #btn-exportar-csv,
//   #totalizador, #tabela-acessos-corpo, #pag-info, #btn-pag-anterior, #btn-pag-proximo

const ROTULOS_RESULTADO = {
    liberado: { texto: "Liberado", classe: "badge-liberado" },
    negado_sem_permissao: { texto: "Negado (sem permissão)", classe: "badge-negado" },
    negado_inativo: { texto: "Negado (inativo)", classe: "badge-negado" },
    negado_desconhecido: { texto: "Desconhecido", classe: "badge-desconhecido" },
};

let _tabelaAcessosEstado = { pagina: 1, resultado: "", mostrarFiltroFuncionario: false };

function _badgeResultado(resultado) {
    const info = ROTULOS_RESULTADO[resultado] || { texto: resultado, classe: "" };
    return `<span class="badge ${info.classe}">${info.texto}</span>`;
}

async function _carregarAreas() {
    const select = document.getElementById("filtro-area");
    if (!select) return;
    const resposta = await apiFetch("/api/areas");
    const areas = await resposta.json();
    for (const area of areas) {
        const opcao = document.createElement("option");
        opcao.value = area.id;
        opcao.textContent = area.nome;
        select.appendChild(opcao);
    }
}

async function _carregarFuncionarios() {
    const select = document.getElementById("filtro-funcionario");
    if (!select) return;
    const resposta = await apiFetch("/api/funcionarios");
    const funcionarios = await resposta.json();
    for (const funcionario of funcionarios) {
        const opcao = document.createElement("option");
        opcao.value = funcionario.id;
        opcao.textContent = funcionario.nome;
        select.appendChild(opcao);
    }
}

function _montarQueryString() {
    const params = new URLSearchParams();

    if (_tabelaAcessosEstado.mostrarFiltroFuncionario) {
        const funcionarioId = document.getElementById("filtro-funcionario")?.value;
        if (funcionarioId) params.set("funcionario_id", funcionarioId);
    }

    const areaId = document.getElementById("filtro-area")?.value;
    if (areaId) params.set("area_id", areaId);

    const dataInicio = document.getElementById("filtro-data-inicio")?.value;
    if (dataInicio) params.set("data_inicio", dataInicio);

    const dataFim = document.getElementById("filtro-data-fim")?.value;
    if (dataFim) params.set("data_fim", dataFim);

    if (_tabelaAcessosEstado.resultado) params.set("resultado", _tabelaAcessosEstado.resultado);

    params.set("page", _tabelaAcessosEstado.pagina);
    params.set("limit", 20);

    return params.toString();
}

async function _carregarAcessos() {
    const resposta = await apiFetch("/api/acessos?" + _montarQueryString());
    const dados = await resposta.json();

    const corpo = document.getElementById("tabela-acessos-corpo");
    corpo.innerHTML = dados.registros.map((r) => `
        <tr>
            <td>${r.funcionario || "Desconhecido"}</td>
            <td>${r.area || "—"}</td>
            <td>${_badgeResultado(r.resultado)}</td>
            <td>${new Date(r.data_hora).toLocaleString("pt-BR")}</td>
        </tr>
    `).join("") || `<tr><td colspan="4">Nenhum registro encontrado.</td></tr>`;

    document.getElementById("totalizador").textContent =
        `${dados.totais.liberados} liberados · ${dados.totais.negados} negados · ${dados.totais.desconhecidos} desconhecidos`;

    document.getElementById("pag-info").textContent = `Página ${dados.pagina} de ${dados.paginas}`;
    document.getElementById("btn-pag-anterior").disabled = dados.pagina <= 1;
    document.getElementById("btn-pag-proximo").disabled = dados.pagina >= dados.paginas;
}

async function _exportarCSV() {
    const resposta = await apiFetch("/api/acessos/exportar?" + _montarQueryString());
    const blob = await resposta.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "acessos.csv";
    link.click();
}

function initTabelaAcessos({ mostrarFiltroFuncionario = false } = {}) {
    _tabelaAcessosEstado.mostrarFiltroFuncionario = mostrarFiltroFuncionario;

    _carregarAreas();
    if (mostrarFiltroFuncionario) _carregarFuncionarios();

    const aplicarEReiniciarPagina = () => {
        _tabelaAcessosEstado.pagina = 1;
        _carregarAcessos();
    };

    // Aplica os filtros automaticamente ao trocar área/funcionário/data, sem
    // precisar clicar em "Aplicar filtros" (que continua disponível por clareza).
    document.getElementById("filtro-area")?.addEventListener("change", aplicarEReiniciarPagina);
    document.getElementById("filtro-funcionario")?.addEventListener("change", aplicarEReiniciarPagina);
    document.getElementById("filtro-data-inicio")?.addEventListener("change", aplicarEReiniciarPagina);
    document.getElementById("filtro-data-fim")?.addEventListener("change", aplicarEReiniciarPagina);

    document.querySelectorAll(".badge-filtro").forEach((botao) => {
        botao.addEventListener("click", () => {
            document.querySelectorAll(".badge-filtro").forEach((b) => b.classList.remove("ativo"));
            botao.classList.add("ativo");
            _tabelaAcessosEstado.resultado = botao.dataset.resultado;
            aplicarEReiniciarPagina();
        });
    });

    document.getElementById("btn-aplicar-filtros").addEventListener("click", aplicarEReiniciarPagina);

    document.getElementById("btn-exportar-csv").addEventListener("click", _exportarCSV);

    document.getElementById("btn-pag-anterior").addEventListener("click", () => {
        _tabelaAcessosEstado.pagina -= 1;
        _carregarAcessos();
    });

    document.getElementById("btn-pag-proximo").addEventListener("click", () => {
        _tabelaAcessosEstado.pagina += 1;
        _carregarAcessos();
    });

    _carregarAcessos();
}
