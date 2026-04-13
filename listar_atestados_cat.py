import sys, re
sys.path.insert(0, '.')
from backend.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
r = db.execute(text("""
    SELECT id, contratante, descricao_servico, data_emissao, texto_extraido,
           jsonb_array_length(COALESCE(servicos_json, '[]'::jsonb)) AS qtd_servicos
    FROM atestados
    ORDER BY id
""")).fetchall()

print(f"Total: {len(r)} atestados\n")
print(f"{'ID':<5} | {'CAT':<16} | {'ART':<18} | {'Contratante':<48} | {'Data':<12} | {'Itens':>5} | Descricao")
print("-" * 190)

for x in r:
    desc = str(x.descricao_servico)[:65] if x.descricao_servico else 'N/A'
    data = str(x.data_emissao)[:10] if x.data_emissao else 'N/A'
    txt = x.texto_extraido or ''

    # Extrair CAT
    cat_match = re.search(r'(?:Certid.o de Acervo T.cnico n.\s*|CAT COM REGISTRO DE ATESTADO\s*\n?\s*|CAT COM REGISTRO DE ATESTADO\s+)(\d{5,}/\d{4})', txt)
    if not cat_match:
        cat_match = re.search(r'(\d{6}/\d{4})', txt)
    cat = cat_match.group(1) if cat_match else '-'

    # Extrair ART
    art_match = re.search(r'(?:ART[:\s]+|ART n.\s*|N.mero da ART:\s*)(PB\d{11,})', txt, re.IGNORECASE)
    if not art_match:
        art_match = re.search(r'(PB\d{11,})', txt)
    art = art_match.group(1) if art_match else '-'

    print(f"#{x.id:<4} | {cat:<16} | {art:<18} | {x.contratante[:48]:<48} | {data:<12} | {x.qtd_servicos:>5} | {desc}")

db.close()
