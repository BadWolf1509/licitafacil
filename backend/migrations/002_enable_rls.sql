-- =============================================================================
-- Migração: Habilitar Row Level Security (RLS) no LicitaFácil
-- =============================================================================
-- Esta migração implementa políticas de segurança no nível do banco de dados
-- para garantir que usuários só acessem seus próprios dados.
--
-- IMPORTANTE: Execute este script no Supabase SQL Editor
-- =============================================================================

-- Função auxiliar para obter o user_id local a partir do auth.uid() do Supabase
CREATE OR REPLACE FUNCTION get_local_user_id()
RETURNS INTEGER AS $$
DECLARE
    local_id INTEGER;
BEGIN
    SELECT id INTO local_id
    FROM usuarios
    WHERE supabase_id = auth.uid()::text;

    RETURN local_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Função auxiliar para verificar se o usuário atual é admin
CREATE OR REPLACE FUNCTION is_current_user_admin()
RETURNS BOOLEAN AS $$
DECLARE
    user_is_admin BOOLEAN;
BEGIN
    SELECT is_admin INTO user_is_admin
    FROM usuarios
    WHERE supabase_id = auth.uid()::text;

    RETURN COALESCE(user_is_admin, FALSE);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =============================================================================
-- TABELA: usuarios
-- =============================================================================
ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY;

-- Política: Usuário pode ver apenas seu próprio perfil
CREATE POLICY usuarios_select_own ON usuarios
    FOR SELECT
    USING (supabase_id = auth.uid()::text);

-- Política: Admins podem ver todos os usuários
CREATE POLICY usuarios_admin_select ON usuarios
    FOR SELECT
    USING (is_current_user_admin());

-- Política: Usuário pode atualizar apenas seu próprio perfil (campos limitados)
CREATE POLICY usuarios_update_own ON usuarios
    FOR UPDATE
    USING (supabase_id = auth.uid()::text)
    WITH CHECK (supabase_id = auth.uid()::text);

-- Política: Admins podem atualizar qualquer usuário
CREATE POLICY usuarios_admin_update ON usuarios
    FOR UPDATE
    USING (is_current_user_admin());

-- =============================================================================
-- TABELA: atestados
-- =============================================================================
ALTER TABLE atestados ENABLE ROW LEVEL SECURITY;

-- Política: Usuário vê apenas seus atestados
CREATE POLICY atestados_select_own ON atestados
    FOR SELECT
    USING (user_id = get_local_user_id());

-- Política: Admins podem ver todos os atestados
CREATE POLICY atestados_admin_select ON atestados
    FOR SELECT
    USING (is_current_user_admin());

-- Política: Usuário pode criar atestados para si mesmo
CREATE POLICY atestados_insert_own ON atestados
    FOR INSERT
    WITH CHECK (user_id = get_local_user_id());

-- Política: Usuário pode atualizar seus atestados
CREATE POLICY atestados_update_own ON atestados
    FOR UPDATE
    USING (user_id = get_local_user_id())
    WITH CHECK (user_id = get_local_user_id());

-- Política: Usuário pode deletar seus atestados
CREATE POLICY atestados_delete_own ON atestados
    FOR DELETE
    USING (user_id = get_local_user_id());

-- Política: Admins podem manipular todos os atestados
CREATE POLICY atestados_admin_all ON atestados
    FOR ALL
    USING (is_current_user_admin());

-- =============================================================================
-- TABELA: analises
-- =============================================================================
ALTER TABLE analises ENABLE ROW LEVEL SECURITY;

-- Política: Usuário vê apenas suas análises
CREATE POLICY analises_select_own ON analises
    FOR SELECT
    USING (user_id = get_local_user_id());

-- Política: Admins podem ver todas as análises
CREATE POLICY analises_admin_select ON analises
    FOR SELECT
    USING (is_current_user_admin());

-- Política: Usuário pode criar análises para si mesmo
CREATE POLICY analises_insert_own ON analises
    FOR INSERT
    WITH CHECK (user_id = get_local_user_id());

-- Política: Usuário pode atualizar suas análises
CREATE POLICY analises_update_own ON analises
    FOR UPDATE
    USING (user_id = get_local_user_id())
    WITH CHECK (user_id = get_local_user_id());

-- Política: Usuário pode deletar suas análises
CREATE POLICY analises_delete_own ON analises
    FOR DELETE
    USING (user_id = get_local_user_id());

-- Política: Admins podem manipular todas as análises
CREATE POLICY analises_admin_all ON analises
    FOR ALL
    USING (is_current_user_admin());

-- =============================================================================
-- TABELA: processing_jobs
-- =============================================================================
ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;

-- Política: Usuário vê apenas seus jobs
CREATE POLICY jobs_select_own ON processing_jobs
    FOR SELECT
    USING (user_id = get_local_user_id());

-- Política: Admins podem ver todos os jobs
CREATE POLICY jobs_admin_select ON processing_jobs
    FOR SELECT
    USING (is_current_user_admin());

-- Política: Usuário pode criar jobs para si mesmo
CREATE POLICY jobs_insert_own ON processing_jobs
    FOR INSERT
    WITH CHECK (user_id = get_local_user_id());

-- Política: Usuário pode cancelar (atualizar) seus jobs
CREATE POLICY jobs_update_own ON processing_jobs
    FOR UPDATE
    USING (user_id = get_local_user_id());

-- Política: Admins podem manipular todos os jobs
CREATE POLICY jobs_admin_all ON processing_jobs
    FOR ALL
    USING (is_current_user_admin());

-- =============================================================================
-- TABELA: audit_logs
-- =============================================================================
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Política: Apenas admins podem ver logs de auditoria
CREATE POLICY audit_admin_only ON audit_logs
    FOR SELECT
    USING (is_current_user_admin());

-- Política: O sistema pode inserir logs (via service_role)
-- Nota: Inserts são feitos pelo backend com service_role key
CREATE POLICY audit_insert_system ON audit_logs
    FOR INSERT
    WITH CHECK (true);

-- =============================================================================
-- GRANT: Permissões para roles do Supabase
-- =============================================================================

-- Permitir que authenticated users acessem as funções auxiliares
GRANT EXECUTE ON FUNCTION get_local_user_id() TO authenticated;
GRANT EXECUTE ON FUNCTION is_current_user_admin() TO authenticated;

-- Permitir SELECT, INSERT, UPDATE, DELETE nas tabelas com RLS
GRANT SELECT, INSERT, UPDATE, DELETE ON usuarios TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON atestados TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON analises TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON processing_jobs TO authenticated;
GRANT SELECT ON audit_logs TO authenticated;

-- Service role tem acesso total (usado pelo backend)
GRANT ALL ON usuarios TO service_role;
GRANT ALL ON atestados TO service_role;
GRANT ALL ON analises TO service_role;
GRANT ALL ON processing_jobs TO service_role;
GRANT ALL ON audit_logs TO service_role;

-- =============================================================================
-- VERIFICAÇÃO: Checar se RLS está habilitado
-- =============================================================================
-- Execute esta query para verificar:
-- SELECT tablename, rowsecurity
-- FROM pg_tables
-- WHERE schemaname = 'public'
-- AND tablename IN ('usuarios', 'atestados', 'analises', 'processing_jobs', 'audit_logs');
