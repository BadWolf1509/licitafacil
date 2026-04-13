import sys, json
sys.path.insert(0, '.')
from backend.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

descricao = 'CONSTRUÇÃO DE QUADRA POLIESPORTIVA'
contratante = 'Prefeitura Municipal de São José dos Cordeiros'
data_emissao = '2026-02-25'

texto_extraido = """ATESTADO DE CAPACIDADE TÉCNICA
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

servicos = [
    {"item": "1.1", "descricao": "Ligação Predial de Água em Mureta de Concreto, com Fornecimento de Material, exceto Mureta e Hidrômetro - Rev 03_10/2022", "unidade": "UN", "quantidade": 1.00},
    {"item": "1.2", "descricao": "Placa de obra em chapa aço galvanizado, instalada - Rev 02_01/2022", "unidade": "m²", "quantidade": 8.00},
    {"item": "2.1", "descricao": "Escavação manual de vala ou cava em material de 1ª categoria, profundidade até 1,50m", "unidade": "m³", "quantidade": 27.00},
    {"item": "2.2", "descricao": "REATERRO MANUAL APILOADO COM SOQUETE. AF_10/2017", "unidade": "m³", "quantidade": 58.83},
    {"item": "2.3", "descricao": "ATERRO COM AREIA COM ADENSAMENTO HIDRAULICO", "unidade": "m³", "quantidade": 337.54},
    {"item": "3.1", "descricao": "Escavação manual de vala ou cava em material de 1ª categoria, profundidade até 1,50m", "unidade": "m³", "quantidade": 40.00},
    {"item": "3.2", "descricao": "REATERRO MANUAL APILOADO COM SOQUETE. AF_10/2017", "unidade": "m³", "quantidade": 14.00},
    {"item": "3.3", "descricao": "LASTRO DE CONCRETO MAGRO, APLICADO EM PISOS, LAJES SOBRE SOLO OU RADIERS. AF_08/2017", "unidade": "m³", "quantidade": 2.00},
    {"item": "3.4", "descricao": "Concreto armado fck=15MPa fabricado na obra, adensado e lançado, para Uso Geral, com formas planas em compensado resinado 12mm (05 usos)", "unidade": "m³", "quantidade": 19.44},
    {"item": "4.1", "descricao": "Concreto Armado fck=30,0MPa, usinado, bombeado, adensado e lançado, para uso Geral, com formas planas em compensado resinado 12mm (05 usos)", "unidade": "m³", "quantidade": 14.82},
    {"item": "5.1", "descricao": "ALVENARIA DE VEDAÇÃO DE BLOCOS CERÂMICOS FURADOS NA HORIZONTAL DE 9X19X19 CM (ESPESSURA 9 CM) E ARGAMASSA DE ASSENTAMENTO COM PREPARO EM BETONEIRA. AF_12/2021", "unidade": "m²", "quantidade": 261.36},
    {"item": "5.2", "descricao": "ALVENARIA DE VEDAÇÃO COM ELEMENTO VAZADO DE CONCRETO (COBOGÓ) DE 7X50X50CM E ARGAMASSA DE ASSENTAMENTO COM PREPARO EM BETONEIRA. AF_05/2020", "unidade": "m²", "quantidade": 117.17},
    {"item": "5.3", "descricao": "CHAPISCO APLICADO EM ALVENARIAS E ESTRUTURAS DE CONCRETO INTERNAS, COM COLHER DE PEDREIRO. ARGAMASSA TRAÇO 1:3 COM PREPARO EM BETONEIRA 400L. AF_10/2022", "unidade": "m²", "quantidade": 503.46},
    {"item": "5.4", "descricao": "MASSA ÚNICA, PARA RECEBIMENTO DE PINTURA, EM ARGAMASSA TRAÇO 1:2:8, PREPARO MECÂNICO COM BETONEIRA 400L, APLICADA MANUALMENTE EM FACES INTERNAS DE PAREDES, ESPESSURA DE 10MM, COM EXECUÇÃO DE TALISCAS. AF_06/2014", "unidade": "m²", "quantidade": 406.73},
    {"item": "6.1", "descricao": "Impermeabilização - Aplicação de Frioasfalto - 01 demão", "unidade": "m²", "quantidade": 41.05},
    {"item": "7.1", "descricao": "ESTRUTURA METALICA EM ACO ESTRUTURAL PERFIL \"I\" 12' X 5 1/4'", "unidade": "KG", "quantidade": 8900.40},
    {"item": "7.2", "descricao": "Telhamento com telha metálica em chapa de aço galvanizado natural ondulada e=0,5mm", "unidade": "m²", "quantidade": 768.00},
    {"item": "7.3", "descricao": "Telhamento com telha metálica em chapa de aço galvanizado natural ondulada e=0,5mm", "unidade": "m²", "quantidade": 293.80},
    {"item": "8.1", "descricao": "Pavimentação em bloco de concreto vibroprensado, intertravado, colorido, 10x20cm, e=6cm, 46un/m2, NBR9781, Fck(min)=35MPa, sob coxim areia grossa compactada c/ placa vibratória, e(comp.)=6cm, rejuntado c/ areia fina.", "unidade": "m²", "quantidade": 164.85},
    {"item": "8.2", "descricao": "PISO EM CONCRETO 20 MPA PREPARO MECÂNICO, ESPESSURA 7CM. AF_09/2020", "unidade": "m²", "quantidade": 617.50},
    {"item": "8.3", "descricao": "Polimento de piso de alta resistência (existente)", "unidade": "m²", "quantidade": 617.50},
    {"item": "8.4", "descricao": "Lastro de brita 1", "unidade": "m³", "quantidade": 30.88},
    {"item": "8.5", "descricao": "Lona plástica preta", "unidade": "m²", "quantidade": 617.50},
    {"item": "8.6", "descricao": "LASTRO DE CONCRETO MAGRO, APLICADO EM PISOS, LAJES SOBRE SOLO OU RADIERS. AF_08/2017", "unidade": "m³", "quantidade": 3.05},
    {"item": "8.7", "descricao": "CONTRAPISO EM ARGAMASSA TRAÇO 1:4 (CIMENTO E AREIA), PREPARO MECÂNICO COM BETONEIRA 400 L, APLICADO EM ÁREAS MOLHADAS SOBRE IMPERMEABILIZAÇÃO, ACABAMENTO NÃO REFORÇADO, ESPESSURA 3CM. AF_07/2021", "unidade": "m²", "quantidade": 30.88},
    {"item": "9.1", "descricao": "QUADRO DE DISTRIBUIÇÃO DE ENERGIA DE EMBUTIR, EM CHAPA METÁLICA, PARA 18 DISJUNTORES TERMOMAGNÉTICOS MONOPOLARES, COM BARRAMENTO TRIFÁSICO E NEUTRO, FORNECIMENTO E INSTALAÇÃO", "unidade": "UN", "quantidade": 1.00},
    {"item": "9.2", "descricao": "Disjuntor termomagnético trifásico 32 A, padrão DIN (linha branca)", "unidade": "UN", "quantidade": 1.00},
    {"item": "9.3", "descricao": "DISJUNTOR TERMOMAGNÉTICO MONOPOLAR PADRÃO NEMA (AMERICANO) 10 A 30A 240V, FORNECIMENTO E INSTALAÇÃO", "unidade": "UN", "quantidade": 1.00},
    {"item": "9.4", "descricao": "ELETRODUTO FLEXÍVEL CORRUGADO, PVC, DN 25 MM (3/4\"), PARA CIRCUITOS TERMINAIS, INSTALADO EM PAREDE - FORNECIMENTO E INSTALAÇÃO. AF_03/2023", "unidade": "M", "quantidade": 200.00},
    {"item": "9.5", "descricao": "ELETRODUTO RÍGIDO ROSCÁVEL, PVC, DN 32 MM (1\"), PARA CIRCUITOS TERMINAIS, INSTALADO EM PAREDE - FORNECIMENTO E INSTALAÇÃO.", "unidade": "M", "quantidade": 200.00},
    {"item": "9.6", "descricao": "CONDULETE DE PVC, TIPO B, PARA ELETRODUTO DE PVC SOLDÁVEL DN 25 MM (3/4''), APARENTE - FORNECIMENTO E INSTALAÇÃO. AF_10/2022", "unidade": "UN", "quantidade": 65.00},
    {"item": "9.7", "descricao": "CABO DE COBRE FLEXÍVEL ISOLADO, 2,5 MM², ANTI-CHAMA 450/750 V, PARA CIRCUITOS TERMINAIS - FORNECIMENTO E INSTALAÇÃO. AF_03/2023", "unidade": "M", "quantidade": 450.00},
    {"item": "9.8", "descricao": "CABO DE COBRE FLEXÍVEL ISOLADO, 6 MM², ANTI-CHAMA 450/750 V, PARA CIRCUITOS TERMINAIS - FORNECIMENTO E INSTALAÇÃO. AF_03/2023", "unidade": "M", "quantidade": 150.00},
    {"item": "9.9", "descricao": "REFLETOR REDONDO EM ALUMÍNIO COM SUPORTE E ALÇA REGULÁVEL PARA FIXAÇÃO, COM LÂMPADA VAPOR DE MERCÚRIO 250W", "unidade": "UN", "quantidade": 30.00},
    {"item": "9.10", "descricao": "DISJUNTOR TERMOMAGNÉTICO MONOPOLAR PADRÃO NEMA (AMERICANO) 10 A 30A 240V, FORNECIMENTO E INSTALAÇÃO", "unidade": "UN", "quantidade": 1.00},
    {"item": "9.11", "descricao": "CAIXA RETANGULAR 4\" X 2\" MÉDIA (1,30 M DO PISO), PVC, INSTALADA EM PAREDE - FORNECIMENTO E INSTALAÇÃO. AF_03/2023", "unidade": "UN", "quantidade": 4.00},
    {"item": "9.12", "descricao": "INTERRUPTOR PARALELO (2 MÓDULOS), 10A/250V, INCLUINDO SUPORTE E PLACA - FORNECIMENTO E INSTALAÇÃO. AF_03/2023", "unidade": "UN", "quantidade": 4.00},
    {"item": "10.1", "descricao": "HASTE COPPERWELD 5/8\" X 3,0M COM CONECTOR", "unidade": "UN", "quantidade": 4.00},
    {"item": "10.2", "descricao": "Caixa de inspeção 0,30 x 0,30 x 0,40m", "unidade": "UN", "quantidade": 4.00},
    {"item": "10.3", "descricao": "Conector de bronze d=22mm x 3/4\"", "unidade": "UN", "quantidade": 4.00},
    {"item": "10.4", "descricao": "CORDOALHA DE COBRE NU 25 MM², NÃO ENTERRADA, COM ISOLADOR - FORNECIMENTO E INSTALAÇÃO. AF_12/2017", "unidade": "M", "quantidade": 150.00},
    {"item": "11.1", "descricao": "Pintura para exteriores, sobre paredes, com lixamento, aplicação de 01 demão de líquido selador acrílico e 02 demãos de tinta pva latex convencional para exteriores", "unidade": "m²", "quantidade": 654.60},
    {"item": "11.2", "descricao": "PINTURA ESMALTE ACETINADO, DUAS DEMÃOS, SOBRE SUPERFÍCIE METÁLICA", "unidade": "m²", "quantidade": 674.78},
    {"item": "11.3", "descricao": "PINTURA ACRÍLICA EM PISO CIMENTADO DUAS DEMÃOS", "unidade": "m²", "quantidade": 617.50},
    {"item": "11.4", "descricao": "PINTURA DE DEMARCAÇÃO DE QUADRA POLIESPORTIVA COM TINTA ACRÍLICA, E = 5 CM, APLICAÇÃO MANUAL. AF_05/2021", "unidade": "M", "quantidade": 300.00},
    {"item": "12.1", "descricao": "CONJUNTO PARA FUTSAL COM TRAVES OFICIAIS DE 3,00 X 2,00 M EM TUBO DE AÇO GALVANIZADO 3\" COM REQUADRO EM TUBO DE 1\", PINTURA EM PRIMER COM TINTA ESMALTE SINTÉTICO E REDES", "unidade": "CJ", "quantidade": 1.00},
    {"item": "12.2", "descricao": "ALAMBRADO PARA QUADRA POLIESPORTIVA, ESTRUTURADO POR TUBOS DE AÇO GALVANIZADO, (MONTANTES COM DIÂMETRO 2\", TRAVESSAS E ESCORAS COM DIÂMETRO 1 ¼\"), COM TELA DE ARAME GALVANIZADO, FIO 14 BWG E MALHA QUADRADA 5X5CM (EXCETO MURETA). AF_03/2021", "unidade": "m²", "quantidade": 168.00}
]

servicos_json = json.dumps(servicos, ensure_ascii=False)

result = db.execute(text("""
    INSERT INTO atestados (user_id, descricao_servico, contratante, data_emissao, texto_extraido, servicos_json)
    VALUES (:user_id, :descricao, :contratante, :data_emissao, :texto_extraido, CAST(:servicos_json AS jsonb))
    RETURNING id
"""), {
    'user_id': 1,
    'descricao': descricao,
    'contratante': contratante,
    'data_emissao': data_emissao,
    'texto_extraido': texto_extraido,
    'servicos_json': servicos_json
})

new_id = result.fetchone()[0]
db.commit()
print(f'Atestado inserido com sucesso! ID: {new_id}')

r = db.execute(text('SELECT COUNT(*) FROM atestados')).fetchone()
print(f'Total de atestados agora: {r[0]}')

db.close()
