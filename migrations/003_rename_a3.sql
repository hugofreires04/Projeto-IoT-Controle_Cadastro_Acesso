-- Migration 003 — Renomeia para o prefixo a3_ as tabelas que já existem no banco
-- ENG4051 — PUC-Rio
--
-- O commit "Prefixa tabelas do banco com a3_" trocou os nomes nas queries do
-- código (routes/acessos.py etc.) e em database/schema.sql/migrations/002_login.sql,
-- mas não renomeou as tabelas que já tinham sido criadas no banco compartilhado
-- da turma antes desse commit. Sem isso, o código passa a consultar
-- a3_cartoes_rfid/a3_registros_acesso/etc. que não existem, e toda chamada do
-- Node-RED (GET /api/acesso/<uid>, POST /api/acesso/log) falha com erro 500.
--
-- Cada rename é IF EXISTS para ser seguro de rodar tanto num banco que ainda
-- está com os nomes antigos quanto num banco que já foi criado direto com
-- schema.sql/002_login.sql já atualizados (onde os a3_* já existem e os
-- ALTER TABLE abaixo simplesmente não encontram nada para renomear).

ALTER TABLE IF EXISTS funcionarios     RENAME TO a3_funcionarios;
ALTER TABLE IF EXISTS logs_acesso      RENAME TO a3_logs_acesso;
ALTER TABLE IF EXISTS areas            RENAME TO a3_areas;
ALTER TABLE IF EXISTS cartoes_rfid     RENAME TO a3_cartoes_rfid;
ALTER TABLE IF EXISTS permissoes       RENAME TO a3_permissoes;
ALTER TABLE IF EXISTS usuarios         RENAME TO a3_usuarios;
ALTER TABLE IF EXISTS sessoes          RENAME TO a3_sessoes;
ALTER TABLE IF EXISTS registros_acesso RENAME TO a3_registros_acesso;

ALTER INDEX IF EXISTS idx_logs_uid_cartao             RENAME TO idx_a3_logs_uid_cartao;
ALTER INDEX IF EXISTS idx_registros_acesso_uid         RENAME TO idx_a3_registros_acesso_uid;
ALTER INDEX IF EXISTS idx_registros_acesso_funcionario RENAME TO idx_a3_registros_acesso_funcionario;
