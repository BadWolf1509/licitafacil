"""Busca servicos com compatibilidade tecnica para recurso administrativo da WJX."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

print("=" * 130)
print("SERVICOS COM COMPATIBILIDADE TECNICA PARA RECURSO ADMINISTRATIVO - WJX CONSTRUCOES")
print("=" * 130)

# =====================================================
# COMPATIBILIDADE 1: FORRO DE FIBRA MINERAL
# =====================================================
print()
print("=" * 130)
print("EXIGENCIA 1: Forro de fibra mineral em placas 625x625mm, 15mm, borda reta,")
print("             pintura antimofo, apoiado em perfil de aco galvanizado 24mm - INSTALADO")
print("=" * 130)
print()
print("TESE: O forro de fibra mineral e um sistema modular de forro suspenso com placas")
print("apoiadas em perfis metalicos (sistema T). A instalacao e tecnicamente analoga a")
print("outros forros modulares (gesso acartonado, drywall), pois envolvem:")
print("  - Fixacao de estrutura metalica suspensa (perfis em T)")
print("  - Nivelamento e alinhamento de perfis")
print("  - Colocacao de placas modulares sobre a estrutura")
print()

# 1a. Forros - Instalacao
print("--- 1a. FORROS - INSTALACAO (excluindo remocao/demolicao) ---")
r = db.execute(text("""
    SELECT a.id, a.contratante,
        s->>'item' AS item, s->>'descricao' AS d,
        (s->>'quantidade')::NUMERIC AS q, s->>'unidade' AS u
    FROM atestados a, jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
    WHERE LOWER(s->>'descricao') LIKE '%forro%'
      AND LOWER(s->>'descricao') NOT LIKE '%remo%'
      AND LOWER(s->>'descricao') NOT LIKE '%demol%'
      AND LOWER(s->>'descricao') NOT LIKE '%retir%'
    ORDER BY (s->>'quantidade')::NUMERIC DESC NULLS LAST
""")).fetchall()
print(f"  {len(r)} resultado(s)")
for x in r:
    print(f"  Atestado #{x.id} | Contratante: {x.contratante}")
    print(f"    Item {x.item}: {str(x.d)[:140]}")
    print(f"    Qtd: {float(x.q) if x.q else 0:,.2f} {x.u or ''}")
    print()

# 1b. Drywall (sistema analogo - placas com perfis metalicos)
print("--- 1b. DRYWALL - INSTALACAO (sistema analogo: placas + perfis metalicos) ---")
r = db.execute(text("""
    SELECT a.id, a.contratante,
        s->>'item' AS item, s->>'descricao' AS d,
        (s->>'quantidade')::NUMERIC AS q, s->>'unidade' AS u
    FROM atestados a, jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
    WHERE LOWER(s->>'descricao') LIKE '%drywall%'
      AND LOWER(s->>'descricao') NOT LIKE '%remo%'
      AND LOWER(s->>'descricao') NOT LIKE '%demol%'
    ORDER BY (s->>'quantidade')::NUMERIC DESC NULLS LAST
""")).fetchall()
print(f"  {len(r)} resultado(s)")
for x in r:
    print(f"  Atestado #{x.id} | {x.contratante} | Item {x.item}: {str(x.d)[:120]} | {float(x.q) if x.q else 0:,.2f} {x.u or ''}")

# 1c. Gesso (forro em gesso - habilidade similar)
print()
print("--- 1c. GESSO / PLACAS DE GESSO - INSTALACAO ---")
r = db.execute(text("""
    SELECT a.id, a.contratante,
        s->>'item' AS item, s->>'descricao' AS d,
        (s->>'quantidade')::NUMERIC AS q, s->>'unidade' AS u
    FROM atestados a, jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
    WHERE (LOWER(s->>'descricao') LIKE '%gesso%' OR LOWER(s->>'descricao') LIKE '%placa de gesso%')
      AND LOWER(s->>'descricao') NOT LIKE '%remo%'
      AND LOWER(s->>'descricao') NOT LIKE '%demol%'
      AND LOWER(s->>'descricao') NOT LIKE '%retir%'
    ORDER BY (s->>'quantidade')::NUMERIC DESC NULLS LAST
""")).fetchall()
print(f"  {len(r)} resultado(s)")
for x in r:
    print(f"  Atestado #{x.id} | {x.contratante} | Item {x.item}: {str(x.d)[:120]} | {float(x.q) if x.q else 0:,.2f} {x.u or ''}")

# 1d. Perfis metalicos / galvanizado
print()
print("--- 1d. PERFIS METALICOS / GALVANIZADO ---")
r = db.execute(text("""
    SELECT a.id, a.contratante,
        s->>'item' AS item, s->>'descricao' AS d,
        (s->>'quantidade')::NUMERIC AS q, s->>'unidade' AS u
    FROM atestados a, jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
    WHERE (LOWER(s->>'descricao') LIKE '%perfil%' AND LOWER(s->>'descricao') LIKE '%galvanizado%')
       OR (LOWER(s->>'descricao') LIKE '%perfil met%')
    ORDER BY (s->>'quantidade')::NUMERIC DESC NULLS LAST
""")).fetchall()
print(f"  {len(r)} resultado(s)")
for x in r:
    print(f"  Atestado #{x.id} | {x.contratante} | Item {x.item}: {str(x.d)[:120]} | {float(x.q) if x.q else 0:,.2f} {x.u or ''}")

# 1e. PVC forro
print()
print("--- 1e. FORRO PVC ---")
r = db.execute(text("""
    SELECT a.id, a.contratante,
        s->>'item' AS item, s->>'descricao' AS d,
        (s->>'quantidade')::NUMERIC AS q, s->>'unidade' AS u
    FROM atestados a, jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
    WHERE LOWER(s->>'descricao') LIKE '%forro%' AND LOWER(s->>'descricao') LIKE '%pvc%'
      AND LOWER(s->>'descricao') NOT LIKE '%remo%'
    ORDER BY (s->>'quantidade')::NUMERIC DESC NULLS LAST
""")).fetchall()
print(f"  {len(r)} resultado(s)")
for x in r:
    print(f"  Atestado #{x.id} | {x.contratante} | Item {x.item}: {str(x.d)[:120]} | {float(x.q) if x.q else 0:,.2f} {x.u or ''}")

# =====================================================
# COMPATIBILIDADE 2: TELHA TERMOISOLANTE
# =====================================================
print()
print()
print("=" * 130)
print("EXIGENCIA 2: Telha termoisolante revestida em aco galvalume, face superior trapezoidal")
print("             e face inferior plana, nucleo PIR 50mm")
print("=" * 130)
print()
print("TESE: A telha termoisolante (sanduiche) e uma cobertura metalica industrial.")
print("A competencia tecnica pode ser comprovada por servicos de:")
print("  - Telhamento com telhas metalicas (aco/aluminio)")
print("  - Coberturas metalicas industriais")
print("  - Estruturas metalicas para cobertura")
print("A diferenca e apenas no tipo de telha (simples vs sanduiche), nao na tecnica de instalacao.")
print()

# 2a. Telhas metalicas (aco/aluminio)
print("--- 2a. TELHAS METALICAS (aco/aluminio) - INSTALACAO ---")
r = db.execute(text("""
    SELECT a.id, a.contratante,
        s->>'item' AS item, s->>'descricao' AS d,
        (s->>'quantidade')::NUMERIC AS q, s->>'unidade' AS u
    FROM atestados a, jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
    WHERE (LOWER(s->>'descricao') LIKE '%telha%' AND (LOWER(s->>'descricao') LIKE '%a_o%' OR LOWER(s->>'descricao') LIKE '%alum%' OR LOWER(s->>'descricao') LIKE '%met%'))
      AND LOWER(s->>'descricao') NOT LIKE '%remo%'
      AND LOWER(s->>'descricao') NOT LIKE '%demol%'
      AND LOWER(s->>'descricao') NOT LIKE '%retir%'
    ORDER BY (s->>'quantidade')::NUMERIC DESC NULLS LAST
""")).fetchall()
print(f"  {len(r)} resultado(s)")
for x in r:
    print(f"  Atestado #{x.id} | Contratante: {x.contratante}")
    print(f"    Item {x.item}: {str(x.d)[:140]}")
    print(f"    Qtd: {float(x.q) if x.q else 0:,.2f} {x.u or ''}")
    print()

# 2b. Coberturas em geral (excluindo remocao)
print("--- 2b. COBERTURAS / TELHAMENTO em geral (instalacao) ---")
r = db.execute(text("""
    SELECT a.id, a.contratante,
        s->>'item' AS item, s->>'descricao' AS d,
        (s->>'quantidade')::NUMERIC AS q, s->>'unidade' AS u
    FROM atestados a, jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
    WHERE (LOWER(s->>'descricao') LIKE '%telhamento%' OR LOWER(s->>'descricao') LIKE '%cobertura%')
      AND LOWER(s->>'descricao') NOT LIKE '%remo%'
      AND LOWER(s->>'descricao') NOT LIKE '%demol%'
      AND LOWER(s->>'descricao') NOT LIKE '%retir%'
      AND LOWER(s->>'descricao') NOT LIKE '%revis%'
    ORDER BY (s->>'quantidade')::NUMERIC DESC NULLS LAST
""")).fetchall()
print(f"  {len(r)} resultado(s)")
for x in r:
    print(f"  Atestado #{x.id} | {x.contratante} | Item {x.item}: {str(x.d)[:120]} | {float(x.q) if x.q else 0:,.2f} {x.u or ''}")

# 2c. Estrutura metalica
print()
print("--- 2c. ESTRUTURA METALICA (para cobertura) ---")
r = db.execute(text("""
    SELECT a.id, a.contratante,
        s->>'item' AS item, s->>'descricao' AS d,
        (s->>'quantidade')::NUMERIC AS q, s->>'unidade' AS u
    FROM atestados a, jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
    WHERE (LOWER(s->>'descricao') LIKE '%estrutura met%'
       OR (LOWER(s->>'descricao') LIKE '%trama%' AND LOWER(s->>'descricao') LIKE '%metal%'))
      AND LOWER(s->>'descricao') NOT LIKE '%remo%'
    ORDER BY (s->>'quantidade')::NUMERIC DESC NULLS LAST
""")).fetchall()
print(f"  {len(r)} resultado(s)")
for x in r:
    print(f"  Atestado #{x.id} | {x.contratante} | Item {x.item}: {str(x.d)[:120]} | {float(x.q) if x.q else 0:,.2f} {x.u or ''}")

# 2d. Fibrocimento (tecnica similar de fixacao em estrutura)
print()
print("--- 2d. TELHAS FIBROCIMENTO (tecnica de fixacao similar) ---")
r = db.execute(text("""
    SELECT a.id, a.contratante,
        s->>'item' AS item, s->>'descricao' AS d,
        (s->>'quantidade')::NUMERIC AS q, s->>'unidade' AS u
    FROM atestados a, jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
    WHERE LOWER(s->>'descricao') LIKE '%fibrocimento%'
      AND LOWER(s->>'descricao') NOT LIKE '%remo%'
      AND LOWER(s->>'descricao') NOT LIKE '%demol%'
    ORDER BY (s->>'quantidade')::NUMERIC DESC NULLS LAST
""")).fetchall()
print(f"  {len(r)} resultado(s)")
for x in r:
    print(f"  Atestado #{x.id} | {x.contratante} | Item {x.item}: {str(x.d)[:120]} | {float(x.q) if x.q else 0:,.2f} {x.u or ''}")

# 2e. Trama para telhado
print()
print("--- 2e. TRAMA / ESTRUTURA PARA TELHADO ---")
r = db.execute(text("""
    SELECT a.id, a.contratante,
        s->>'item' AS item, s->>'descricao' AS d,
        (s->>'quantidade')::NUMERIC AS q, s->>'unidade' AS u
    FROM atestados a, jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
    WHERE LOWER(s->>'descricao') LIKE '%trama%'
      AND LOWER(s->>'descricao') NOT LIKE '%remo%'
    ORDER BY (s->>'quantidade')::NUMERIC DESC NULLS LAST
""")).fetchall()
print(f"  {len(r)} resultado(s)")
for x in r:
    print(f"  Atestado #{x.id} | {x.contratante} | Item {x.item}: {str(x.d)[:120]} | {float(x.q) if x.q else 0:,.2f} {x.u or ''}")

# =====================================================
# Buscar descricao geral dos atestados que possuem estes servicos
# =====================================================
print()
print()
print("=" * 130)
print("ATESTADOS MAIS RELEVANTES (com servicos de forro E cobertura metalica)")
print("=" * 130)
r = db.execute(text("""
    SELECT DISTINCT a.id, a.contratante, a.descricao_servico, a.quantidade, a.unidade, a.data_emissao
    FROM atestados a, jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
    WHERE (
        (LOWER(s->>'descricao') LIKE '%forro%' AND LOWER(s->>'descricao') NOT LIKE '%remo%')
        OR (LOWER(s->>'descricao') LIKE '%gesso%' AND LOWER(s->>'descricao') NOT LIKE '%remo%')
        OR (LOWER(s->>'descricao') LIKE '%drywall%' AND LOWER(s->>'descricao') NOT LIKE '%remo%')
        OR (LOWER(s->>'descricao') LIKE '%telha%' AND LOWER(s->>'descricao') LIKE '%a_o%' AND LOWER(s->>'descricao') NOT LIKE '%remo%')
    )
    ORDER BY a.id
""")).fetchall()
print(f"  {len(r)} atestado(s) relevantes")
for x in r:
    print(f"\n  Atestado #{x.id} | Contratante: {x.contratante}")
    print(f"    Descricao: {str(x.descricao_servico)[:150] if x.descricao_servico else 'N/A'}")
    print(f"    Quantidade: {float(x.quantidade) if x.quantidade else 0:,.2f} {x.unidade or ''}")
    print(f"    Data emissao: {x.data_emissao or 'N/A'}")

db.close()
print("\n\nConsulta finalizada.")
