"""
Script para verificar se os atestados no banco de dados atendem às exigências
de qualificação técnico-operacional.

Critérios refinados para evitar falsos positivos:
- Exclui serviços de demolição/remoção
- Valida unidades compatíveis por exigência (m³, m², m)
- Usa critérios específicos por exigência
"""
import os
import re
import sys

# Fix Windows console encoding
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

# Adicionar o diretório backend ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_session
from models import Atestado

# Palavras que indicam que NÃO é execução do serviço
PALAVRAS_EXCLUSAO = [
    "demolição", "remoção", "remocao", "demolir", "remover",
]


def normalizar(texto: str) -> str:
    """Normaliza texto para comparação."""
    if not texto:
        return ""
    return texto.lower().strip()


def unidade_compativel(unidade: str, unidade_exigida: str) -> bool:
    """Verifica se a unidade do serviço é compatível com a exigida."""
    u = normalizar(unidade)
    if not u:
        return True  # Se não tem unidade, aceitar (será revisão manual)

    if unidade_exigida == "m3":
        return any(x in u for x in ["m3", "m³", "m 3"])
    elif unidade_exigida == "m2":
        return any(x in u for x in ["m2", "m²", "m 2"])
    elif unidade_exigida == "m":
        # Metro linear - aceita "m", "m.", "ml" mas NÃO "m2", "m3", "m²", "m³"
        u_clean = u.strip().rstrip(".")
        if any(x in u for x in ["m2", "m²", "m3", "m³"]):
            return False
        return u_clean in ("m", "ml", "m.")
    return True


def eh_servico_execucao(descricao: str) -> bool:
    """Verifica se é um serviço de execução (não demolição/remoção)."""
    desc = normalizar(descricao)
    for palavra in PALAVRAS_EXCLUSAO:
        if palavra in desc:
            return False
    return True


# ============================================================================
# MATCHERS - Funções de correspondência por exigência
# ============================================================================

def match_escavacao_vala_1a_2a(desc: str) -> bool:
    """
    a.1) Escavação manual/mecânica de vala em material de 1ª e 2ª categoria.
    """
    d = normalizar(desc)

    # Deve mencionar escavação
    if "escavação" not in d and "escavacao" not in d:
        return False

    # Deve ser de vala
    if "vala" not in d:
        return False

    # Deve ser 1ª/2ª categoria (ou não mencionar 3ª categoria/rocha)
    # Aceita: "1ª categoria", "2ª categoria", "1a categoria", "2a categoria"
    # Também aceita se não especifica categoria (escavação genérica de vala)
    eh_3a = "3ª" in d or "3a categ" in d or "rocha" in d
    if eh_3a:
        return False

    return True


def match_escavacao_vala_3a(desc: str) -> bool:
    """
    a.2) Escavação de vala em material 3ª categoria - rocha dura.
    """
    d = normalizar(desc)

    if "escavação" not in d and "escavacao" not in d:
        return False

    if "vala" not in d:
        return False

    # Deve ser 3ª categoria ou rocha
    eh_3a = "3ª" in d or "3a categ" in d or "rocha" in d
    return eh_3a


def match_aterro_reaterro_vala(desc: str) -> bool:
    """
    a.3) Execução de aterro/reaterro de vala.
    """
    d = normalizar(desc)
    if not eh_servico_execucao(d):
        return False

    tem_aterro = "aterro" in d or "reaterro" in d
    tem_vala = "vala" in d

    # Aceitar aterro de vala, reaterro de vala, aterro/reaterro
    return tem_aterro and tem_vala


def match_envoltoria_colchao_areia(desc: str) -> bool:
    """
    a.4) Execução de envoltória e/ou colchão de areia para assentamento de tubulação.
    """
    d = normalizar(desc)
    if not eh_servico_execucao(d):
        return False

    tem_envoltoria = "envoltória" in d or "envoltoria" in d
    tem_colchao = "colchão" in d or "colchao" in d
    tem_berco = "berço" in d or "berco" in d
    tem_areia = "areia" in d

    # Envoltória ou colchão/berço de areia, preferencialmente ligado a tubulação
    if tem_envoltoria:
        return True
    if (tem_colchao or tem_berco) and tem_areia:
        return True

    return False


def match_cibramento(desc: str) -> bool:
    """
    a.5) Execução de cibramento (escoramento de valas).
    """
    d = normalizar(desc)
    if not eh_servico_execucao(d):
        return False

    # Cibramento ou escoramento de vala
    return "cibramento" in d or ("escoramento" in d and "vala" in d)


def match_tubo_pead(desc: str) -> bool:
    """
    a.6) Assentamento de tubo PEAD DN>=90mm.
    """
    d = normalizar(desc)
    if not eh_servico_execucao(d):
        return False

    # Deve mencionar tubo/tubulação
    tem_tubo = "tubo" in d or "tubulação" in d or "tubulacao" in d
    # Deve ser PEAD (polietileno de alta densidade)
    tem_pead = "pead" in d or "polietileno" in d or "pe " in d

    return tem_tubo and tem_pead


def match_tubo_pvc(desc: str) -> bool:
    """
    a.7) Assentamento de tubo PVC DN>=150mm.
    """
    d = normalizar(desc)
    if not eh_servico_execucao(d):
        return False

    tem_tubo = "tubo" in d or "tubulação" in d or "tubulacao" in d
    tem_pvc = "pvc" in d

    return tem_tubo and tem_pvc


def match_concreto_estrutural(desc: str) -> bool:
    """
    a.8) Execução de concreto estrutural e/ou armado >=25 MPa.
    """
    d = normalizar(desc)
    if not eh_servico_execucao(d):
        return False

    tem_concreto = "concreto" in d
    tem_estrutural = "estrutural" in d
    tem_armado = "armado" in d
    tem_fck_alto = False

    # Verificar FCK >= 25
    match_fck = re.search(r'fck\s*[=>]*\s*(\d+)', d)
    if match_fck:
        valor_fck = int(match_fck.group(1))
        if valor_fck >= 25:
            tem_fck_alto = True

    # Concretagem de vigas/lajes/pilares com FCK>=25 também conta
    tem_concretagem = "concretagem" in d

    if tem_concreto and tem_estrutural:
        return True
    if tem_concreto and tem_armado and tem_fck_alto:
        return True
    if (tem_concreto or tem_concretagem) and tem_fck_alto:
        return True

    return False


# ============================================================================
# CONFIGURAÇÃO DAS EXIGÊNCIAS
# ============================================================================

MATCHERS = {
    1: match_escavacao_vala_1a_2a,
    2: match_escavacao_vala_3a,
    3: match_aterro_reaterro_vala,
    4: match_envoltoria_colchao_areia,
    5: match_cibramento,
    6: match_tubo_pead,
    7: match_tubo_pvc,
    8: match_concreto_estrutural,
}

EXIGENCIAS = [
    {
        "id": 1,
        "descricao": "Escavacao manual/mecanica de vala em material 1a e 2a categoria",
        "quantidade_minima": 4500.00,
        "unidade": "m3",
    },
    {
        "id": 2,
        "descricao": "Escavacao de vala em material 3a categoria - rocha dura",
        "quantidade_minima": 500.00,
        "unidade": "m3",
    },
    {
        "id": 3,
        "descricao": "Execucao de aterro/reaterro de vala",
        "quantidade_minima": 3500.00,
        "unidade": "m3",
    },
    {
        "id": 4,
        "descricao": "Envoltoria e/ou colchao de areia para assentamento de tubulacao",
        "quantidade_minima": 1300.00,
        "unidade": "m3",
    },
    {
        "id": 5,
        "descricao": "Execucao de cibramento",
        "quantidade_minima": 1500.00,
        "unidade": "m2",
    },
    {
        "id": 6,
        "descricao": "Assentamento de tubo PEAD DN>=90mm",
        "quantidade_minima": 3000.00,
        "unidade": "m",
    },
    {
        "id": 7,
        "descricao": "Assentamento de tubo PVC DN>=150mm",
        "quantidade_minima": 2500.00,
        "unidade": "m",
    },
    {
        "id": 8,
        "descricao": "Execucao de concreto estrutural e/ou armado >=25 MPa",
        "quantidade_minima": 80.00,
        "unidade": "m3",
    },
]


def unidade_label(unidade: str) -> str:
    """Retorna label amigável da unidade."""
    if unidade == "m3":
        return "m3"
    elif unidade == "m2":
        return "m2"
    elif unidade == "m":
        return "m"
    return unidade


def verificar_exigencias():
    """Consulta o banco e verifica atendimento das exigências."""

    with get_db_session() as db:
        atestados = db.query(Atestado).all()

        print(f"\n{'='*80}")
        print("  VERIFICAÇÃO DE QUALIFICAÇÃO TÉCNICO-OPERACIONAL")
        print(f"  Total de atestados no banco: {len(atestados)}")
        print(f"{'='*80}\n")

        resultados = []

        for exigencia in EXIGENCIAS:
            matcher = MATCHERS[exigencia["id"]]
            unid_exigida = exigencia["unidade"]
            servicos_encontrados = []
            quantidade_total = 0.0

            for atestado in atestados:
                # Verificar serviços no JSON detalhado
                if atestado.servicos_json:
                    for servico in atestado.servicos_json:
                        desc = servico.get("descricao", "")
                        qtd = servico.get("quantidade")
                        unid = servico.get("unidade", "")

                        if matcher(desc):
                            qtd_float = float(qtd) if qtd else 0.0
                            unid_ok = unidade_compativel(unid, unid_exigida)
                            servicos_encontrados.append({
                                "atestado_id": atestado.id,
                                "contratante": atestado.contratante or "N/I",
                                "descricao": desc[:120],
                                "quantidade": qtd_float,
                                "unidade": unid,
                                "unidade_compativel": unid_ok,
                            })
                            if unid_ok:
                                quantidade_total += qtd_float

                # Verificar também na descrição principal do atestado
                if atestado.descricao_servico and matcher(atestado.descricao_servico):
                    ids_json = [s["atestado_id"] for s in servicos_encontrados]
                    if atestado.id not in ids_json:
                        qtd_float = float(atestado.quantidade) if atestado.quantidade else 0.0
                        unid = atestado.unidade or ""
                        unid_ok = unidade_compativel(unid, unid_exigida)
                        servicos_encontrados.append({
                            "atestado_id": atestado.id,
                            "contratante": atestado.contratante or "N/I",
                            "descricao": atestado.descricao_servico[:120],
                            "quantidade": qtd_float,
                            "unidade": unid,
                            "unidade_compativel": unid_ok,
                        })
                        if unid_ok:
                            quantidade_total += qtd_float

            atende = quantidade_total >= exigencia["quantidade_minima"]

            resultados.append({
                "exigencia": exigencia,
                "servicos": servicos_encontrados,
                "quantidade_total": quantidade_total,
                "atende": atende,
            })

        # Exibir resultados
        for r in resultados:
            ex = r["exigencia"]
            ul = unidade_label(ex["unidade"])
            status = ">> ATENDE <<" if r["atende"] else "** NÃO ATENDE **"
            diferenca = r["quantidade_total"] - ex["quantidade_minima"]

            print(f"{'─'*80}")
            print(f"  EXIGÊNCIA a.{ex['id']}: {ex['descricao']}")
            print(f"  Quantidade mínima exigida: {ex['quantidade_minima']:>10,.2f} {ul}")
            print(f"  Quantidade comprovada:     {r['quantidade_total']:>10,.2f} {ul}")
            print(f"  Status: {status}")
            if diferenca >= 0:
                print(f"  Excedente: +{diferenca:,.2f} {ul}")
            else:
                print(f"  Faltante: {diferenca:,.2f} {ul}")

            if r["servicos"]:
                compativeis = [s for s in r["servicos"] if s["unidade_compativel"]]
                incompativeis = [s for s in r["servicos"] if not s["unidade_compativel"]]

                if compativeis:
                    print(f"\n  Serviços comprovados (unidade compatível {ul}):")
                    for s in compativeis:
                        print(f"    - Atestado #{s['atestado_id']} | {s['contratante']}")
                        print(f"      {s['descricao']}")
                        print(f"      Qtd: {s['quantidade']:,.2f} {s['unidade']}")

                if incompativeis:
                    print("\n  [!] Serviços com UNIDADE INCOMPATÍVEL (não somados):")
                    for s in incompativeis:
                        print(f"    - Atestado #{s['atestado_id']} | {s['contratante']}")
                        print(f"      {s['descricao']}")
                        print(f"      Qtd: {s['quantidade']:,.2f} {s['unidade']} (UNIDADE DIFERENTE)")
            else:
                print("\n  Nenhum atestado encontrado para este serviço.")
            print()

        # Resumo final
        total_atende = sum(1 for r in resultados if r["atende"])
        total_exigencias = len(resultados)

        print(f"\n{'='*80}")
        print("  RESUMO FINAL")
        print(f"{'='*80}")
        print(f"  Exigências atendidas: {total_atende}/{total_exigencias}")
        print()
        for r in resultados:
            ex = r["exigencia"]
            ul = unidade_label(ex["unidade"])
            icon = "[OK]" if r["atende"] else "[X] "
            print(f"  {icon} a.{ex['id']}: {r['quantidade_total']:>10,.2f} / {ex['quantidade_minima']:>10,.2f} {ul:>3}  - {ex['descricao'][:50]}")

        print()
        if total_atende == total_exigencias:
            print("  >>> RESULTADO: EMPRESA QUALIFICADA <<<")
        else:
            print("  >>> RESULTADO: EMPRESA NÃO QUALIFICADA <<<")
            nao_atende = [r for r in resultados if not r["atende"]]
            print("\n  Exigências pendentes:")
            for r in nao_atende:
                ex = r["exigencia"]
                ul = unidade_label(ex["unidade"])
                faltante = ex["quantidade_minima"] - r["quantidade_total"]
                print(f"    - a.{ex['id']}: faltam {faltante:,.2f} {ul} - {ex['descricao'][:55]}")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    verificar_exigencias()
