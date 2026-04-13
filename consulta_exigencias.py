"""Script para consultar exigências específicas no banco de dados."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from backend.database import SessionLocal
from sqlalchemy import text


def normalize_kw(kw):
    """Remove acentos de uma keyword para busca."""
    replacements = {
        'á': 'a', 'ã': 'a', 'â': 'a', 'à': 'a',
        'é': 'e', 'ê': 'e',
        'í': 'i',
        'ó': 'o', 'ô': 'o', 'õ': 'o',
        'ú': 'u', 'ü': 'u',
        'ç': 'c',
    }
    result = kw.lower()
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result


TRANSLATE_EXPR = "LOWER(TRANSLATE(s->>'descricao', 'àáâãéêíóôõúüçÀÁÂÃÉÊÍÓÔÕÚÜÇ', 'aaaaeeiooouucAAAAEEIOOOUUC'))"

SERVICOS = [
    ('Estrutura treliçada de cobertura, tipo arco, com ligações soldadas',
     4302.36, 'kg',
     ['estrutura', 'treliç', 'cobertura']),

    ('Alvenaria de vedação blocos cerâmicos 9x19x19cm',
     390.30, 'm²',
     ['alvenaria', 'vedação', 'cerâmic']),

    ('Revestimento cerâmico para paredes internas 33x45cm',
     370.11, 'm²',
     ['revestimento', 'cerâmic', 'parede']),

    ('Fabricação e montagem de pórtico metálico',
     0.50, 'und',
     ['pórtico', 'metálic']),

    ('Telhamento com telha de aço/alumínio e=0,5mm',
     375.99, 'm²',
     ['telhamento', 'telha']),

    ('Porta de alumínio de abrir com lambri',
     25.09, 'm²',
     ['porta', 'alumínio']),

    ('Laje pré-moldada unidirecional para forro (8+3)',
     126.66, 'm²',
     ['laje', 'pré-moldada']),

    ('Revestimento cerâmico para piso 35x35cm',
     274.71, 'm²',
     ['revestimento', 'cerâmic', 'piso']),

    ('Piso intertravado, bloco retangular 20x10cm, esp. 6cm',
     162.16, 'm²',
     ['piso', 'intertravado']),

    ('Fôrma de viga, escoramento metálico, madeira plastificada',
     129.97, 'm²',
     ['forma', 'viga', 'escoramento']),
]


def buscar():
    db = SessionLocal()
    try:
        total_atestados = db.execute(text("SELECT COUNT(*) FROM atestados")).scalar()
        total_servicos = db.execute(text(
            "SELECT COUNT(*) FROM atestados a, "
            "jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s"
        )).scalar()
        print(f"Total de atestados no banco: {total_atestados}")
        print(f"Total de itens de servico: {total_servicos}")
        print()

        resumo = []

        for nome, qtd_req, unidade, keywords in SERVICOS:
            print("=" * 110)
            print(f"BUSCANDO: {nome}")
            print(f"Necessario: {qtd_req:,.2f} {unidade}")
            print(f"Keywords: {keywords}")
            print("-" * 110)

            # Busca com todas as keywords
            kw_norms = [normalize_kw(kw) for kw in keywords]
            conditions = " AND ".join([
                f"{TRANSLATE_EXPR} LIKE :kw{i}"
                for i in range(len(kw_norms))
            ])
            params = {f"kw{i}": f"%{kw}%" for i, kw in enumerate(kw_norms)}

            query = text(f"""
                SELECT
                    a.id AS atestado_id,
                    a.contratante,
                    s->>'item' AS item_code,
                    s->>'descricao' AS item_descricao,
                    (s->>'quantidade')::NUMERIC AS quantidade,
                    s->>'unidade' AS unidade
                FROM atestados a,
                    jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
                WHERE {conditions}
                ORDER BY (s->>'quantidade')::NUMERIC DESC NULLS LAST
            """)

            results = db.execute(query, params).fetchall()

            if results:
                qtd_total = 0
                print(f"ENCONTRADOS: {len(results)} registro(s)")
                for r in results:
                    qtd = float(r.quantidade) if r.quantidade else 0
                    qtd_total += qtd
                    print(f"  Atestado #{r.atestado_id} | Contratante: {r.contratante or 'N/A'}")
                    print(f"    Item: {r.item_code or 'N/A'} | {r.item_descricao}")
                    print(f"    Quantidade: {qtd:,.2f} {r.unidade or 'N/A'}")

                pct = (qtd_total / qtd_req * 100) if qtd_req > 0 else 0
                status = "ATENDE" if qtd_total >= qtd_req else "PARCIAL"
                print(f"  TOTAL: {qtd_total:,.2f} / {qtd_req:,.2f} {unidade} = {pct:.1f}% => {status}")
                resumo.append((nome, qtd_req, qtd_total, unidade, pct, status, len(results)))
            else:
                # Busca ampliada - keywords individuais
                print("Nenhum resultado com todas as keywords. Buscando individualmente...")
                for i, kw in enumerate(keywords):
                    kw_n = normalize_kw(kw)
                    q2 = text(f"""
                        SELECT
                            a.id AS atestado_id,
                            a.contratante,
                            s->>'item' AS item_code,
                            s->>'descricao' AS item_descricao,
                            (s->>'quantidade')::NUMERIC AS quantidade,
                            s->>'unidade' AS unidade
                        FROM atestados a,
                            jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
                        WHERE {TRANSLATE_EXPR} LIKE :kw
                        ORDER BY (s->>'quantidade')::NUMERIC DESC NULLS LAST
                        LIMIT 5
                    """)
                    partial = db.execute(q2, {"kw": f"%{kw_n}%"}).fetchall()
                    if partial:
                        print(f"  Keyword '{kw}' -> {len(partial)} resultado(s):")
                        for p in partial:
                            qtd = float(p.quantidade) if p.quantidade else 0
                            desc = p.item_descricao or ""
                            desc_trunc = (desc[:90] + "...") if len(desc) > 90 else desc
                            print(f"    Atestado #{p.atestado_id}: {desc_trunc} | {qtd:,.2f} {p.unidade or 'N/A'}")
                    else:
                        print(f"  Keyword '{kw}' -> NENHUM resultado")

                # Busca com pares de keywords
                if len(keywords) >= 2:
                    print("  Tentando combinacoes de 2 keywords...")
                    for i in range(len(keywords)):
                        for j in range(i + 1, len(keywords)):
                            kw1_n = normalize_kw(keywords[i])
                            kw2_n = normalize_kw(keywords[j])
                            q3 = text(f"""
                                SELECT
                                    a.id AS atestado_id,
                                    a.contratante,
                                    s->>'item' AS item_code,
                                    s->>'descricao' AS item_descricao,
                                    (s->>'quantidade')::NUMERIC AS quantidade,
                                    s->>'unidade' AS unidade
                                FROM atestados a,
                                    jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
                                WHERE {TRANSLATE_EXPR} LIKE :kw1
                                  AND {TRANSLATE_EXPR} LIKE :kw2
                                ORDER BY (s->>'quantidade')::NUMERIC DESC NULLS LAST
                                LIMIT 5
                            """)
                            partial2 = db.execute(q3, {"kw1": f"%{kw1_n}%", "kw2": f"%{kw2_n}%"}).fetchall()
                            if partial2:
                                print(f"  Keywords '{keywords[i]}' + '{keywords[j]}' -> {len(partial2)} resultado(s):")
                                for p in partial2:
                                    qtd = float(p.quantidade) if p.quantidade else 0
                                    desc = p.item_descricao or ""
                                    desc_trunc = (desc[:90] + "...") if len(desc) > 90 else desc
                                    print(f"    Atestado #{p.atestado_id}: {desc_trunc} | {qtd:,.2f} {p.unidade or 'N/A'}")

                resumo.append((nome, qtd_req, 0, unidade, 0, "NAO ENCONTRADO", 0))

            print()

        # Resumo final
        print("=" * 120)
        print("RESUMO GERAL")
        print("=" * 120)
        header = f"{'Servico':<60} {'Necessario':>12} {'Encontrado':>12} {'%':>8} {'Status':<20}"
        print(header)
        print("-" * 120)
        for nome, qtd_req, qtd_enc, unidade, pct, status, n in resumo:
            print(f"{nome[:59]:<60} {qtd_req:>10,.2f} {qtd_enc:>10,.2f} {pct:>7.1f}% {status:<20}")

        atende = sum(1 for r in resumo if r[5] == "ATENDE")
        parcial = sum(1 for r in resumo if r[5] == "PARCIAL")
        nao = sum(1 for r in resumo if r[5] == "NAO ENCONTRADO")
        print()
        print(f"Atendem: {atende}/{len(resumo)} | Parciais: {parcial}/{len(resumo)} | Nao atendem: {nao}/{len(resumo)}")

    except Exception as e:
        print(f"ERRO: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    buscar()
