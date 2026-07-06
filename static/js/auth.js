// auth.js — Funções compartilhadas de autenticação, incluídas em todas as páginas.
//
// Como funciona a sessão:
//   1. O login (POST /api/login) devolve um token UUID gravado em a3_sessoes no banco.
//   2. O token (+ nome e nível do usuário) fica salvo no localStorage do navegador.
//   3. Toda chamada à API passa o token no header "Authorization: Bearer <token>".
//   4. O backend valida o token e a expiração a cada requisição (ver auth.py).
//   5. Se qualquer chamada devolver 401 (token expirado/inválido), a sessão local
//      é limpa e o usuário volta para a tela de login.

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

// Chamado no topo das páginas protegidas: sem token, volta pro login.
function exigirLogin() {
    if (!obterToken()) {
        window.location.href = "/static/login.html";
    }
}

// Wrapper do fetch() usado em TODAS as chamadas à API: injeta o token no
// header Authorization e trata o 401 de forma centralizada (logout forçado).
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

// Logout: invalida a sessão no servidor (DELETE em a3_sessoes) e limpa o
// localStorage mesmo que a chamada falhe (finally) — o usuário sempre sai.
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
