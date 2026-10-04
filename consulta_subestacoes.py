"""Conta e detalha subestacoes (com foco nas AEREAS) nos atestados da WJX.

Busca em tres frentes, porque a informacao pode estar em qualquer uma:
  1. itens de servico extraidos (servicos_json)
  2. descricao_servico do atestado
  3. texto_extraido da CAT (fallback, quando a extracao nao itemizou)

Uso:  .venv/Scripts/python.exe consulta_subestacoes.py
"""
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from backend.database import SessionLocal  # noqa: E402


def sem_acento(s):
    """Normaliza para comparacao: minusculas, sem acento, espacos colapsados."""
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', s).lower()


# Classificacao do tipo de subestacao a partir da descricao
AEREA = re.compile(r'aere|em poste|sobre poste|no poste|posteacao')
NAO_AEREA = re.compile(r'abrigad|alvenaria|cabine|pedestal|blindad|compacta|enterrad|subterran|interna')


def classificar(desc):
    d = sem_acento(desc)
    if AEREA.search(d):
        return 'AEREA'
    if NAO_AEREA.search(d):
        return 'NAO-AEREA'
    return 'INDEFINIDA'


def main():
    db = SessionLocal()

    # ---------------------------------------------------------------- itens
    itens = db.execute(text("""
        SELECT a.id, a.contratante, a.data_emissao,
               s->>'item'        AS item,
               s->>'descricao'   AS descricao,
               s->>'quantidade'  AS quantidade,
               s->>'unidade'     AS unidade
        FROM atestados a,
             jsonb_array_elements(COALESCE(a.servicos_json, '[]'::jsonb)) AS s
        WHERE LOWER(s->>'descricao') LIKE '%subesta%'
        ORDER BY a.id, s->>'item'
    """)).fetchall()

    print('=' * 160)
    print('1) ITENS DE SERVICO COM "SUBESTA" (servicos_json)')
    print('=' * 160)
    print(f'  {len(itens)} item(ns)\n')

    por_tipo = {}
    atestados_aereos = set()
    qtd_aerea = 0.0

    for x in itens:
        tipo = classificar(x.descricao)
        por_tipo.setdefault(tipo, []).append(x)
        if tipo == 'AEREA':
            atestados_aereos.add(x.id)
            try:
                qtd_aerea += float(str(x.quantidade).replace(',', '.'))
            except (TypeError, ValueError):
                pass

    for tipo in ('AEREA', 'INDEFINIDA', 'NAO-AEREA'):
        linhas = por_tipo.get(tipo, [])
        print(f'  --- {tipo}: {len(linhas)} item(ns) ---')
        for x in linhas:
            emissao = str(x.data_emissao)[:10] if x.data_emissao else 'N/A'
            print(f'    Atestado #{x.id} | {x.contratante} | emissao {emissao}')
            print(f'      Item {x.item}: {x.descricao}')
            print(f'      Qtd: {x.quantidade} {x.unidade or ""}')
        print()

    # ------------------------------------------------- descricao_servico
    print('=' * 160)
    print('2) ATESTADOS COM "SUBESTA" NA descricao_servico')
    print('=' * 160)
    descs = db.execute(text("""
        SELECT id, contratante, data_emissao, quantidade, unidade, descricao_servico
        FROM atestados
        WHERE LOWER(descricao_servico) LIKE '%subesta%'
        ORDER BY id
    """)).fetchall()
    print(f'  {len(descs)} atestado(s)\n')
    for x in descs:
        emissao = str(x.data_emissao)[:10] if x.data_emissao else 'N/A'
        print(f'  #{x.id} [{classificar(x.descricao_servico)}] | {x.contratante} | {emissao} '
              f'| {x.quantidade} {x.unidade or ""}')
        print(f'    {str(x.descricao_servico)[:400]}')
        print()

    # --------------------------------------------------- texto_extraido
    print('=' * 160)
    print('3) OCORRENCIAS EM texto_extraido (com contexto, para conferencia manual)')
    print('=' * 160)
    brutos = db.execute(text("""
        SELECT id, contratante, data_emissao, texto_extraido
        FROM atestados
        WHERE LOWER(texto_extraido) LIKE '%subesta%'
        ORDER BY id
    """)).fetchall()
    print(f'  {len(brutos)} atestado(s)\n')
    for x in brutos:
        txt = re.sub(r'\s+', ' ', x.texto_extraido or '')
        hits = [m.start() for m in re.finditer(r'(?i)subesta', txt)]
        emissao = str(x.data_emissao)[:10] if x.data_emissao else 'N/A'
        print(f'  #{x.id} | {x.contratante} | {emissao} | {len(hits)} ocorrencia(s)')
        for h in hits[:15]:
            trecho = txt[max(0, h - 130):h + 200]
            print(f'      [{classificar(trecho)}] ...{trecho}...')
        print()

    # ------------------------------------------------------------ resumo
    print('=' * 160)
    print('RESUMO')
    print('=' * 160)
    total = db.execute(text('SELECT COUNT(*) FROM atestados')).scalar()
    print(f'  Atestados na base ................................: {total}')
    print(f'  Atestados com item de subestacao AEREA ...........: {len(atestados_aereos)} '
          f'{sorted(atestados_aereos) if atestados_aereos else ""}')
    print(f'  Itens de subestacao AEREA ........................: {len(por_tipo.get("AEREA", []))}')
    print(f'  Soma das quantidades dos itens AEREOS ............: {qtd_aerea:,.2f}')
    print(f'  Itens de subestacao de tipo INDEFINIDO ...........: {len(por_tipo.get("INDEFINIDA", []))}'
          '  <-- conferir no texto da CAT')
    print(f'  Itens de subestacao NAO-AEREA ....................: {len(por_tipo.get("NAO-AEREA", []))}')
    print(f'  Atestados citando "subesta" no texto bruto .......: {len(brutos)}')
    print()
    print('  OBS: a contagem AEREA vem da descricao dos itens. Itens INDEFINIDOS nao afirmam')
    print('       que nao sao aereos - apenas que a descricao nao diz o tipo. Confira a secao 3.')

    db.close()


if __name__ == '__main__':
    try:
        main()
    except OperationalError as e:
        primeira = str(e.orig).strip().splitlines()[0] if e.orig else str(e)
        print('ERRO: nao foi possivel conectar ao banco.')
        print(f'  {primeira}')
        print()
        print('  Verifique o DATABASE_URL no .env (project ref / senha / host do pooler).')
        sys.exit(1)
