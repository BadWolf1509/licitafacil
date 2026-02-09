"""
Script de validacao: re-executa o matching_service com o codigo melhorado
contra os dados da ultima analise (ID 15 - CR/2/2026 Itabaiana).

Compara os resultados ANTIGOS (gravados no banco) com os NOVOS (recalculados).
"""
# ruff: noqa: E402

import os
import sys
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import desc

from database import get_db_session
from models import Analise, Atestado
from services.matching_service import matching_service


def main():
    with get_db_session() as db:
        # 1. Buscar última análise
        ultima = db.query(Analise).order_by(desc(Analise.created_at)).first()
        if not ultima:
            print("Nenhuma análise encontrada.")
            return

        print(f"Análise ID: {ultima.id} | {ultima.nome_licitacao}")
        print(f"Criada em: {ultima.created_at}")
        print()

        exigencias = ultima.exigencias_json or []
        resultado_antigo = ultima.resultado_json or []

        if not exigencias:
            print("Análise sem exigências.")
            return

        # 2. Buscar atestados do mesmo usuário
        atestados_db = db.query(Atestado).filter(
            Atestado.user_id == ultima.user_id
        ).all()

        print(f"Atestados do usuário: {len(atestados_db)}")

        # Converter para dicts
        atestados = []
        for at in atestados_db:
            atestados.append({
                "id": at.id,
                "descricao_servico": at.descricao_servico,
                "quantidade": float(at.quantidade) if at.quantidade else None,
                "unidade": at.unidade,
                "servicos_json": at.servicos_json,
            })

        # 3. Re-executar matching com código novo
        resultado_novo = matching_service.match_exigencias(exigencias, atestados)

        # 4. Comparar resultados
        print("\n" + "=" * 100)
        print("COMPARAÇÃO: RESULTADO ANTIGO vs NOVO")
        print("=" * 100)

        for i, exig in enumerate(exigencias):
            desc_exig = exig.get("descricao", "N/A")
            qtd_exig = exig.get("quantidade_minima", 0)
            unid_exig = exig.get("unidade", "")

            print(f"\n{'─' * 100}")
            print(f"CRITÉRIO {i+1}: {desc_exig}")
            print(f"  Quantidade exigida: {qtd_exig} {unid_exig}")

            # Resultado antigo
            antigo = resultado_antigo[i] if i < len(resultado_antigo) else None
            # Resultado novo
            novo = resultado_novo[i] if i < len(resultado_novo) else None

            if antigo:
                print("\n  >>> RESULTADO ANTIGO (gravado no banco):")
                print(f"      Status: {antigo.get('status')}")
                print(f"      Soma: {antigo.get('soma_quantidades', 0)}")
                print(f"      Percentual: {antigo.get('percentual_total', 0):.1f}%")
                recs_antigo = antigo.get("atestados_recomendados", [])
                print(f"      Atestados recomendados: {len(recs_antigo)}")
                for j, rec in enumerate(recs_antigo, 1):
                    at_id = rec.get("atestado_id", "?")
                    at_desc = rec.get("descricao_servico", rec.get("descricao_item", ""))[:80]
                    at_qty = rec.get("quantidade", 0)
                    at_unit = rec.get("unidade", "")
                    # Mostrar itens se disponíveis
                    itens = rec.get("itens", [])
                    print(f"      {j}. Atestado #{at_id}: {at_qty} {at_unit} | {at_desc}")
                    for it in itens[:3]:
                        print(f"         - Item {it.get('item', '?')}: {it.get('descricao', '')[:70]} ({it.get('quantidade', 0)} {it.get('unidade', '')})")
                    if len(itens) > 3:
                        print(f"         ... +{len(itens)-3} itens")

            if novo:
                print("\n  >>> RESULTADO NOVO (recalculado com melhorias):")
                print(f"      Status: {novo.get('status')}")
                print(f"      Soma: {novo.get('soma_quantidades', 0)}")
                print(f"      Percentual: {novo.get('percentual_total', 0):.1f}%")
                recs_novo = novo.get("atestados_recomendados", [])
                print(f"      Atestados recomendados: {len(recs_novo)}")
                for j, rec in enumerate(recs_novo, 1):
                    at_id = rec.get("atestado_id", "?")
                    at_desc = rec.get("descricao_servico", "")[:80]
                    at_qty = rec.get("quantidade", 0)
                    at_unit = rec.get("unidade", "")
                    sim = rec.get("best_similarity", 0)
                    itens = rec.get("itens", [])
                    print(f"      {j}. Atestado #{at_id}: {at_qty} {at_unit} (sim={sim:.2f}) | {at_desc}")
                    for it in itens[:5]:
                        print(f"         - Item {it.get('item', '?')}: {it.get('descricao', '')[:70]} ({it.get('quantidade', 0)} {it.get('unidade', '')})")
                    if len(itens) > 5:
                        print(f"         ... +{len(itens)-5} itens")

            # Resumo da comparação
            if antigo and novo:
                soma_a = antigo.get("soma_quantidades", 0)
                soma_n = novo.get("soma_quantidades", 0)
                status_a = antigo.get("status", "?")
                status_n = novo.get("status", "?")
                mudou = "MUDOU" if (status_a != status_n or abs(soma_a - soma_n) > 0.01) else "IGUAL"
                print(f"\n  *** {mudou}: {status_a}({soma_a}) → {status_n}({soma_n})")

        print(f"\n{'=' * 100}")
        print("VALIDAÇÃO CONCLUÍDA")
        print("=" * 100)


if __name__ == "__main__":
    main()
