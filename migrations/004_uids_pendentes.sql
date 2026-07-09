-- Migration 004 — Fila de UIDs pendentes de cadastro via leitura na catraca
-- ENG4051 — PUC-Rio
--
-- Quando um admin usa o próprio cartão na catraca (GET /api/acesso/<uid> retorna
-- isAdmin=true), o firmware entra em modo de cadastro: a próxima leitura de
-- cartão (da pessoa a ser cadastrada) é publicada no tópico MQTT a3/cadastros
-- em vez de a3/catraca/entrada. O Node-RED repassa esse UID para o Flask
-- (POST /api/cadastros/uid-pendente), que guarda aqui até o admin completar
-- o cadastro manual (ou descartar) na aba "Cadastrar" do admin.html.

CREATE TABLE IF NOT EXISTS a3_uids_pendentes (
  id          SERIAL PRIMARY KEY,
  uid         VARCHAR(30) NOT NULL,
  recebido_em TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_a3_uids_pendentes_recebido_em ON a3_uids_pendentes (recebido_em DESC);
