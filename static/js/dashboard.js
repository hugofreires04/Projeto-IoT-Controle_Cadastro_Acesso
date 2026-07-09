// dashboard.js — Aba "Dashboard" do painel admin.
//
// Consome GET /api/acessos/estatisticas e renderiza:
//   1. Tiles de estatística (acessos de hoje, liberados, negados, funcionários ativos)
//   2. Gráfico de colunas empilhadas dos últimos 7 dias, desenhado em SVG puro
//      (sem bibliotecas externas), com tooltip ao passar o mouse.
//
// O gráfico segue o mesmo papel do Grafana na arquitetura do projeto, mas
// embutido no próprio painel: agregação diária feita pelo TimescaleDB
// (time_bucket) no backend, visualização aqui no frontend.

// Cores das séries — paleta de status validada para daltonismo (ΔE >= 12
// entre pares adjacentes) e contraste >= 3:1 sobre fundo branco.
const SERIES_GRAFICO = [
    { chave: "liberados",     rotulo: "Liberados",     cor: "#0ca30c" },
    { chave: "negados",       rotulo: "Negados",       cor: "#d03b3b" },
    { chave: "desconhecidos", rotulo: "Desconhecidos", cor: "#c98500" },
];

const DIAS_SEMANA = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

// ── Tiles de estatística ────────────────────────────────────────────────────

function _renderTiles(dados) {
    document.getElementById("tile-hoje").textContent = dados.hoje.total;
    document.getElementById("tile-liberados").textContent = dados.hoje.liberados;
    document.getElementById("tile-negados").textContent =
        dados.hoje.negados + dados.hoje.desconhecidos;
    document.getElementById("tile-funcionarios").textContent = dados.funcionarios_ativos;
    document.getElementById("tile-funcionarios-detalhe").textContent =
        `${dados.total_areas} ${dados.total_areas === 1 ? "lugar cadastrado" : "lugares cadastrados"}`;
}

// ── Gráfico de colunas empilhadas (SVG) ─────────────────────────────────────

// Arredonda o teto do eixo Y para o próximo múltiplo de 4: como o eixo tem
// 4 divisões, isso garante que todas as linhas de grade caiam em inteiros.
function _tetoLimpo(maximo) {
    return Math.max(Math.ceil(maximo / 4) * 4, 4);
}

// Cria um elemento SVG com atributos (helper para não repetir setAttribute).
function _svgEl(tag, atributos) {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [chave, valor] of Object.entries(atributos)) el.setAttribute(chave, valor);
    return el;
}

// Caminho de um retângulo com só os cantos DE CIMA arredondados — usado no
// segmento do topo de cada coluna (base da coluna permanece reta, colada no eixo).
function _retanguloTopoRedondo(x, y, largura, altura, raio) {
    const r = Math.min(raio, altura, largura / 2);
    return `M ${x} ${y + altura}
            L ${x} ${y + r}
            Q ${x} ${y} ${x + r} ${y}
            L ${x + largura - r} ${y}
            Q ${x + largura} ${y} ${x + largura} ${y + r}
            L ${x + largura} ${y + altura} Z`;
}

function _renderGrafico(serie) {
    const container = document.getElementById("grafico-container");
    container.innerHTML = "";

    const totalGeral = serie.reduce(
        (soma, dia) => soma + dia.liberados + dia.negados + dia.desconhecidos, 0
    );
    if (totalGeral === 0) {
        const vazio = document.createElement("p");
        vazio.className = "grafico-vazio";
        vazio.textContent = "Nenhum acesso registrado nos últimos 7 dias. Passe um cartão na catraca para ver o gráfico ganhar vida.";
        container.appendChild(vazio);
        return;
    }

    // Geometria do gráfico (coordenadas do viewBox; escala junto com o card).
    const LARGURA = 680, ALTURA = 250;
    const MARGEM = { esquerda: 34, direita: 8, topo: 22, baixo: 26 };
    const larguraPlot = LARGURA - MARGEM.esquerda - MARGEM.direita;
    const alturaPlot = ALTURA - MARGEM.topo - MARGEM.baixo;
    const LARGURA_COLUNA = 26;   // colunas finas — o "ar" entre elas é proposital
    const GAP_SEGMENTO = 2;      // respiro branco entre segmentos empilhados

    const maximo = _tetoLimpo(Math.max(
        ...serie.map((d) => d.liberados + d.negados + d.desconhecidos)
    ));
    const escalaY = (valor) => alturaPlot * (valor / maximo);

    const svg = _svgEl("svg", {
        viewBox: `0 0 ${LARGURA} ${ALTURA}`,
        class: "grafico-svg",
        role: "img",
        "aria-label": "Acessos por dia nos últimos 7 dias, divididos entre liberados, negados e desconhecidos",
    });

    // Linhas de grade horizontais + valores do eixo Y (4 divisões).
    for (let i = 0; i <= 4; i++) {
        const valor = (maximo / 4) * i;
        const y = MARGEM.topo + alturaPlot - escalaY(valor);

        svg.appendChild(_svgEl("line", {
            x1: MARGEM.esquerda, y1: y, x2: LARGURA - MARGEM.direita, y2: y,
            stroke: i === 0 ? "#c9cedb" : "#eceef4",   // linha de base um pouco mais forte
            "stroke-width": 1,
        }));

        const tick = _svgEl("text", {
            x: MARGEM.esquerda - 8, y: y + 3.5,
            "text-anchor": "end", "font-size": 10.5, fill: "#8a93a8",
        });
        tick.textContent = valor;
        svg.appendChild(tick);
    }

    const bandaDia = larguraPlot / serie.length;

    serie.forEach((dia, indice) => {
        const centroX = MARGEM.esquerda + bandaDia * indice + bandaDia / 2;
        const xColuna = centroX - LARGURA_COLUNA / 2;
        const total = dia.liberados + dia.negados + dia.desconhecidos;

        // Desenha os segmentos de baixo para cima: liberados → negados → desconhecidos.
        // O último segmento com valor recebe o topo arredondado.
        const valores = SERIES_GRAFICO.map((s) => ({ ...s, valor: dia[s.chave] }));
        const comValor = valores.filter((v) => v.valor > 0);
        let yAtual = MARGEM.topo + alturaPlot;

        comValor.forEach((segmento, i) => {
            const altura = Math.max(escalaY(segmento.valor) - (i > 0 ? GAP_SEGMENTO : 0), 1.5);
            yAtual -= (i > 0 ? GAP_SEGMENTO : 0) + altura;

            const ehTopo = i === comValor.length - 1;
            const marca = ehTopo
                ? _svgEl("path", { d: _retanguloTopoRedondo(xColuna, yAtual, LARGURA_COLUNA, altura, 4), fill: segmento.cor })
                : _svgEl("rect", { x: xColuna, y: yAtual, width: LARGURA_COLUNA, height: altura, fill: segmento.cor });
            svg.appendChild(marca);
        });

        // Total no topo da coluna (rótulo direto — o tooltip traz o detalhamento).
        if (total > 0) {
            const rotuloTotal = _svgEl("text", {
                x: centroX, y: yAtual - 6,
                "text-anchor": "middle", "font-size": 11, "font-weight": 600, fill: "#52596b",
            });
            rotuloTotal.textContent = total;
            svg.appendChild(rotuloTotal);
        }

        // Rótulo do dia no eixo X: "Seg 30/06".
        const data = new Date(dia.dia + "T00:00:00");
        const rotuloDia = _svgEl("text", {
            x: centroX, y: ALTURA - 8,
            "text-anchor": "middle", "font-size": 10.5, fill: "#8a93a8",
        });
        rotuloDia.textContent =
            `${DIAS_SEMANA[data.getDay()]} ${String(data.getDate()).padStart(2, "0")}/${String(data.getMonth() + 1).padStart(2, "0")}`;
        svg.appendChild(rotuloDia);

        // Área de hover: retângulo invisível cobrindo a banda inteira do dia
        // (alvo bem maior que a coluna — o leitor mira no dia, não em pixels).
        const hit = _svgEl("rect", {
            x: MARGEM.esquerda + bandaDia * indice, y: MARGEM.topo,
            width: bandaDia, height: alturaPlot,
            fill: "transparent",
        });
        hit.addEventListener("pointermove", (evento) => _mostrarTooltip(evento, dia, data));
        hit.addEventListener("pointerleave", _esconderTooltip);
        svg.appendChild(hit);
    });

    container.appendChild(svg);
}

// ── Tooltip do gráfico ──────────────────────────────────────────────────────

function _mostrarTooltip(evento, dia, data) {
    const tooltip = document.getElementById("grafico-tooltip");
    tooltip.innerHTML = "";

    // Cabeçalho: data por extenso.
    const cabecalho = document.createElement("div");
    cabecalho.className = "tt-dia";
    cabecalho.textContent = data.toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "2-digit" });
    tooltip.appendChild(cabecalho);

    // Uma linha por série, sempre as três (mesmo com valor 0), valor em destaque.
    for (const s of SERIES_GRAFICO) {
        const linha = document.createElement("div");
        linha.className = "tt-linha";

        const nome = document.createElement("span");
        nome.className = "tt-serie";
        const chip = document.createElement("span");
        chip.className = "legenda-cor";
        chip.style.background = s.cor;
        nome.appendChild(chip);
        nome.appendChild(document.createTextNode(s.rotulo));

        const valor = document.createElement("strong");
        valor.textContent = dia[s.chave];

        linha.appendChild(nome);
        linha.appendChild(valor);
        tooltip.appendChild(linha);
    }

    // Posiciona perto do cursor, dentro do card (evita vazar pela direita).
    const card = tooltip.parentElement.getBoundingClientRect();
    let x = evento.clientX - card.left + 14;
    const y = evento.clientY - card.top + 14;
    if (x + 160 > card.width) x -= 180;

    tooltip.style.left = x + "px";
    tooltip.style.top = y + "px";
    tooltip.classList.add("visivel");
}

function _esconderTooltip() {
    document.getElementById("grafico-tooltip").classList.remove("visivel");
}

// ── Carregamento e atualização automática ──────────────────────────────────

async function _carregarDashboard() {
    // Só busca dados se a aba Dashboard estiver visível (economiza requisições).
    if (!document.getElementById("tab-dashboard").classList.contains("ativo")) return;

    const resposta = await apiFetch("/api/acessos/estatisticas");
    const dados = await resposta.json();

    _renderTiles(dados);
    _renderGrafico(dados.ultimos_7_dias);

    document.getElementById("dashboard-atualizado").textContent =
        "Atualizado às " + new Date().toLocaleTimeString("pt-BR");
}

function initDashboard() {
    _carregarDashboard();

    // Recarrega ao entrar na aba e a cada 30s enquanto ela estiver aberta —
    // mesmo espírito do painel do Grafana, que se atualiza sozinho.
    document.querySelector('.tab-btn[data-tab="dashboard"]').addEventListener("click", _carregarDashboard);
    setInterval(_carregarDashboard, 30000);
}
