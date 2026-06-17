// Funções compartilhadas de autenticação (token salvo no localStorage).

function obterToken() {
    return localStorage.getItem("token");
}

function obterNivel() {
    return localStorage.getItem("nivel");
}

function obterNome() {
    return localStorage.getItem("nome");
}

function salvarSessao(dados) {
    localStorage.setItem("token", dados.token);
    localStorage.setItem("nivel", dados.nivel);
    localStorage.setItem("nome", dados.nome);
}

function limparSessao() {
    localStorage.removeItem("token");
    localStorage.removeItem("nivel");
    localStorage.removeItem("nome");
}

function exigirLogin() {
    if (!obterToken()) {
        window.location.href = "/static/login.html";
    }
}

async function apiFetch(url, opcoes = {}) {
    opcoes.headers = Object.assign({}, opcoes.headers, { Authorization: "Bearer " + obterToken() });
    const resposta = await fetch(url, opcoes);
    if (resposta.status === 401) {
        limparSessao();
        window.location.href = "/static/login.html";
        throw new Error("Não autorizado");
    }
    return resposta;
}

async function sair() {
    try {
        await apiFetch("/api/logout", { method: "POST" });
    } finally {
        limparSessao();
        window.location.href = "/static/login.html";
    }
}

function configurarHeaderUsuario() {
    const elNome = document.getElementById("header-usuario-nome");
    if (elNome) elNome.textContent = obterNome() || "";

    const btnSair = document.getElementById("btn-sair");
    if (btnSair) btnSair.addEventListener("click", sair);
}
