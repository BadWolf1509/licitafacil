"""Verifica se os atestados no banco cobrem exigencias especificas."""
import sys
import unicodedata

sys.path.insert(0, ".")
from database import get_db_session
from models.atestado import Atestado


def normalize(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) not in ("Mn",))
    return text.lower().strip()


EXIGENCIAS = [
    {
        "nome": "Forma para sapata em chapa de madeira compensada resinada, 17 mm, 4 utilizacoes",
        "keywords": ["forma", "sapata", "compensada", "resinada"],
        "min_match": 2,
    },
    {
        "nome": "Alvenaria de vedacao de blocos ceramicos furados 9x19x19 cm (espessura 9 cm)",
        "keywords": ["alvenaria", "vedacao", "bloco", "ceramic", "9x19"],
        "min_match": 2,
    },
    {
        "nome": "Trama de madeira (ripas, caibros, tercas) para telhados ate 2 aguas, telha ceramica capa-canal",
        "keywords": ["trama", "ripas", "caibros", "tercas", "telhado", "capa"],
        "min_match": 2,
    },
    {
        "nome": "Tesoura inteira em madeira nao aparelhada, vao de 6 m, telha ceramica ou concreto",
        "keywords": ["tesoura", "madeira", "aparelhada", "vao"],
        "min_match": 2,
    },
    {
        "nome": "Porta de aluminio de abrir com lambril, com guarnicao",
        "keywords": ["porta", "aluminio", "lambril", "abrir"],
        "min_match": 2,
    },
]


with get_db_session() as db:
    atestados = db.query(Atestado).all()
    print(f"Total de atestados no banco: {len(atestados)}\n")

    for exig in EXIGENCIAS:
        print(f"{'='*80}")
        print(f"EXIGENCIA: {exig['nome']}")
        print(f"{'='*80}")
        encontrados = []

        for a in atestados:
            servicos = a.servicos_json or []
            for s in servicos:
                desc = normalize(s.get("descricao") or "")
                matched = [kw for kw in exig["keywords"] if kw in desc]
                if len(matched) >= exig["min_match"]:
                    encontrados.append(
                        {
                            "atestado_id": a.id,
                            "contratante": a.contratante or "?",
                            "item": s.get("item", "-"),
                            "descricao": (s.get("descricao") or "")[:160],
                            "quantidade": s.get("quantidade"),
                            "unidade": s.get("unidade"),
                            "matched": matched,
                        }
                    )

        if encontrados:
            print(f"  ATENDE - {len(encontrados)} servico(s) encontrado(s):")
            for e in encontrados:
                print(f"    Atestado #{e['atestado_id']} ({e['contratante']})")
                print(f"      [{e['item']}] {e['descricao']}")
                print(f"      Qtd: {e['quantidade']} {e['unidade']} | Keywords: {e['matched']}")
        else:
            print("  NAO ATENDE - Nenhum servico encontrado nos atestados")
        print()
