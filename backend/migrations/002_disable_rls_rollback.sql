-- =============================================================================
-- ROLLBACK: Desabilitar Row Level Security (RLS)
-- =============================================================================
-- Use este script para reverter as políticas RLS se houver problemas.
-- ATENÇÃO: Isso remove TODA a proteção RLS das tabelas!
-- =============================================================================

-- Remover políticas da tabela usuarios
DROP POLICY IF EXISTS usuarios_select_own ON usuarios;
DROP POLICY IF EXISTS usuarios_admin_select ON usuarios;
DROP POLICY IF EXISTS usuarios_update_own ON usuarios;
DROP POLICY IF EXISTS usuarios_admin_update ON usuarios;

-- Remover políticas da tabela atestados
DROP POLICY IF EXISTS atestados_select_own ON atestados;
DROP POLICY IF EXISTS atestados_admin_select ON atestados;
DROP POLICY IF EXISTS atestados_insert_own ON atestados;
DROP POLICY IF EXISTS atestados_update_own ON atestados;
DROP POLICY IF EXISTS atestados_delete_own ON atestados;
DROP POLICY IF EXISTS atestados_admin_all ON atestados;

-- Remover políticas da tabela analises
DROP POLICY IF EXISTS analises_select_own ON analises;
DROP POLICY IF EXISTS analises_admin_select ON analises;
DROP POLICY IF EXISTS analises_insert_own ON analises;
DROP POLICY IF EXISTS analises_update_own ON analises;
DROP POLICY IF EXISTS analises_delete_own ON analises;
DROP POLICY IF EXISTS analises_admin_all ON analises;

-- Remover políticas da tabela processing_jobs
DROP POLICY IF EXISTS jobs_select_own ON processing_jobs;
DROP POLICY IF EXISTS jobs_admin_select ON processing_jobs;
DROP POLICY IF EXISTS jobs_insert_own ON processing_jobs;
DROP POLICY IF EXISTS jobs_update_own ON processing_jobs;
DROP POLICY IF EXISTS jobs_admin_all ON processing_jobs;

-- Remover políticas da tabela audit_logs
DROP POLICY IF EXISTS audit_admin_only ON audit_logs;
DROP POLICY IF EXISTS audit_insert_system ON audit_logs;

-- Desabilitar RLS nas tabelas
ALTER TABLE usuarios DISABLE ROW LEVEL SECURITY;
ALTER TABLE atestados DISABLE ROW LEVEL SECURITY;
ALTER TABLE analises DISABLE ROW LEVEL SECURITY;
ALTER TABLE processing_jobs DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY;

-- Remover funções auxiliares
DROP FUNCTION IF EXISTS get_local_user_id();
DROP FUNCTION IF EXISTS is_current_user_admin();

-- Verificar que RLS foi desabilitado
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN ('usuarios', 'atestados', 'analises', 'processing_jobs', 'audit_logs');
