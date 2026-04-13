import sys, json
sys.path.insert(0, '.')
from backend.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

descricao = 'EXECUÇÃO DOS SERVIÇOS DE PAVIMENTAÇÃO EM PARALELEPÍPEDO E DRENAGEM NO BAIRRO DA VÁRZEA NO MUNICÍPIO DE BAÍA DA TRAIÇÃO - PB'
contratante = 'Prefeitura Municipal de Baia da Traição'
data_emissao = '2025-12-15'

texto_extraido = """Certidão de Acervo Técnico - CAT
CREA-PB CAT COM REGISTRO DE ATESTADO
227542/2026
Atividade concluída
Profissional: WELLINGTON JARDEL RIBEIRO DE OLIVEIRA
Registro: 11216822020PB RNP: 1619113406
Título profissional: ENGENHEIRO CIVIL
Número da ART: PB20240599779 Tipo de ART: OBRA / SERVIÇO Registrada em: 21/02/2024 Baixada em: 25/02/2026
Empresa contratada: WJX CONSTRUÇÕES E SERVIÇOS DE ENGENHARIA LTDA - EPP
Contratante: Prefeitura Municipal de Baia da Traição CPF/CNPJ: 08.894.859/0001-01
Contrato: 00044/2024-CPL Celebrado em: 19/02/2024
Valor do contrato: R$ 287.691,35
Cidade: BAÍA DA TRAIÇÃO UF: PB
Data de início: 29/02/2024 Conclusão efetiva: 24/05/2024
Finalidade: Infraestrutura
Atividade Técnica: 16 - Execução TRANSPORTES > INFRAESTRUTURA URBANA > DE PAVIMENTAÇÃO > #4.2.1.3 - EM PARALELEPÍPEDO PARA VIAS URBANAS 49 - Execução de obra 1522.53 metro quadrado; 16 - Execução OBRAS HIDRÁULICAS E RECURSOS HÍDRICOS > SISTEMAS DE DRENAGEM PARA OBRAS CIVIS > DE SISTEMAS DE DRENAGEM PARA OBRAS CIVIS > #5.3.1.7 - MEIO-FIO 49 - Execução de obra 618.05 metro;
Certidão de Acervo Técnico nº 227542/2026
ART nº PB20240599779
Responsável Técnico: Wellington Jardel Ribeiro de Oliveira, CREA nº 161911340-6
ART DE FISCALIZAÇÃO: PB20250751508 - Gabriel Victor de Oliveira Barbosa, CREA: 161987504-7"""

servicos = [
    {"item": "1.1", "descricao": "PLACA DE OBRA EM CHAPA DE AÇO GALVANIZADO", "unidade": "m²", "quantidade": 8.00},
    {"item": "1.2", "descricao": "LOCAÇÃO DE PAVIMENTAÇÃO. AF_10/2018", "unidade": "M", "quantidade": 293.61},
    {"item": "2.1", "descricao": "REGULARIZAÇÃO E COMPACTAÇÃO DE SUBLEITO DE SOLO PREDOMINANTEMENTE ARGILOSO. AF_11/2019", "unidade": "m²", "quantidade": 1522.53},
    {"item": "3.1", "descricao": "EXECUÇÃO DE PAVIMENTO EM PARALELEPÍPEDOS, REJUNTAMENTO COM ARGAMASSA TRAÇO 1:3 (CIMENTO E AREIA). AF_05/2020", "unidade": "m²", "quantidade": 1522.53},
    {"item": "3.2", "descricao": "ASSENTAMENTO DE GUIA (MEIO-FIO) EM TRECHO RETO, CONFECCIONADA EM CONCRETO PRÉ-FABRICADO, DIMENSÕES 100X15X13X30 CM (COMPRIMENTO X BASE INFERIOR X BASE SUPERIOR X ALTURA), PARA VIAS URBANAS (USO VIÁRIO). AF_06/2016", "unidade": "M", "quantidade": 618.05},
    {"item": "4.1", "descricao": "COMPACTAÇÃO MECÂNICA DE SOLO PARA EXECUÇÃO DE RADIER, PISO DE CONCRETO OU LAJE SOBRE SOLO, COM COMPACTADOR DE SOLOS TIPO PLACA VIBRATÓRIA. AF_09/2021", "unidade": "m²", "quantidade": 711.66},
    {"item": "4.2", "descricao": "EXECUÇÃO DE PASSEIO (CALÇADA) OU PISO DE CONCRETO COM CONCRETO MOLDADO IN LOCO, FEITO EM OBRA, ACABAMENTO CONVENCIONAL, NÃO ARMADO. AF_08/2022", "unidade": "m³", "quantidade": 27.79},
    {"item": "4.3", "descricao": "RAMPA DE ACESSIBILIDADE (PASSEIO 1,2M) [PROJETO ESPECÍFICO]", "unidade": "UN", "quantidade": 12.00},
    {"item": "4.4", "descricao": "PISO TÁTIL DIRECIONAL E DE ALERTA, EM CONCRETO COLORIDO, P/DEFICIENTES VISUAIS, DIMENSÕES 25X25CM, APLICADO COM ARGAMASSA INDUSTRIALIZADA AC-II, REJUNTADO, EXCLUSIVE REGULARIZAÇÃO DE BASE", "unidade": "m²", "quantidade": 126.01},
    {"item": "4.5", "descricao": "PINTURA DE MEIO-FIO COM TINTA BRANCA A BASE DE CAL (CAIAÇÃO). AF_05/2021", "unidade": "M", "quantidade": 593.05},
    {"item": "4.6", "descricao": "LIMPEZA FINAL COM VARRIÇÃO E REMOÇÃO DE ENTULHOS", "unidade": "m²", "quantidade": 2234.19},
    {"item": "5.1", "descricao": "LOCAÇÃO DE REDE DE ÁGUA OU ESGOTO. AF_10/2018", "unidade": "M", "quantidade": 32.59},
    {"item": "5.2", "descricao": "COMPACTAÇÃO MECÂNICA DE SOLO PARA EXECUÇÃO DE RADIER, PISO DE CONCRETO OU LAJE SOBRE SOLO, COM COMPACTADOR DE SOLOS TIPO PLACA VIBRATÓRIA. AF_09/2021", "unidade": "m²", "quantidade": 17.84},
    {"item": "5.3", "descricao": "LASTRO COM MATERIAL GRANULAR (AREIA MÉDIA), APLICADO EM PISOS OU LAJES SOBRE SOLO, ESPESSURA DE 10 CM. AF_07/2019", "unidade": "m³", "quantidade": 7.14},
    {"item": "5.4", "descricao": "BOCA PARA BUEIRO SIMPLES TUBULAR D = 100 CM EM CONCRETO, ALAS COM ESCONSIDADE DE 0°, INCLUINDO FÔRMAS E MATERIAIS. AF_07/2021", "unidade": "UN", "quantidade": 2.00},
    {"item": "5.5", "descricao": "TUBO DE CONCRETO PARA REDES COLETORAS DE ÁGUAS PLUVIAIS, DIÂMETRO DE 1000 MM, JUNTA RÍGIDA, INSTALADO EM LOCAL COM BAIXO NÍVEL DE INTERFERÊNCIAS - FORNECIMENTO E ASSENTAMENTO. AF_12/2015", "unidade": "M", "quantidade": 12.39},
    {"item": "5.6", "descricao": "ESCAVAÇÃO MECANIZADA DE VALA COM PROFUNDIDADE ATÉ 1,5 M, RETROESCAV. (0,26 M3), LARGURA DE 0,8 M A 1,5 M, EM SOLO DE 1A CATEGORIA, LOCAIS COM BAIXO NÍVEL DE INTERFERÊNCIA. AF_02/2021", "unidade": "m³", "quantidade": 25.97},
    {"item": "5.7", "descricao": "REATERRO MECANIZADO DE VALA COM RETROESCAVADEIRA (CAPACIDADE DA CAÇAMBA DA RETRO: 0,26 M³ / POTÊNCIA: 88 HP), LARGURA DE 0,8 A 1,5 M, PROFUNDIDADE ATÉ 1,5 M, COM SOLO DE 1ª CATEGORIA EM LOCAIS COM BAIXO NÍVEL DE INTERFERÊNCIA. AF_04/2016", "unidade": "m³", "quantidade": 11.20},
    {"item": "5.8", "descricao": "LASTRO COM MATERIAL GRANULAR (AREIA MÉDIA), APLICADO EM PISOS OU LAJES SOBRE SOLO, ESPESSURA DE 10 CM. AF_07/2019", "unidade": "m³", "quantidade": 8.44},
    {"item": "5.9", "descricao": "COMPACTAÇÃO MECÂNICA DE SOLO PARA EXECUÇÃO DE RADIER, PISO DE CONCRETO OU LAJE SOBRE SOLO, COM COMPACTADOR DE SOLOS TIPO PLACA VIBRATÓRIA. AF_09/2021", "unidade": "m²", "quantidade": 29.26},
    {"item": "5.10", "descricao": "ESCORAMENTO DE VALA, TIPO CONTÍNUO, COM PROFUNDIDADE DE 0 A 1,5 M, LARGURA MENOR QUE 1,5 M. AF_08/2020", "unidade": "m²", "quantidade": 43.59},
    {"item": "5.11", "descricao": "TUBO DE CONCRETO (SIMPLES) PARA REDES COLETORAS DE ÁGUAS PLUVIAIS, DIÂMETRO DE 400 MM, JUNTA RÍGIDA, INSTALADO EM LOCAL COM BAIXO NÍVEL DE INTERFERÊNCIAS - FORNECIMENTO E ASSENTAMENTO. AF_12/2015", "unidade": "M", "quantidade": 5.20},
    {"item": "5.12", "descricao": "TUBO DE CONCRETO PARA REDES COLETORAS DE ÁGUAS PLUVIAIS, DIÂMETRO DE 600 MM, JUNTA RÍGIDA, INSTALADO EM LOCAL COM BAIXO NÍVEL DE INTERFERÊNCIAS - FORNECIMENTO E ASSENTAMENTO. AF_12/2015", "unidade": "M", "quantidade": 15.00},
    {"item": "5.13", "descricao": "CAIXA PARA BOCA DE LOBO SIMPLES RETANGULAR, EM CONCRETO PRÉ-MOLDADO, DIMENSÕES INTERNAS: 0,6X1,0X1,2 M. AF_12/2020", "unidade": "UN", "quantidade": 2.00},
    {"item": "5.14", "descricao": "BOCA PARA BUEIRO SIMPLES TUBULAR D = 60 CM EM CONCRETO, ALAS COM ESCONSIDADE DE 0°, INCLUINDO FÔRMAS E MATERIAIS. AF_07/2021", "unidade": "UN", "quantidade": 1.00},
    {"item": "5.15", "descricao": "CARGA, MANOBRA E DESCARGA DE SOLOS E MATERIAIS GRANULARES EM CAMINHÃO BASCULANTE 6 M³ - CARGA COM ESCAVADEIRA HIDRÁULICA (CAÇAMBA DE 1,20 M³ / 155 HP) E DESCARGA LIVRE (UNIDADE: M3). AF_07/2020", "unidade": "m³", "quantidade": 18.46},
    {"item": "5.16", "descricao": "TRANSPORTE DE ENTULHO COM CAMINHÃO BASCULANTE 6 M3, RODOVIA PAVIMENTADA, DMT ATE 0,5 KM", "unidade": "m³", "quantidade": 18.46},
    {"item": "6.1", "descricao": "PLACA ESMALTADA PARA IDENTIFICAÇÃO NR DE RUA, DIMENSÕES 45X25CM", "unidade": "UN", "quantidade": 5.00},
    {"item": "6.2", "descricao": "Placa em aço - película I + I - fornecimento e implantação", "unidade": "m²", "quantidade": 2.52}
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

# Verificar
r = db.execute(text('SELECT COUNT(*) FROM atestados')).fetchone()
print(f'Total de atestados agora: {r[0]}')

db.close()
