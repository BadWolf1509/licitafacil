"""Análise completa de capacidade técnica - 20 exigências."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from backend.database import SessionLocal
from sqlalchemy import text

TRANSLATE = "LOWER(TRANSLATE(s->>'descricao', 'àáâãéêíóôõúüçÀÁÂÃÉÊÍÓÔÕÚÜÇ', 'aaaaeeiooouucAAAAEEIOOOUUC'))"

EXIGENCIAS = [
    ("Estrutura treliçada de cobertura, tipo arco, com ligações soldadas", 8604.71, "KG",
     [["trelic", "estrutura"], ["trelic"]]),
    ("Alvenaria de vedação blocos cerâmicos 9x19x19cm", 780.59, "M2",
     [["alvenaria", "vedac", "ceramic"]]),
    ("Revestimento cerâmico para paredes internas 33x45cm", 740.22, "M2",
     [["revestimento", "ceramic", "parede"]]),
    ("Fabricação e montagem de pórtico metálico", 1.0, "UND",
     [["portico", "metalic"], ["portico"]]),
    ("Telhamento com telha de aço/alumínio e=0,5mm", 751.98, "M2",
     [["telhamento", "telha"], ["telha", "aco"], ["telhamento"]]),
    ("Porta de alumínio de abrir com lambri", 50.18, "M2",
     [["porta", "aluminio", "lambri"], ["porta", "aluminio"]]),
    ("Laje pré-moldada unidirecional para forro (8+3)", 253.31, "M2",
     [["laje", "pre-moldada"], ["laje", "pre", "moldada"], ["laje", "forro"]]),
    ("Revestimento cerâmico para piso 35x35cm", 549.42, "M2",
     [["revestimento", "ceramic", "piso"]]),
    ("Contrapiso em argamassa traço 1:4", 592.23, "M2",
     [["contrapiso", "argamassa"], ["contrapiso"]]),
    ("Porta de aço chapa 24, de enrolar", 43.32, "M2",
     [["porta", "aco", "enrolar"], ["porta", "enrolar"], ["porta", "aco", "chapa"]]),
    ("Emboço em argamassa traço 1:2:8, paredes internas", 740.22, "M2",
     [["emboco", "argamassa"], ["emboco"]]),
    ("Piso intertravado, bloco retangular 20x10cm, esp. 6cm", 324.31, "M2",
     [["piso", "intertravado"]]),
    ("Fôrma de viga, escoramento metálico, madeira plastificada", 259.93, "M2",
     [["forma", "viga", "escoramento"], ["forma", "viga"]]),
    ("Massa única, argamassa traço 1:2:8, paredes internas", 768.74, "M2",
     [["massa unica", "argamassa"], ["massa unica"]]),
    ("Cabo de cobre flexível 6mm², anti-chama 0,6/1,0kV", 1585.89, "M",
     [["cabo", "cobre", "flexivel"], ["cabo", "cobre"]]),
    ("Forro em placas de gesso", 367.22, "M2",
     [["forro", "gesso", "placa"], ["forro", "gesso"]]),
    ("Fôrma para viga baldrame, madeira serrada", 214.43, "M2",
     [["forma", "viga", "baldrame"], ["forma", "baldrame"]]),
    ("Emassamento com massa látex, parede, duas demãos", 768.74, "M2",
     [["emassamento", "massa", "latex"], ["emassamento", "latex"], ["emassamento"]]),
    ("Eletroduto flexível corrugado PVC DN 25mm (3/4\")", 700.75, "M",
     [["eletroduto", "flexivel", "corrugado"], ["eletroduto", "flexivel"], ["eletroduto", "corrugado"]]),
    ("Lastro de concreto magro, pisos, espessura 3cm", 592.23, "M2",
     [["lastro", "concreto", "magro"], ["lastro", "concreto"], ["lastro"]]),
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

        for nome, qtd_req, unidade_esp, keyword_sets in EXIGENCIAS:
            print("=" * 120)
            print(f"EXIGENCIA: {nome}")
            print(f"Necessario: {qtd_req:,.2f} {unidade_esp}")
            print("-" * 120)

            results = None
            used_kws = None

            # Tentar cada conjunto de keywords, do mais específico ao mais amplo
            for kws in keyword_sets:
                conditions = " AND ".join([
                    f"{TRANSLATE} LIKE :kw{i}" for i in range(len(kws))
                ])
                params = {f"kw{i}": f"%{kw}%" for i, kw in enumerate(kws)}

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

                r = db.execute(query, params).fetchall()
                if r:
                    results = r
                    used_kws = kws
                    break

            if results:
                qtd_total = 0.0
                print(f"Keywords usadas: {used_kws}")
                print(f"Registros encontrados: {len(results)}")
                for r in results:
                    qtd = float(r.quantidade) if r.quantidade else 0
                    qtd_total += qtd
                    desc = r.item_descricao or ""
                    desc_trunc = (desc[:95] + "...") if len(desc) > 95 else desc
                    print(f"  Atestado #{r.atestado_id} | {r.contratante or 'N/A'}")
                    print(f"    {r.item_code or '-'} | {desc_trunc}")
                    print(f"    Qtd: {qtd:,.2f} {r.unidade or 'N/A'}")

                pct = (qtd_total / qtd_req * 100) if qtd_req > 0 else 0
                if qtd_total >= qtd_req:
                    status = "ATENDE"
                elif qtd_total >= qtd_req * 0.5:
                    status = "PARCIAL"
                else:
                    status = "INSUFICIENTE"
                print(f"\n  >>> SOMA: {qtd_total:,.2f} / {qtd_req:,.2f} {unidade_esp} = {pct:.1f}% => {status}")
                resumo.append((nome, qtd_req, qtd_total, unidade_esp, pct, status, len(results)))
            else:
                print("  >>> NENHUM REGISTRO ENCONTRADO")
                resumo.append((nome, qtd_req, 0, unidade_esp, 0, "NAO ENCONTRADO", 0))

            print()

        # Resumo final
        print("\n" + "=" * 130)
        print("RESUMO GERAL DA ANALISE DE CAPACIDADE TECNICA")
        print("=" * 130)
        print(f"{'#':<3} {'Exigencia':<58} {'Unid':<5} {'Necessario':>12} {'Encontrado':>12} {'%':>8} {'Status':<18}")
        print("-" * 130)
        for i, (nome, qtd_req, qtd_enc, unidade, pct, status, n) in enumerate(resumo, 1):
            print(f"{i:<3} {nome[:57]:<58} {unidade:<5} {qtd_req:>10,.2f} {qtd_enc:>10,.2f} {pct:>7.1f}% {status:<18}")

        print("-" * 130)
        atende = sum(1 for r in resumo if r[5] == "ATENDE")
        parcial = sum(1 for r in resumo if r[5] == "PARCIAL")
        insuf = sum(1 for r in resumo if r[5] == "INSUFICIENTE")
        nao = sum(1 for r in resumo if r[5] == "NAO ENCONTRADO")
        total = len(resumo)
        print(f"\nATENDEM:         {atende}/{total}")
        print(f"PARCIAIS:        {parcial}/{total}")
        print(f"INSUFICIENTES:   {insuf}/{total}")
        print(f"NAO ENCONTRADOS: {nao}/{total}")

    except Exception as e:
        print(f"ERRO: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    buscar()
