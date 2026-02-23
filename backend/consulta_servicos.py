"""Script para consultar serviços específicos no banco de dados."""
import os
import sys

# Adicionar o diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal
from sqlalchemy import text

# Serviços a buscar (descrição, quantidade necessária, unidade)
SERVICOS_BUSCADOS = [
    ("Demolição de alvenaria", 175.0, "m³", [
        "demolição", "alvenaria", "mecanizada"
    ]),
    ("Escavação horizontal em solo de 1ª categoria com trator de esteiras", 698.17, "m³", [
        "escavação", "horizontal", "solo", "trator", "esteira"
    ]),
    ("Execução e compactação de corpo de aterro (95% Proctor Normal)", 713.54, "m³", [
        "compactação", "aterro", "proctor"
    ]),
    ("Armação de aço CA-50", 7858.23, "kg", [
        "armação", "aço", "ca-50"
    ]),
    ("Alvenaria de vedação blocos cerâmicos 19x19x19", 416.65, "m²", [
        "alvenaria", "vedação", "cerâmic"
    ]),
    ("Pintura látex acrílica premium", 502.18, "m²", [
        "pintura", "látex", "acrílica"
    ]),
    ("Revestimento cerâmico porcelanato 60x60", 304.26, "m²", [
        "revestimento", "porcelanato", "60x60"
    ]),
    ("Forro em placas de gesso", 216.41, "m²", [
        "forro", "gesso", "placa"
    ]),
    ("Forro em drywall", 72.91, "m²", [
        "forro", "drywall"
    ]),
]


def buscar_servicos():
    """Busca serviços no banco expandindo servicos_json."""
    db = SessionLocal()
    try:
        # Primeiro, listar todos os atestados e seus serviços
        print("=" * 100)
        print("CONSULTA DE SERVIÇOS NO BANCO DE DADOS")
        print("=" * 100)

        # Contar total de atestados
        total_atestados = db.execute(text("SELECT COUNT(*) FROM atestados")).scalar()
        print(f"\nTotal de atestados no banco: {total_atestados}")

        # Contar total de serviços (itens dentro de servicos_json)
        total_servicos = db.execute(text("""
            SELECT COUNT(*)
            FROM atestados a,
            jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
        """)).scalar()
        print(f"Total de itens de serviço no banco: {total_servicos}")

        print("\n" + "=" * 100)
        print("BUSCA POR SERVIÇO")
        print("=" * 100)

        resultados_resumo = []

        for nome_servico, qtd_necessaria, unidade_esperada, keywords in SERVICOS_BUSCADOS:
            print(f"\n{'─' * 100}")
            print(f"🔍 BUSCANDO: {nome_servico}")
            print(f"   Quantidade necessária: {qtd_necessaria:,.2f} {unidade_esperada}")
            print(f"   Palavras-chave: {keywords}")
            print(f"{'─' * 100}")

            # Construir query com ILIKE para cada keyword
            # Buscar no servicos_json expandido
            conditions = " AND ".join([
                f"LOWER(s->>'descricao') LIKE '%{kw.lower()}%'" for kw in keywords
            ])

            query = f"""
                SELECT
                    a.id AS atestado_id,
                    a.contratante,
                    a.descricao_servico AS descricao_principal,
                    s->>'item' AS item_code,
                    s->>'descricao' AS item_descricao,
                    (s->>'quantidade')::NUMERIC AS quantidade,
                    s->>'unidade' AS unidade
                FROM atestados a,
                    jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
                WHERE {conditions}
                ORDER BY (s->>'quantidade')::NUMERIC DESC NULLS LAST
            """

            results = db.execute(text(query)).fetchall()

            if results:
                qtd_total = 0
                print(f"\n   ✅ ENCONTRADOS: {len(results)} registro(s)")
                for r in results:
                    qtd = float(r.quantidade) if r.quantidade else 0
                    qtd_total += qtd
                    print(f"\n   📋 Atestado #{r.atestado_id} | Contratante: {r.contratante or 'N/A'}")
                    print(f"      Item: {r.item_code or 'N/A'}")
                    print(f"      Descrição: {r.item_descricao}")
                    print(f"      Quantidade: {qtd:,.2f} {r.unidade or 'N/A'}")

                percentual = (qtd_total / qtd_necessaria * 100) if qtd_necessaria > 0 else 0
                status = "✅ ATENDE" if qtd_total >= qtd_necessaria else "⚠️ PARCIAL" if qtd_total > 0 else "❌ NÃO ATENDE"

                print(f"\n   📊 TOTAL ACUMULADO: {qtd_total:,.2f} {unidade_esperada}")
                print(f"   📊 NECESSÁRIO: {qtd_necessaria:,.2f} {unidade_esperada}")
                print(f"   📊 PERCENTUAL: {percentual:.1f}%")
                print(f"   📊 STATUS: {status}")

                resultados_resumo.append({
                    "servico": nome_servico,
                    "necessario": qtd_necessaria,
                    "encontrado": qtd_total,
                    "unidade": unidade_esperada,
                    "percentual": percentual,
                    "status": status,
                    "registros": len(results)
                })
            else:
                # Tentar busca mais ampla com menos keywords
                print("\n   ❌ Nenhum resultado com todas as palavras-chave.")
                print("   🔄 Tentando busca ampliada (keywords individuais)...")

                encontrou_algo = False
                for kw in keywords:
                    query_ampla = f"""
                        SELECT
                            a.id AS atestado_id,
                            a.contratante,
                            s->>'item' AS item_code,
                            s->>'descricao' AS item_descricao,
                            (s->>'quantidade')::NUMERIC AS quantidade,
                            s->>'unidade' AS unidade
                        FROM atestados a,
                            jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
                        WHERE LOWER(s->>'descricao') LIKE '%{kw.lower()}%'
                        ORDER BY (s->>'quantidade')::NUMERIC DESC NULLS LAST
                        LIMIT 5
                    """
                    partial = db.execute(text(query_ampla)).fetchall()
                    if partial:
                        encontrou_algo = True
                        print(f"\n      Palavra '{kw}' encontrada em {len(partial)} item(ns):")
                        for p in partial:
                            qtd = float(p.quantidade) if p.quantidade else 0
                            print(f"         - Atestado #{p.atestado_id}: {p.item_descricao[:80]}... | {qtd:,.2f} {p.unidade or 'N/A'}")

                if not encontrou_algo:
                    # Buscar também no descricao_servico principal
                    for kw in keywords[:2]:
                        query_desc = f"""
                            SELECT
                                a.id AS atestado_id,
                                a.contratante,
                                a.descricao_servico,
                                a.quantidade,
                                a.unidade
                            FROM atestados a
                            WHERE LOWER(a.descricao_servico) LIKE '%{kw.lower()}%'
                            LIMIT 5
                        """
                        desc_results = db.execute(text(query_desc)).fetchall()
                        if desc_results:
                            encontrou_algo = True
                            print(f"\n      Palavra '{kw}' encontrada no campo descricao_servico:")
                            for d in desc_results:
                                qtd = float(d.quantidade) if d.quantidade else 0
                                print(f"         - Atestado #{d.atestado_id}: {d.descricao_servico[:80]}... | {qtd:,.2f} {d.unidade or 'N/A'}")

                if not encontrou_algo:
                    print("\n   ❌ NENHUM REGISTRO ENCONTRADO para este serviço.")

                resultados_resumo.append({
                    "servico": nome_servico,
                    "necessario": qtd_necessaria,
                    "encontrado": 0,
                    "unidade": unidade_esperada,
                    "percentual": 0,
                    "status": "❌ NÃO ENCONTRADO",
                    "registros": 0
                })

        # Resumo final
        print("\n\n" + "=" * 100)
        print("RESUMO GERAL")
        print("=" * 100)
        print(f"\n{'Serviço':<55} {'Necessário':>12} {'Encontrado':>12} {'%':>8} {'Status':<20}")
        print("─" * 110)

        for r in resultados_resumo:
            print(f"{r['servico'][:54]:<55} {r['necessario']:>10,.2f} {r['encontrado']:>10,.2f} {r['percentual']:>7.1f}% {r['status']:<20}")

        atende = sum(1 for r in resultados_resumo if "ATENDE" in r["status"] and "NÃO" not in r["status"] and "PARCIAL" not in r["status"])
        parcial = sum(1 for r in resultados_resumo if "PARCIAL" in r["status"])
        nao_atende = sum(1 for r in resultados_resumo if "NÃO" in r["status"] or r["encontrado"] == 0)

        print(f"\n{'─' * 110}")
        print(f"✅ Atendem plenamente: {atende}/{len(resultados_resumo)}")
        print(f"⚠️ Atendem parcialmente: {parcial}/{len(resultados_resumo)}")
        print(f"❌ Não atendem/encontrados: {nao_atende}/{len(resultados_resumo)}")

    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    buscar_servicos()
