"""Atualiza CAT/ART faltantes nos atestados."""
import sys
sys.path.insert(0, '.')
from backend.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Dados extraidos dos PDFs das CATs
updates = {
    # #43 - Esperança - Creche FNDE
    43: {
        'cat': '226846/2026',
        'art': 'PB20230521884',
        'texto': """Certidão de Acervo Técnico - CAT
CREA-PB CAT COM REGISTRO DE ATESTADO
226846/2026
Atividade concluída
Profissional: WELLINGTON JARDEL RIBEIRO DE OLIVEIRA
Registro: 11216822020PB RNP: 1619113406
Título profissional: ENGENHEIRO CIVIL
Número da ART: PB20230521884 Tipo de ART: OBRA / SERVIÇO Registrada em: 28/03/2023 Baixada em: 04/02/2026
Forma de registro: SUBSTITUIÇÃO
Empresa contratada: WJX CONSTRUÇÕES E SERVIÇOS DE ENGENHARIA LTDA - EPP
Contratante: PREFEITURA MUNICIPAL DE ESPERANÇA CPF/CNPJ: 08.993.909/0001-08
Contrato: 0066/2023 Celebrado em: 01/03/2023
Valor do contrato: R$ 1.493.737,22
Cidade: ESPERANÇA UF: PB
Data de início: 20/03/2023 Conclusão efetiva: 18/03/2024
Finalidade: Escolar
Certidão de Acervo Técnico nº 226846/2026
ART nº PB20230521884 SUBSTITUIÇÃO à PB20230521277
Responsável Técnico: Wellington Jardel Ribeiro de Oliveira, CREA nº 161911340-6
Engenheiro Fiscal: Weslley Fernandes Câmara, CREA nº 161783213-8
Secretário de Obras: Welton Rodrigo de Almeida"""
    },
    # #45 - São José dos Cordeiros - Quadra Poliesportiva (sem CAT emitida ainda, mas adicionar ART)
    45: {
        'cat': None,
        'art': 'PB20240665173',
        'texto': """ATESTADO DE CAPACIDADE TÉCNICA
Prefeitura Municipal de São José dos Cordeiros, Rua Antero Torreão 59 - Centro - São José dos Cordeiros - PB, CNPJ nº 08.873.226/0001-09
Empresa: WJX CONSTRUÇÕES E SERVIÇOS DE ENGENHARIA LTDA - CNPJ nº 13.408.085/0001-93
Contrato de Empreitada N° 10107/2024-CPL, CONCORRÊNCIA ELETRÔNICA Nº 005/2024
Obra: CONSTRUÇÃO DE QUADRA POLIESPORTIVA
Período: 14 de outubro de 2024 à 18 de novembro de 2025
ART nº PB20240665173
Responsável Técnico: Wellington Jardel Ribeiro de Oliveira, CREA nº 161911340-6
Engenheiro Fiscal: Plinio Campos Medeiros
Prefeito: Felicio Kelmo Almeida Queiroz
São José dos Cordeiros, 25 de fevereiro de 2026."""
    }
}

for atestado_id, data in updates.items():
    if data['texto']:
        db.execute(text("""
            UPDATE atestados SET texto_extraido = :texto WHERE id = :id
        """), {'texto': data['texto'], 'id': atestado_id})
        print(f"Atestado #{atestado_id}: texto_extraido atualizado (CAT: {data['cat']}, ART: {data['art']})")

db.commit()

# Verificar resultado
import re
r = db.execute(text("""
    SELECT id, contratante, texto_extraido
    FROM atestados
    WHERE id IN (35, 37, 38, 41, 43, 45)
    ORDER BY id
""")).fetchall()

print("\n--- Verificação ---")
for x in r:
    txt = x.texto_extraido or ''
    cat_match = re.search(r'(\d{6}/\d{4})', txt)
    art_match = re.search(r'(PB\d{11,})', txt)
    cat = cat_match.group(1) if cat_match else '-'
    art = art_match.group(1) if art_match else '-'
    print(f"  #{x.id} | {x.contratante[:45]:<45} | CAT: {cat:<16} | ART: {art}")

db.close()
