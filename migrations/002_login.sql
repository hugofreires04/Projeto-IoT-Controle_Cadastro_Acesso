-- Migration 002 — Login com permissões + cadastro via RFID + lista de acessos
-- ENG4051 — PUC-Rio
--
-- Evolui o schema original (a3_funcionarios.uid_cartao 1:1 + a3_logs_acesso/autorizado)
-- para o novo modelo: cartões RFID separados do funcionário, permissões por área,
-- usuários/sessões para login e a3_registros_acesso com motivo de negação detalhado.
-- Tabelas prefixadas com a3_ (grupo A3) por compartilhar o banco com a turma.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── Áreas físicas controladas por catraca/leitor ──────────────────────────
CREATE TABLE IF NOT EXISTS a3_areas (
  id          SERIAL PRIMARY KEY,
  nome        VARCHAR(100) UNIQUE NOT NULL,
  descricao   TEXT
);

INSERT INTO a3_areas (nome, descricao) VALUES
  ('Recepção', 'Entrada principal do prédio'),
  ('Laboratório', 'Sala de laboratório e equipamentos'),
  ('Datacenter', 'Sala de servidores e infraestrutura')
ON CONFLICT (nome) DO NOTHING;

-- ── Cartões RFID (separados do funcionário para permitir múltiplos cartões) ─
CREATE TABLE IF NOT EXISTS a3_cartoes_rfid (
  id              SERIAL PRIMARY KEY,
  uid             VARCHAR(30) UNIQUE NOT NULL,
  id_funcionario  INT REFERENCES a3_funcionarios(id) ON DELETE CASCADE,
  ativo           BOOLEAN DEFAULT TRUE
);

-- Migra o uid_cartao que hoje vive em a3_funcionarios para a nova tabela
INSERT INTO a3_cartoes_rfid (uid, id_funcionario, ativo)
SELECT uid_cartao, id, ativo FROM a3_funcionarios
ON CONFLICT (uid) DO NOTHING;

ALTER TABLE a3_funcionarios DROP COLUMN IF EXISTS uid_cartao;

-- ── Permissões por área (cartão x área) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS a3_permissoes (
  id_cartao   INT NOT NULL REFERENCES a3_cartoes_rfid(id) ON DELETE CASCADE,
  id_area     INT NOT NULL REFERENCES a3_areas(id) ON DELETE CASCADE,
  PRIMARY KEY (id_cartao, id_area)
);

-- ── Usuários do sistema (login no painel) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS a3_usuarios (
  id              SERIAL PRIMARY KEY,
  nome            VARCHAR(100) NOT NULL,
  email           VARCHAR(100) UNIQUE NOT NULL,
  senha_hash      VARCHAR(255) NOT NULL,
  nivel_acesso    VARCHAR(20) NOT NULL CHECK (nivel_acesso IN ('admin', 'operador')),
  id_funcionario  INT REFERENCES a3_funcionarios(id) ON DELETE SET NULL,
  criado_em       TIMESTAMP DEFAULT NOW()
);

-- ── Sessões (tokens de login, substituem Flask-Login/JWT) ─────────────────
CREATE TABLE IF NOT EXISTS a3_sessoes (
  token         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  id_usuario    INT NOT NULL REFERENCES a3_usuarios(id) ON DELETE CASCADE,
  nivel_acesso  VARCHAR(20) NOT NULL,
  criado_em     TIMESTAMP DEFAULT NOW(),
  expira_em     TIMESTAMP NOT NULL
);

-- ── Registros de acesso (substitui a3_logs_acesso, distingue tipos de negação) ─
CREATE TABLE IF NOT EXISTS a3_registros_acesso (
  id              SERIAL,
  uid             VARCHAR(30) NOT NULL,
  id_funcionario  INT REFERENCES a3_funcionarios(id) ON DELETE SET NULL,
  id_area         INT REFERENCES a3_areas(id) ON DELETE SET NULL,
  resultado       VARCHAR(30) NOT NULL DEFAULT 'negado_desconhecido'
    CHECK (resultado IN (
      'liberado',
      'negado_sem_permissao',
      'negado_inativo',
      'negado_desconhecido'
    )),
  data_hora       TIMESTAMP WITH TIME ZONE DEFAULT now(),
  PRIMARY KEY (data_hora, id)
);

SELECT create_hypertable('a3_registros_acesso', 'data_hora', if_not_exists => TRUE);

-- Migra o histórico de a3_logs_acesso (autorizado boolean) para o novo enum
INSERT INTO a3_registros_acesso (uid, id_funcionario, resultado, data_hora)
SELECT
  l.uid_cartao,
  f.id,
  CASE WHEN l.autorizado THEN 'liberado' ELSE 'negado_desconhecido' END,
  l.data_hora
FROM a3_logs_acesso l
LEFT JOIN a3_funcionarios f ON f.nome = l.nome_funcionario;

DROP TABLE IF EXISTS a3_logs_acesso;

CREATE INDEX IF NOT EXISTS idx_a3_registros_acesso_uid ON a3_registros_acesso (uid, data_hora DESC);
CREATE INDEX IF NOT EXISTS idx_a3_registros_acesso_funcionario ON a3_registros_acesso (id_funcionario, data_hora DESC);

-- ── Seed: usuário admin padrão ─────────────────────────────────────────────
-- O hash abaixo é um placeholder inválido — rode `python setup_admin.py` depois
-- da migration para gravar o hash bcrypt real da senha do admin.
INSERT INTO a3_usuarios (nome, email, senha_hash, nivel_acesso)
VALUES (
  'Administrador',
  'admin@sistema.com',
  '$2b$12$PLACEHOLDER_HASH_RODAR_SETUP_ADMIN_PY_______________',
  'admin'
) ON CONFLICT (email) DO NOTHING;
