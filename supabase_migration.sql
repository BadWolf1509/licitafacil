-- =============================================================================
-- SCHEMA POSTGRESQL PARA SUPABASE - LicitaFácil
-- =============================================================================
-- Sistema de Análise de Capacidade Técnica para Licitações
-- Migração de SQLite para Supabase (PostgreSQL)
-- =============================================================================

-- Habilitar extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- 1. TABELA: usuarios
-- =============================================================================
-- Usuários do sistema com autenticação e controle de acesso

CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL,
    nome VARCHAR(255) NOT NULL,

    -- Flags de permissão
    is_admin BOOLEAN DEFAULT FALSE,
    is_approved BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,

    -- Preferências
    tema_preferido VARCHAR(10) DEFAULT 'light',  -- 'light' ou 'dark'

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    approved_by INTEGER REFERENCES usuarios(id)
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);
CREATE INDEX IF NOT EXISTS idx_usuarios_is_approved ON usuarios(is_approved);
CREATE INDEX IF NOT EXISTS idx_usuarios_is_admin ON usuarios(is_admin);

-- =============================================================================
-- 2. TABELA: atestados
-- =============================================================================
-- Atestados de capacidade técnica cadastrados pelos usuários

CREATE TABLE IF NOT EXISTS atestados (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,

    -- Dados do atestado
    descricao_servico TEXT NOT NULL,
    quantidade NUMERIC(15, 4),
    unidade VARCHAR(20),

    -- Informações do contratante
    contratante VARCHAR(255),
    data_emissao TIMESTAMP,

    -- Arquivos e extração
    arquivo_path VARCHAR(500),
    texto_extraido TEXT,
    servicos_json JSONB,  -- Lista de serviços extraídos do documento

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_atestados_user_id ON atestados(user_id);
CREATE INDEX IF NOT EXISTS idx_atestados_contratante ON atestados(contratante);
CREATE INDEX IF NOT EXISTS idx_atestados_created_at ON atestados(created_at);

-- Índice GIN para busca em JSON
CREATE INDEX IF NOT EXISTS idx_atestados_servicos ON atestados USING GIN (servicos_json);

-- =============================================================================
-- 3. TABELA: analises
-- =============================================================================
-- Análises de licitações comparando exigências com atestados disponíveis

CREATE TABLE IF NOT EXISTS analises (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,

    -- Dados da licitação
    nome_licitacao VARCHAR(255) NOT NULL,
    arquivo_path VARCHAR(500),

    -- Exigências e resultados em JSON
    exigencias_json JSONB,  -- Lista de exigências extraídas do edital
    resultado_json JSONB,   -- Resultado do matching entre exigências e atestados

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_analises_user_id ON analises(user_id);
CREATE INDEX IF NOT EXISTS idx_analises_nome_licitacao ON analises(nome_licitacao);
CREATE INDEX IF NOT EXISTS idx_analises_created_at ON analises(created_at);

-- Índices GIN para busca em JSON
CREATE INDEX IF NOT EXISTS idx_analises_exigencias ON analises USING GIN (exigencias_json);
CREATE INDEX IF NOT EXISTS idx_analises_resultado ON analises USING GIN (resultado_json);

-- =============================================================================
-- 4. TABELA: processing_jobs
-- =============================================================================
-- Fila de processamento de documentos (OCR, extração de dados)

CREATE TABLE IF NOT EXISTS processing_jobs (
    id TEXT PRIMARY KEY,  -- UUID como texto para compatibilidade
    user_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,

    -- Arquivo
    file_path TEXT NOT NULL,
    original_filename TEXT,

    -- Tipo e status
    job_type VARCHAR(50) NOT NULL DEFAULT 'atestado',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- status: pending, processing, completed, failed, cancelled

    -- Timestamps
    created_at TEXT NOT NULL,  -- ISO format com timezone
    started_at TEXT,
    completed_at TEXT,
    canceled_at TEXT,

    -- Resultado e erros
    result JSONB,
    error TEXT,

    -- Controle de tentativas
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,

    -- Progresso
    progress_current INTEGER DEFAULT 0,
    progress_total INTEGER DEFAULT 0,
    progress_stage VARCHAR(100),
    progress_message TEXT,

    -- Pipeline utilizado
    pipeline VARCHAR(50)
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON processing_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON processing_jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON processing_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_pending ON processing_jobs(status) WHERE status IN ('pending', 'processing');

-- =============================================================================
-- 5. TRIGGERS DE ATUALIZAÇÃO
-- =============================================================================

-- Função para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para atestados
DROP TRIGGER IF EXISTS update_atestados_updated_at ON atestados;
CREATE TRIGGER update_atestados_updated_at
    BEFORE UPDATE ON atestados
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- 6. ROW LEVEL SECURITY (RLS) - DESABILITADO
-- =============================================================================
-- NOTA: O LicitaFácil usa autenticação JWT própria (não Supabase Auth).
-- O controle de acesso é feito pela aplicação backend.
-- RLS está desabilitado para permitir acesso via service_role key.

-- Se quiser habilitar RLS no futuro com Supabase Auth, descomente:
-- ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE atestados ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE analises ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- 7. FUNÇÕES AUXILIARES
-- =============================================================================

-- Função para obter estatísticas de jobs por usuário
CREATE OR REPLACE FUNCTION get_job_stats(p_user_id INTEGER DEFAULT NULL)
RETURNS TABLE(
    total BIGINT,
    pending BIGINT,
    processing BIGINT,
    completed BIGINT,
    failed BIGINT,
    cancelled BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total,
        COUNT(*) FILTER (WHERE status = 'pending')::BIGINT as pending,
        COUNT(*) FILTER (WHERE status = 'processing')::BIGINT as processing,
        COUNT(*) FILTER (WHERE status = 'completed')::BIGINT as completed,
        COUNT(*) FILTER (WHERE status = 'failed')::BIGINT as failed,
        COUNT(*) FILTER (WHERE status = 'cancelled')::BIGINT as cancelled
    FROM processing_jobs
    WHERE p_user_id IS NULL OR user_id = p_user_id;
END;
$$ LANGUAGE plpgsql;

-- Função para buscar atestados por texto
CREATE OR REPLACE FUNCTION search_atestados(
    p_user_id INTEGER,
    p_query TEXT
)
RETURNS TABLE(
    id INTEGER,
    descricao_servico TEXT,
    contratante VARCHAR(255),
    quantidade NUMERIC(15,4),
    unidade VARCHAR(20),
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id,
        a.descricao_servico,
        a.contratante,
        a.quantidade,
        a.unidade,
        a.created_at
    FROM atestados a
    WHERE a.user_id = p_user_id
      AND (
          a.descricao_servico ILIKE '%' || p_query || '%'
          OR a.contratante ILIKE '%' || p_query || '%'
          OR a.texto_extraido ILIKE '%' || p_query || '%'
      )
    ORDER BY a.created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 8. SEED DO ADMIN (ajustar senha em produção!)
-- =============================================================================
-- IMPORTANTE: Altere a senha antes de usar em produção!

-- INSERT INTO usuarios (email, senha_hash, nome, is_admin, is_approved, is_active)
-- VALUES (
--     'admin@licitafacil.com.br',
--     '$2b$12$...',  -- Hash bcrypt da senha
--     'Administrador',
--     true,
--     true,
--     true
-- )
-- ON CONFLICT (email) DO NOTHING;

-- =============================================================================
-- RESUMO DAS TABELAS
-- =============================================================================
--
-- usuarios (4 tabelas no total):
--   - Autenticação e perfil do usuário
--   - Controle de acesso (admin, approved, active)
--   - Auto-referência para approved_by
--
-- atestados:
--   - Documentos de capacidade técnica
--   - Serviços em JSON para múltiplos itens
--   - Texto OCR extraído para busca
--
-- analises:
--   - Análises de editais de licitação
--   - Exigências e resultados em JSON
--
-- processing_jobs:
--   - Fila de processamento assíncrono
--   - Controle de status e progresso
--   - Retry com limite de tentativas
--
-- =============================================================================
