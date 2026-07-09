-- Schema do banco de dados para o sistema de controle de acesso via RFID
-- ENG4051 — PUC-Rio
-- Tabelas prefixadas com a3_ (grupo A3) por compartilhar o banco com a turma

-- Tabela de funcionários
CREATE TABLE IF NOT EXISTS a3_funcionarios (
    id              SERIAL PRIMARY KEY,
    nome            VARCHAR(100) NOT NULL,
    uid_cartao      VARCHAR(30) UNIQUE NOT NULL,
    cargo           VARCHAR(100),
    ativo           BOOLEAN DEFAULT TRUE,
    criado_em       TIMESTAMP WITH TIME ZONE DEFAULT now(),
    atualizado_em   TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Hipertabela de logs de acesso (TimescaleDB)
CREATE TABLE IF NOT EXISTS a3_logs_acesso (
    data_hora           TIMESTAMP WITH TIME ZONE DEFAULT now(),
    uid_cartao          VARCHAR(30),
    nome_funcionario    VARCHAR(100),
    tipo                VARCHAR(10),   -- 'entrada' ou 'saida'
    autorizado          BOOLEAN,
    PRIMARY KEY (data_hora, uid_cartao)
);

SELECT create_hypertable('a3_logs_acesso', 'data_hora', if_not_exists => TRUE);

-- Dados de exemplo para facilitar os testes
INSERT INTO a3_funcionarios (nome, uid_cartao, cargo, ativo) VALUES
    ('João Silva',    'E7 45 D6 19', 'Analista de Sistemas', TRUE),
    ('Maria Oliveira','A3 BC 12 F0', 'Engenheira de Hardware', TRUE),
    ('Carlos Souza',  '7F 2A 98 3C', 'Estagiário', FALSE)
ON CONFLICT (uid_cartao) DO NOTHING;

-- Índice para consultas de log por funcionário
CREATE INDEX IF NOT EXISTS idx_a3_logs_uid_cartao ON a3_logs_acesso (uid_cartao, data_hora DESC);
