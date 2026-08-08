-- =============================================================================
-- Migração 003: Fechar lacunas de RLS e revogar acesso público (anon)
-- =============================================================================
-- CONTEXTO
-- A migração 002 habilitou RLS em usuarios, atestados, analises, processing_jobs
-- e audit_logs — as cinco tabelas que existiam naquele momento. Todas as tabelas
-- criadas depois (módulo de licitações, PNCP, notificações) nasceram sem RLS.
--
-- Como o Supabase concede por padrão SELECT/INSERT/UPDATE/DELETE aos papéis
-- `anon` e `authenticated` em todo o schema public, e a chave anônima é servida
-- publicamente por GET /auth/config, qualquer pessoa na internet podia ler,
-- alterar e apagar as linhas dessas tabelas via PostgREST.
--
-- Diagnóstico completo em: Security Advisor (11 erros + 41 warnings).
--
-- O QUE ESTA MIGRAÇÃO FAZ
--   Parte 1 — revoga todo acesso do papel `anon` no schema public
--   Parte 2 — corrige os privilégios padrão para tabelas futuras
--   Parte 3 — habilita RLS + políticas nas 9 tabelas com coluna user_id
--   Parte 4 — habilita RLS em licitacao_tags (posse derivada de licitacoes)
--   Parte 5 — habilita RLS em alembic_version (nega tudo: tabela de infra)
--   Parte 6 — fixa search_path das funções e revoga EXECUTE do `anon`
--
-- POR QUE ISSO NÃO QUEBRA O BACKEND
-- O FastAPI conecta via DATABASE_URL com o papel `postgres`, que é OWNER das
-- tabelas. No PostgreSQL o owner ignora RLS (salvo FORCE ROW LEVEL SECURITY,
-- que não é usado aqui). Foi por isso que a 002 não quebrou nada, e vale igual.
--
-- O papel `authenticated` mantém os grants que já tinha — a diferença é que
-- agora estão devidamente barrados por RLS, que era a intenção original da 002.
-- O frontend hoje não consulta tabelas via PostgREST (só auth.getSession e
-- auth.signOut), então nada depende desses grants na prática.
--
-- IMPORTANTE: Execute este script no Supabase SQL Editor.
-- Rollback em: 003_fix_rls_gaps_rollback.sql
-- =============================================================================


-- =============================================================================
-- PARTE 1: Revogar todo acesso do papel `anon`
-- =============================================================================
-- O `anon` é o papel pré-login. Ele só precisa falar com o Supabase Auth,
-- nunca com as tabelas da aplicação. Este bloco é o que fecha o vetor.

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon;

-- ATENÇÃO — armadilha verificada em produção:
-- `REVOKE ALL ON ALL FUNCTIONS ... FROM anon` e
-- `REVOKE USAGE ON SCHEMA public FROM anon` são NO-OP aqui.
-- Nos dois casos o privilégio não vem de um grant ao `anon`: vem de PUBLIC.
-- A ACL das funções é {=X/postgres, postgres=X/..., authenticated=X/...} — o
-- `=X` inicial (grantee vazio) é justamente o PUBLIC. Revogar de `anon` não
-- toca nele, e has_function_privilege('anon', ...) continua true.
-- O revoke correto está na Parte 6b, contra PUBLIC.
--
-- Já nas TABELAS o revoke acima funciona, porque ali o Supabase concede
-- explicitamente ao `anon` (anon=arwdDxtm/postgres) — e é esse grant explícito
-- que abria o buraco.


-- =============================================================================
-- PARTE 2: Corrigir privilégios padrão (impede a falha de voltar)
-- =============================================================================
-- Sem isto, toda tabela nova criada pelo Alembic volta a nascer acessível ao
-- `anon`, que é exatamente como as 11 tabelas ficaram expostas.
-- O papel `postgres` é quem cria os objetos (via DATABASE_URL / Alembic).

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON TABLES FROM anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON FUNCTIONS FROM anon;

-- NOTA: existe um segundo conjunto de privilégios padrão pertencente a
-- `supabase_admin`, que o papel `postgres` não tem permissão para alterar.
-- Ele só se aplica a objetos criados POR `supabase_admin` — nenhuma tabela da
-- aplicação se enquadra, já que o Alembic roda como `postgres`.


-- =============================================================================
-- PARTE 3: RLS + políticas nas 9 tabelas com coluna user_id
-- =============================================================================
-- Segue exatamente o padrão de nomes e predicados da 002
-- (<tabela>_select_own, _admin_select, _insert_own, _update_own, _delete_own,
-- _admin_all), usando os mesmos helpers get_local_user_id() e
-- is_current_user_admin().
--
-- Usa um laço em vez de 54 blocos copiados: o predicado fica declarado em um
-- lugar só, o que torna a revisão viável e elimina erro de copy-paste.

DO $$
DECLARE
    t TEXT;
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
BEGIN
    FOREACH t IN ARRAY tabelas LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);

        -- SELECT: usuário vê apenas o que é seu
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_select_own', t);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR SELECT
             USING (user_id = get_local_user_id())',
            t || '_select_own', t);

        -- SELECT: admin vê tudo
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_admin_select', t);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR SELECT
             USING (is_current_user_admin())',
            t || '_admin_select', t);

        -- INSERT: só para si mesmo
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_insert_own', t);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR INSERT
             WITH CHECK (user_id = get_local_user_id())',
            t || '_insert_own', t);

        -- UPDATE: só o que é seu, e não pode transferir para outro usuário
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_update_own', t);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR UPDATE
             USING (user_id = get_local_user_id())
             WITH CHECK (user_id = get_local_user_id())',
            t || '_update_own', t);

        -- DELETE: só o que é seu
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_delete_own', t);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR DELETE
             USING (user_id = get_local_user_id())',
            t || '_delete_own', t);

        -- ALL: admin manipula tudo
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_admin_all', t);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR ALL
             USING (is_current_user_admin())',
            t || '_admin_all', t);

        RAISE NOTICE 'RLS + 6 políticas aplicadas em %', t;
    END LOOP;
END $$;


-- =============================================================================
-- PARTE 4: licitacao_tags (posse derivada)
-- =============================================================================
-- Estrutura: id, licitacao_id, tag. Não tem user_id — a posse vem da licitação
-- referenciada, então o predicado é um EXISTS contra licitacoes.

ALTER TABLE public.licitacao_tags ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS licitacao_tags_select_own ON public.licitacao_tags;
CREATE POLICY licitacao_tags_select_own ON public.licitacao_tags
    FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM licitacoes l
        WHERE l.id = licitacao_tags.licitacao_id
          AND l.user_id = get_local_user_id()
    ));

DROP POLICY IF EXISTS licitacao_tags_admin_select ON public.licitacao_tags;
CREATE POLICY licitacao_tags_admin_select ON public.licitacao_tags
    FOR SELECT
    USING (is_current_user_admin());

DROP POLICY IF EXISTS licitacao_tags_insert_own ON public.licitacao_tags;
CREATE POLICY licitacao_tags_insert_own ON public.licitacao_tags
    FOR INSERT
    WITH CHECK (EXISTS (
        SELECT 1 FROM licitacoes l
        WHERE l.id = licitacao_tags.licitacao_id
          AND l.user_id = get_local_user_id()
    ));

DROP POLICY IF EXISTS licitacao_tags_update_own ON public.licitacao_tags;
CREATE POLICY licitacao_tags_update_own ON public.licitacao_tags
    FOR UPDATE
    USING (EXISTS (
        SELECT 1 FROM licitacoes l
        WHERE l.id = licitacao_tags.licitacao_id
          AND l.user_id = get_local_user_id()
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM licitacoes l
        WHERE l.id = licitacao_tags.licitacao_id
          AND l.user_id = get_local_user_id()
    ));

DROP POLICY IF EXISTS licitacao_tags_delete_own ON public.licitacao_tags;
CREATE POLICY licitacao_tags_delete_own ON public.licitacao_tags
    FOR DELETE
    USING (EXISTS (
        SELECT 1 FROM licitacoes l
        WHERE l.id = licitacao_tags.licitacao_id
          AND l.user_id = get_local_user_id()
    ));

DROP POLICY IF EXISTS licitacao_tags_admin_all ON public.licitacao_tags;
CREATE POLICY licitacao_tags_admin_all ON public.licitacao_tags
    FOR ALL
    USING (is_current_user_admin());


-- =============================================================================
-- PARTE 5: alembic_version (nega tudo)
-- =============================================================================
-- Tabela de controle do Alembic (uma coluna, version_num). Não tem dono nem
-- dado de usuário. RLS habilitado sem nenhuma política = ninguém acessa via
-- PostgREST. O Alembic segue funcionando porque roda como `postgres` (owner).

ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.alembic_version FROM authenticated;


-- =============================================================================
-- PARTE 6: Endurecer as funções
-- =============================================================================
-- 6a. Fixar search_path (lint 0011).
-- Em funções SECURITY DEFINER, search_path mutável é vetor de escalada de
-- privilégio: um atacante que consiga criar objetos em um schema à frente na
-- resolução sequestra a chamada. get_local_user_id e is_current_user_admin são
-- justamente as funções que decidem identidade e quem é admin.
--
-- Conferido que nenhuma das cinco usa operador de extensão (pg_trgm etc.):
-- todas referenciam só tabelas de public e built-ins de pg_catalog. Fixar em
-- `public, pg_temp` é seguro. `auth.uid()` já vem qualificado no corpo.

ALTER FUNCTION public.get_local_user_id()               SET search_path = public, pg_temp;
ALTER FUNCTION public.is_current_user_admin()           SET search_path = public, pg_temp;
ALTER FUNCTION public.update_updated_at_column()        SET search_path = public, pg_temp;
ALTER FUNCTION public.get_job_stats(integer)            SET search_path = public, pg_temp;
ALTER FUNCTION public.search_atestados(integer, text)   SET search_path = public, pg_temp;

-- 6b. Revogar EXECUTE de PUBLIC (lints 0028/0029).
-- Estavam chamáveis sem login via /rest/v1/rpc/. O revoke tem que ser contra
-- PUBLIC, não contra `anon` — ver a nota na Parte 1. Revogar de PUBLIC preserva
-- os grants explícitos de `authenticated` e `service_role`, feitos na 002.
--
-- update_updated_at_column fica de fora: é função de trigger (RETURNS trigger),
-- o PostgREST não a expõe como RPC e mexer no EXECUTE dela não traz ganho.

REVOKE EXECUTE ON FUNCTION public.get_local_user_id()             FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.is_current_user_admin()         FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.get_job_stats(integer)          FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.search_atestados(integer, text) FROM PUBLIC;

-- Reafirma o acesso de quem precisa. As políticas RLS chamam
-- get_local_user_id() e is_current_user_admin(), e o predicado é avaliado com
-- o privilégio de quem consulta — sem este GRANT, todo SELECT de um usuário
-- autenticado falharia.

GRANT EXECUTE ON FUNCTION public.get_local_user_id()             TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.is_current_user_admin()         TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_job_stats(integer)          TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.search_atestados(integer, text) TO authenticated, service_role;


-- =============================================================================
-- PARTE 7 (OPCIONAL): Revogar também do `authenticated`
-- =============================================================================
-- O frontend NÃO consulta tabelas via PostgREST — os únicos usos do cliente
-- Supabase são auth.getSession e auth.signOut. Todo dado passa pelo FastAPI.
-- Logo, os grants de `authenticated` são superfície de ataque não utilizada.
--
-- Também confirmado no backend: o cliente Supabase com chave anon aparece
-- apenas em sign_in_with_password e refresh_session (services/supabase_auth.py),
-- que chamam /auth/v1/ e não /rest/v1/. Todo acesso a dado usa
-- SUPABASE_SERVICE_KEY (service_role) ou a conexão Postgres direta.
-- `service_role` NÃO é tocado por este bloco.
--
-- Executar isto zera 17 dos 19 lints restantes: os 15
-- pg_graphql_authenticated_table_exposed e os 2
-- authenticated_security_definer_function_executable.
--
-- Fica comentado por padrão porque contraria a intenção declarada da 002, que
-- concedeu DML a `authenticated` antevendo acesso direto via PostgREST. Com o
-- RLS das Partes 3-5 no lugar, manter os grants também é seguro — a diferença
-- é superfície de ataque não utilizada versus zero superfície.
--
-- PARA REABILITAR PostgREST no futuro, reconceda AS DUAS COISAS: os grants de
-- tabela E o EXECUTE dos helpers. Sem o EXECUTE, as políticas RLS falham com
-- permission denied em vez de filtrar. As políticas seguem no lugar, então o
-- re-grant é seguro e imediato.
--
-- REVOKE ALL ON ALL TABLES IN SCHEMA public FROM authenticated;
-- REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM authenticated;
--
-- ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
--     REVOKE ALL ON TABLES FROM authenticated;
-- ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
--     REVOKE ALL ON SEQUENCES FROM authenticated;
--
-- REVOKE EXECUTE ON FUNCTION public.get_local_user_id()             FROM authenticated;
-- REVOKE EXECUTE ON FUNCTION public.is_current_user_admin()         FROM authenticated;
-- REVOKE EXECUTE ON FUNCTION public.get_job_stats(integer)          FROM authenticated;
-- REVOKE EXECUTE ON FUNCTION public.search_atestados(integer, text) FROM authenticated;


-- =============================================================================
-- PARTE 8: Remover política permissiva em audit_logs (herdada da 002)
-- =============================================================================
-- A 002 criou:
--     CREATE POLICY audit_insert_system ON audit_logs
--         FOR INSERT WITH CHECK (true);
--
-- `WITH CHECK (true)` deixa qualquer papel com grant de INSERT gravar o que
-- quiser na trilha de auditoria. A aplicação nunca usa esse caminho: os logs
-- são escritos por services/audit_service.py via SQLAlchemy, ou seja, pela
-- conexão direta como `postgres` (owner), que ignora RLS.
--
-- Sem grants para anon/authenticated a política é inalcançável hoje, mas é o
-- tipo de resquício que volta a morder no dia em que alguém reconceder acesso
-- — e forjar entrada de auditoria é dos piores lugares para isso acontecer.
-- Removendo: com RLS ativo e sem política de INSERT, só o owner escreve.

DROP POLICY IF EXISTS audit_insert_system ON public.audit_logs;


-- =============================================================================
-- VERIFICAÇÃO
-- =============================================================================
-- Esperado: 16 linhas, todas com rls_on = true.
-- As 11 desta migração devem sair com policies > 0, exceto alembic_version,
-- que fica com 0 de propósito (nega tudo).

SELECT c.relname AS tabela,
       c.relrowsecurity AS rls_on,
       (SELECT COUNT(*) FROM pg_policy p WHERE p.polrelid = c.oid) AS policies,
       has_table_privilege('anon', c.oid, 'SELECT') AS anon_ainda_le
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY c.relrowsecurity, c.relname;

-- Esperado: 5 linhas, todas com search_path preenchido.
SELECT p.proname, p.prosecdef AS security_definer, p.proconfig AS search_path
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
ORDER BY p.proname;
