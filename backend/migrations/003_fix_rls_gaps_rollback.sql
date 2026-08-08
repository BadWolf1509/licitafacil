-- =============================================================================
-- ROLLBACK da Migração 003: reverter RLS e privilégios
-- =============================================================================
-- ATENÇÃO — LEIA ANTES DE EXECUTAR
--
-- Este script REABRE a falha que a 003 fechou. Ao restaurar os grants do papel
-- `anon`, as tabelas voltam a ficar legíveis, alteráveis e apagáveis por
-- qualquer pessoa que tenha a chave anônima — que é servida publicamente por
-- GET /auth/config, sem autenticação.
--
-- Use apenas se a 003 tiver quebrado algo em produção e você precisar de um
-- retorno imediato ao estado anterior. Neste caso, prefira reverter só a parte
-- responsável pela quebra (as seções abaixo são independentes) em vez de rodar
-- o arquivo inteiro.
--
-- Ordem inversa à da migração: primeiro as políticas, os grants por último.
-- =============================================================================


-- =============================================================================
-- REVERTE PARTE 8: política permissiva em audit_logs
-- =============================================================================
-- Recria a política da 002. Só faça isso se algo depender de INSERT em
-- audit_logs por um papel que não seja o owner — a aplicação não depende.

DROP POLICY IF EXISTS audit_insert_system ON public.audit_logs;
CREATE POLICY audit_insert_system ON public.audit_logs
    FOR INSERT
    WITH CHECK (true);


-- =============================================================================
-- REVERTE PARTE 6: funções
-- =============================================================================

ALTER FUNCTION public.get_local_user_id()               RESET search_path;
ALTER FUNCTION public.is_current_user_admin()           RESET search_path;
ALTER FUNCTION public.update_updated_at_column()        RESET search_path;
ALTER FUNCTION public.get_job_stats(integer)            RESET search_path;
ALTER FUNCTION public.search_atestados(integer, text)   RESET search_path;

-- Devolve o EXECUTE a PUBLIC (era o estado padrão do Postgres antes da 003).
GRANT EXECUTE ON FUNCTION public.get_local_user_id()             TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_current_user_admin()         TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_job_stats(integer)          TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.search_atestados(integer, text) TO PUBLIC;


-- =============================================================================
-- REVERTE PARTE 5: alembic_version
-- =============================================================================

ALTER TABLE public.alembic_version DISABLE ROW LEVEL SECURITY;
GRANT ALL ON public.alembic_version TO authenticated;


-- =============================================================================
-- REVERTE PARTE 4: licitacao_tags
-- =============================================================================

DROP POLICY IF EXISTS licitacao_tags_select_own   ON public.licitacao_tags;
DROP POLICY IF EXISTS licitacao_tags_admin_select ON public.licitacao_tags;
DROP POLICY IF EXISTS licitacao_tags_insert_own   ON public.licitacao_tags;
DROP POLICY IF EXISTS licitacao_tags_update_own   ON public.licitacao_tags;
DROP POLICY IF EXISTS licitacao_tags_delete_own   ON public.licitacao_tags;
DROP POLICY IF EXISTS licitacao_tags_admin_all    ON public.licitacao_tags;

ALTER TABLE public.licitacao_tags DISABLE ROW LEVEL SECURITY;


-- =============================================================================
-- REVERTE PARTE 3: as 9 tabelas com user_id
-- =============================================================================
-- Mesmo laço da migração, no sentido inverso.

DO $$
DECLARE
    t TEXT;
    sufixo TEXT;
    tabelas TEXT[] := ARRAY[
        'licitacoes',
        'licitacao_historico',
        'documentos_licitacao',
        'checklist_edital',
        'lembretes',
        'notificacoes',
        'preferencias_notificacao',
        'pncp_monitoramentos',
        'pncp_resultados'
    ];
    sufixos TEXT[] := ARRAY[
        '_select_own', '_admin_select', '_insert_own',
        '_update_own', '_delete_own', '_admin_all'
    ];
BEGIN
    FOREACH t IN ARRAY tabelas LOOP
        FOREACH sufixo IN ARRAY sufixos LOOP
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || sufixo, t);
        END LOOP;

        EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', t);

        RAISE NOTICE 'RLS e políticas removidas de %', t;
    END LOOP;
END $$;


-- =============================================================================
-- REVERTE PARTES 1 e 2: grants do `anon`
-- =============================================================================
-- É AQUI que a falha reabre. Se você só precisa desfazer o RLS, pare acima e
-- não execute este bloco — as tabelas continuam protegidas pela ausência de
-- grants, que é a camada que realmente barra o acesso público.

-- (O schema USAGE nunca foi revogado — vinha de PUBLIC, não de um grant ao
-- anon. Ver a nota na Parte 1 da migração. Nada a restaurar aqui.)
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT ALL ON FUNCTIONS TO anon;


-- =============================================================================
-- VERIFICAÇÃO DO ROLLBACK
-- =============================================================================
-- Esperado após o arquivo completo: as 11 tabelas da 003 com rls_on = false,
-- policies = 0 e anon_ainda_le = true (ou seja, de volta ao estado vulnerável).
-- As 5 tabelas da 002 devem permanecer com rls_on = true — esta migração não
-- as toca.

SELECT c.relname AS tabela,
       c.relrowsecurity AS rls_on,
       (SELECT COUNT(*) FROM pg_policy p WHERE p.polrelid = c.oid) AS policies,
       has_table_privilege('anon', c.oid, 'SELECT') AS anon_ainda_le
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY c.relrowsecurity, c.relname;
