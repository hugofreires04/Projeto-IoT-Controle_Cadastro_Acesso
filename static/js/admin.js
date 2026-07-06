// admin.js — Lógica das abas do painel admin (admin.html):
//   initAbas()           → troca de abas (mostra/esconde as <section>)
//   initFuncionarios()   → listagem com busca + ativar/desativar pessoa e cartão
//   initCadastroManual() → formulário de cadastro de funcionário
//   initUidsPendentes()  → fila de UIDs lidos na catraca em modo cadastro
//   initAreas()          → CRUD de lugares (áreas físicas)
//   initUsuarios()       → CRUD de contas de login do painel
//
// Convenção: funções com prefixo _ são internas do arquivo; as init* são
// chamadas uma vez pelo <script> no final do admin.html.

// Liga cada botão .tab-btn à <section> de id "tab-<data-tab>": ao clicar,
// remove a classe .ativo de tudo e aplica só no par botão/section clicado.
function initAbas() {
    document.querySelectorAll(".tab-btn").forEach((botao) => {
        botao.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("ativo"));
            document.querySelectorAll(".tab-conteudo").forEach((c) => c.classList.remove("ativo"));
            botao.classList.add("ativo");
            document.getElementById("tab-" + botao.dataset.tab).classList.add("ativo");
        });
    });
}

// Debounce: adia a execução de fn até o usuário parar de digitar por `espera` ms.
// Evita uma requisição ao banco a cada tecla nos campos de busca.
function _debounce(fn, espera) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), espera);
    };
}

// ── Funcionários ───────────────────────────────────────────────────────────

// Estado atual dos filtros de busca (nome/cargo com debounce, status imediato).
let _filtroFuncionarios = { nome: "", cargo: "", status: "" };

// Converte o estado dos filtros em query string (?nome=...&cargo=...&status=...).
function _montarQueryFuncionarios() {
    const params = new URLSearchParams();
    if (_filtroFuncionarios.nome) params.set("nome", _filtroFuncionarios.nome);
    if (_filtroFuncionarios.cargo) params.set("cargo", _filtroFuncionarios.cargo);
    if (_filtroFuncionarios.status) params.set("status", _filtroFuncionarios.status);
    return params.toString();
}

// Busca os funcionários na API e redesenha a tabela inteira. Cada linha traz
// o status da pessoa e a lista de cartões, ambos com botão de ativar/desativar.
async function _renderFuncionarios() {
    const resposta = await apiFetch("/api/funcionarios?" + _montarQueryFuncionarios());
    const funcionarios = await resposta.json();

    const corpo = document.getElementById("tabela-funcionarios-corpo");
    corpo.innerHTML = funcionarios.map((f) => `
        <tr>
            <td>${f.nome}</td>
            <td>${f.cargo || "—"}</td>
            <td>
                <span class="badge ${f.ativo ? "ativo" : "inativo"}">${f.ativo ? "Ativo" : "Inativo"}</span>
                <button class="btn-link toggle-funcionario" data-id="${f.id}" data-ativo="${f.ativo}">
                    ${f.ativo ? "Desativar" : "Ativar"}
                </button>
            </td>
            <td>
                ${f.cartoes.map((c) => `
                    <div class="cartao-linha">
                        <code>${c.uid}</code>
                        <button class="btn-link toggle-cartao" data-funcionario="${f.id}" data-cartao="${c.id}" data-ativo="${c.ativo}">
                            ${c.ativo ? "Desativar" : "Ativar"}
                        </button>
                    </div>
                `).join("")}
            </td>
        </tr>
    `).join("") || `<tr><td colspan="4" class="vazio">Nenhum funcionário encontrado.</td></tr>`;

    // Ativa/desativa um cartão específico (PUT no par funcionário+cartão).
    corpo.querySelectorAll(".toggle-cartao").forEach((botao) => {
        botao.addEventListener("click", async () => {
            const novoStatus = botao.dataset.ativo !== "true";
            await apiFetch(`/api/funcionarios/${botao.dataset.funcionario}/cartoes/${botao.dataset.cartao}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ativo: novoStatus }),
            });
            _renderFuncionarios();
        });
    });

    // Ativa/desativa o funcionário inteiro (independe do status de cada cartão).
    corpo.querySelectorAll(".toggle-funcionario").forEach((botao) => {
        botao.addEventListener("click", async () => {
            const novoStatus = botao.dataset.ativo !== "true";
            await apiFetch(`/api/funcionarios/${botao.dataset.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ativo: novoStatus }),
            });
            _renderFuncionarios();
        });
    });
}

function initFuncionarios() {
    _renderFuncionarios();
    // Recarrega ao entrar na aba, para refletir cadastros feitos em outras abas.
    document.querySelector('.tab-btn[data-tab="funcionarios"]').addEventListener("click", _renderFuncionarios);

    // Busca "ao vivo": espera 300ms sem digitação antes de consultar a API.
    const aplicarFiltroComDelay = _debounce(_renderFuncionarios, 300);

    document.getElementById("filtro-func-nome").addEventListener("input", (evento) => {
        _filtroFuncionarios.nome = evento.target.value.trim();
        aplicarFiltroComDelay();
    });
    document.getElementById("filtro-func-cargo").addEventListener("input", (evento) => {
        _filtroFuncionarios.cargo = evento.target.value.trim();
        aplicarFiltroComDelay();
    });
    document.getElementById("filtro-func-status").addEventListener("change", (evento) => {
        _filtroFuncionarios.status = evento.target.value;
        _renderFuncionarios();
    });
}

// ── Cadastro manual de funcionário ──────────────────────────────────────────

// Monta o formulário de cadastro: carrega os lugares como checkboxes de
// permissão e envia tudo num único POST /api/funcionarios (que cria o
// funcionário, o cartão, as permissões e, se pedido, a conta de login).
async function initCadastroManual() {
    const resposta = await apiFetch("/api/areas");
    const areas = await resposta.json();

    const container = document.getElementById("cad-areas");
    container.innerHTML = areas.map((area) => `
        <label class="campo-checkbox">
            <input type="checkbox" name="cad-area" value="${area.id}"> ${area.nome}
        </label>
    `).join("") || "Nenhum lugar cadastrado.";

    document.getElementById("form-cadastro-manual").addEventListener("submit", async (evento) => {
        evento.preventDefault();

        const mensagem = document.getElementById("cadastro-mensagem");
        mensagem.style.display = "none";

        const areasSelecionadas = Array.from(container.querySelectorAll("input:checked")).map((el) => Number(el.value));

        const corpo = {
            uid: document.getElementById("cad-uid").value,
            nome: document.getElementById("cad-nome").value,
            cargo: document.getElementById("cad-cargo").value,
            nivel_acesso: document.getElementById("cad-nivel").value || null,
            areas: areasSelecionadas,
        };

        const resp = await apiFetch("/api/funcionarios", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(corpo),
        });
        const dados = await resp.json();

        // Se o cadastro criou uma conta de login junto, mostra a senha inicial
        // gerada (derivada do UID) para o admin repassar ao funcionário.
        let texto;
        if (resp.ok) {
            texto = `Funcionário "${dados.nome}" cadastrado com sucesso!`;
            if (dados.usuario_criado) {
                texto += ` Conta de acesso criada — senha inicial: ${dados.usuario_criado.senha_inicial}`;
            }
        } else {
            texto = dados.erro || "Erro ao cadastrar funcionário.";
        }
        mensagem.className = resp.ok ? "flash flash-sucesso" : "flash flash-erro";
        mensagem.textContent = texto;
        mensagem.style.display = "block";

        if (resp.ok) {
            document.getElementById("form-cadastro-manual").reset();
            _renderUidsPendentes();
        }
    });
}

// ── UIDs pendentes de cadastro (lidos pela catraca em modo admin) ───────────
// Quando o admin usa o próprio cartão na catraca, o ESP entra em modo cadastro
// e publica o(s) próximo(s) UID(s) lido(s) em a3/cadastros (ver nodered/flow_acesso.json),
// que o Flask guarda em a3_uids_pendentes (TTL de alguns minutos) até aparecerem aqui,
// empilhados do mais recente pro mais antigo.

async function _renderUidsPendentes() {
    if (!document.getElementById("tab-cadastrar").classList.contains("ativo")) return;

    const resposta = await apiFetch("/api/cadastros/uid-pendente");
    const pendentes = await resposta.json();

    const lista = document.getElementById("uid-pendentes-lista");
    lista.innerHTML = pendentes.map((p) => `
        <div class="flash flash-info uid-pendente-banner">
            <span class="uid-pendente-texto">
                Cartão novo lido na catraca: <code>${p.uid}</code>
                (${new Date(p.recebido_em).toLocaleTimeString("pt-BR")})
            </span>
            <span class="uid-pendente-acoes">
                <button type="button" class="btn-link usar-uid-pendente" data-uid="${p.uid}">Usar este UID</button>
                <button type="button" class="btn-link perigo descartar-uid-pendente" data-id="${p.id}">Descartar</button>
            </span>
        </div>
    `).join("");

    lista.querySelectorAll(".usar-uid-pendente").forEach((botao) => {
        botao.addEventListener("click", () => {
            document.getElementById("cad-uid").value = botao.dataset.uid;
        });
    });

    lista.querySelectorAll(".descartar-uid-pendente").forEach((botao) => {
        botao.addEventListener("click", async () => {
            await apiFetch(`/api/cadastros/uid-pendente/${botao.dataset.id}`, { method: "DELETE" });
            _renderUidsPendentes();
        });
    });
}

function initUidsPendentes() {
    _renderUidsPendentes();
    // Polling a cada 5s: se alguém passar um cartão novo na catraca com a aba
    // aberta, o banner aparece sem precisar recarregar a página.
    setInterval(_renderUidsPendentes, 5000);
    document.querySelector('.tab-btn[data-tab="cadastrar"]').addEventListener("click", _renderUidsPendentes);
}

// ── Lugares (áreas) ─────────────────────────────────────────────────────────

// O mesmo formulário serve para criar e editar: o campo hidden #area-id
// vazio significa "criar" (POST); preenchido significa "editar" (PUT).

async function _renderAreas() {
    const resposta = await apiFetch("/api/areas");
    const areas = await resposta.json();

    const corpo = document.getElementById("tabela-areas-corpo");
    corpo.innerHTML = areas.map((a) => `
        <tr>
            <td>${a.nome}</td>
            <td>${a.descricao || "—"}</td>
            <td>
                <button class="btn-link editar-area" data-id="${a.id}" data-nome="${a.nome}" data-descricao="${a.descricao || ""}">Editar</button>
                <button class="btn-link perigo remover-area" data-id="${a.id}">Remover</button>
            </td>
        </tr>
    `).join("") || `<tr><td colspan="3" class="vazio">Nenhum lugar cadastrado.</td></tr>`;

    // "Editar" copia os dados da linha para o formulário e troca o modo do botão.

    corpo.querySelectorAll(".editar-area").forEach((botao) => {
        botao.addEventListener("click", () => {
            document.getElementById("area-id").value = botao.dataset.id;
            document.getElementById("area-nome").value = botao.dataset.nome;
            document.getElementById("area-descricao").value = botao.dataset.descricao;
            document.getElementById("area-botao-salvar").textContent = "Salvar alterações";
            document.getElementById("area-cancelar-edicao").style.display = "inline";
        });
    });

    corpo.querySelectorAll(".remover-area").forEach((botao) => {
        botao.addEventListener("click", async () => {
            if (!confirm("Remover este lugar? As permissões associadas a ele também serão removidas.")) return;
            await apiFetch(`/api/areas/${botao.dataset.id}`, { method: "DELETE" });
            _renderAreas();
        });
    });
}

function _resetFormArea() {
    document.getElementById("form-area").reset();
    document.getElementById("area-id").value = "";
    document.getElementById("area-botao-salvar").textContent = "Adicionar";
    document.getElementById("area-cancelar-edicao").style.display = "none";
}

function initAreas() {
    _renderAreas();
    document.querySelector('.tab-btn[data-tab="areas"]').addEventListener("click", _renderAreas);

    document.getElementById("area-cancelar-edicao").addEventListener("click", (evento) => {
        evento.preventDefault();
        _resetFormArea();
    });

    document.getElementById("form-area").addEventListener("submit", async (evento) => {
        evento.preventDefault();

        const id = document.getElementById("area-id").value;
        const corpo = {
            nome: document.getElementById("area-nome").value,
            descricao: document.getElementById("area-descricao").value,
        };

        const resp = id
            ? await apiFetch(`/api/areas/${id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(corpo),
            })
            : await apiFetch("/api/areas", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(corpo),
            });
        const dados = await resp.json();

        const mensagem = document.getElementById("area-mensagem");
        mensagem.className = resp.ok ? "flash flash-sucesso" : "flash flash-erro";
        mensagem.textContent = resp.ok ? "Lugar salvo com sucesso!" : (dados.erro || "Erro ao salvar lugar.");
        mensagem.style.display = "block";

        if (resp.ok) {
            _resetFormArea();
            _renderAreas();
        }
    });
}

// ── Usuários do sistema ──────────────────────────────────────────────────────

// Popula o select "Funcionário vinculado" do formulário de criação de usuário.
// O vínculo é o que permite ao operador ver o próprio histórico de acessos.
async function _carregarFuncionariosSelect() {
    const select = document.getElementById("usuario-funcionario");
    const resposta = await apiFetch("/api/funcionarios");
    const funcionarios = await resposta.json();
    select.innerHTML = '<option value="">Nenhum</option>' +
        funcionarios.map((f) => `<option value="${f.id}">${f.nome}</option>`).join("");
}

async function _renderUsuarios() {
    const resposta = await apiFetch("/api/usuarios");
    const usuarios = await resposta.json();

    const corpo = document.getElementById("tabela-usuarios-corpo");
    corpo.innerHTML = usuarios.map((u) => `
        <tr>
            <td>${u.nome}</td>
            <td>${u.email}</td>
            <td>
                <select class="usuario-nivel" data-id="${u.id}">
                    <option value="operador" ${u.nivel_acesso === "operador" ? "selected" : ""}>Operador</option>
                    <option value="admin" ${u.nivel_acesso === "admin" ? "selected" : ""}>Admin</option>
                </select>
            </td>
            <td>${u.funcionario_nome || "—"}</td>
            <td>
                <button class="btn-link redefinir-senha" data-id="${u.id}">Redefinir senha</button>
                <button class="btn-link perigo remover-usuario" data-id="${u.id}">Remover</button>
            </td>
        </tr>
    `).join("") || `<tr><td colspan="5" class="vazio">Nenhum usuário cadastrado.</td></tr>`;

    // O nível de acesso é editado direto no select da tabela (salva no change).

    corpo.querySelectorAll(".usuario-nivel").forEach((select) => {
        select.addEventListener("change", async () => {
            await apiFetch(`/api/usuarios/${select.dataset.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ nivel_acesso: select.value }),
            });
        });
    });

    corpo.querySelectorAll(".redefinir-senha").forEach((botao) => {
        botao.addEventListener("click", async () => {
            const novaSenha = prompt("Digite a nova senha para este usuário:");
            if (!novaSenha) return;
            await apiFetch(`/api/usuarios/${botao.dataset.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ senha: novaSenha }),
            });
            alert("Senha atualizada.");
        });
    });

    corpo.querySelectorAll(".remover-usuario").forEach((botao) => {
        botao.addEventListener("click", async () => {
            if (!confirm("Remover este usuário?")) return;
            const resp = await apiFetch(`/api/usuarios/${botao.dataset.id}`, { method: "DELETE" });
            if (!resp.ok) {
                const dados = await resp.json();
                alert(dados.erro || "Erro ao remover usuário.");
                return;
            }
            _renderUsuarios();
        });
    });
}

function initUsuarios() {
    _renderUsuarios();
    _carregarFuncionariosSelect();
    document.querySelector('.tab-btn[data-tab="usuarios"]').addEventListener("click", () => {
        _renderUsuarios();
        _carregarFuncionariosSelect();
    });

    document.getElementById("form-usuario").addEventListener("submit", async (evento) => {
        evento.preventDefault();

        const mensagem = document.getElementById("usuario-mensagem");
        mensagem.style.display = "none";

        const corpo = {
            nome: document.getElementById("usuario-nome").value,
            email: document.getElementById("usuario-email").value,
            senha: document.getElementById("usuario-senha").value,
            nivel_acesso: document.getElementById("usuario-nivel").value,
            id_funcionario: document.getElementById("usuario-funcionario").value || null,
        };

        const resp = await apiFetch("/api/usuarios", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(corpo),
        });
        const dados = await resp.json();

        mensagem.className = resp.ok ? "flash flash-sucesso" : "flash flash-erro";
        mensagem.textContent = resp.ok
            ? `Usuário "${dados.nome}" criado com sucesso!`
            : (dados.erro || "Erro ao criar usuário.");
        mensagem.style.display = "block";

        if (resp.ok) {
            document.getElementById("form-usuario").reset();
            _renderUsuarios();
        }
    });
}
