// Navegação por abas + listagem de funcionários + cadastro manual (admin.html).

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

async function _renderFuncionarios() {
    const resposta = await apiFetch("/api/funcionarios");
    const funcionarios = await resposta.json();

    const corpo = document.getElementById("tabela-funcionarios-corpo");
    corpo.innerHTML = funcionarios.map((f) => `
        <tr>
            <td>${f.nome}</td>
            <td>${f.cargo || "—"}</td>
            <td><span class="badge ${f.ativo ? "ativo" : "inativo"}">${f.ativo ? "Ativo" : "Inativo"}</span></td>
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
    `).join("") || `<tr><td colspan="4">Nenhum funcionário cadastrado.</td></tr>`;

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
}

function initFuncionarios() {
    _renderFuncionarios();
    document.querySelector('.tab-btn[data-tab="funcionarios"]').addEventListener("click", _renderFuncionarios);
}

async function initCadastroManual() {
    const resposta = await apiFetch("/api/areas");
    const areas = await resposta.json();

    const container = document.getElementById("cad-areas");
    container.innerHTML = areas.map((area) => `
        <label class="campo-checkbox">
            <input type="checkbox" name="cad-area" value="${area.id}"> ${area.nome}
        </label>
    `).join("") || "Nenhuma área cadastrada.";

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

        mensagem.className = resp.ok ? "flash flash-sucesso" : "flash flash-erro";
        mensagem.textContent = resp.ok
            ? `Funcionário "${dados.nome}" cadastrado com sucesso!`
            : (dados.erro || "Erro ao cadastrar funcionário.");
        mensagem.style.display = "block";

        if (resp.ok) {
            document.getElementById("form-cadastro-manual").reset();
        }
    });
}
