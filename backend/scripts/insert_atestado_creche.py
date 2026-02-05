"""
Script para inserir atestado da Creche Esperança no banco de dados.
Executar do diretório backend: python scripts/insert_atestado_creche.py
"""
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Adicionar backend ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_db_session
from models import Atestado, Usuario


# Dados extraídos do PDF
CONTRATANTE = "Prefeitura Municipal de Esperança - PB"
DATA_EMISSAO = datetime(2026, 2, 3)
DESCRICAO_GERAL = """EXECUÇÃO DE SERVIÇOS DE RETOMADA DAS OBRAS REMANESCENTES DA CRECHE PRÓ-INFÂNCIA, ATRAVÉS DE CONVÊNIO COM O FNDE (FUNDO NACIONAL DE DESENVOLVIMENTO DA EDUCAÇÃO), NO BAIRRO DA BELA VISTA, MUNICÍPIO DE ESPERANÇA/PB.

Contrato: 0066/2023 - Tomada de Preço Nº 012/2022
Período: 20/03/2023 à 04/11/2025
ART: PB20230521884
Responsável Técnico: Wellington Jardel Ribeiro de Oliveira (CREA 161911340-6)
Empresa: WJX Construções e Serviços de Engenharia LTDA (CNPJ 13.408.085/0001-93)"""

# Lista de serviços executados
SERVICOS = [
    # Página 1
    {"item": "5.1.1", "descricao": "Cobogó de concreto (elemento vazado) - (6x40x40cm) assentado com argamassa traço 1:4 (cimento, areia)", "quantidade": 5.14, "unidade": "m²"},
    {"item": "5.2.2", "descricao": "Divisória de banheiros e sanitários em granito com espessura de 2cm polido assentado com argamassa traço 1:4", "quantidade": 22.63, "unidade": "m²"},
    {"item": "6.1.1", "descricao": "Porta de Madeira - PM1 - 70x210, folha lisa com chapa metálica, incluso ferragens, conforme projeto de esquadrias", "quantidade": 10.00, "unidade": "und"},
    {"item": "6.1.2", "descricao": "Porta de Madeira - PM2 - 80x210, com veneziana, incluso ferragens, conforme projeto de esquadrias", "quantidade": 5.00, "unidade": "und"},
    {"item": "6.1.3", "descricao": "Porta de Madeira - PM3 - 80x210, barra e chapa metálica, incluso ferragens, conforme projeto de esquadrias", "quantidade": 4.00, "unidade": "und"},
    {"item": "6.1.4", "descricao": "Porta de Madeira - PM4 - 80x210, folha lisa com chapa metálica, incluso ferragens, conforme projeto de esquadrias", "quantidade": 6.00, "unidade": "und"},
    {"item": "6.1.5", "descricao": "Porta de Madeira - PM5 - 80x210, com barra e chapa metálica e visor, incluso ferragens, conforme projeto de esquadrias", "quantidade": 10.00, "unidade": "und"},
    {"item": "6.2.1", "descricao": "Fechadura de embutir completa, para portas internas", "quantidade": 51.00, "unidade": "und"},
    {"item": "6.3.1", "descricao": "Porta de abrir - PA1 - 100x210 em chapa de alumínio e veneziana conforme projeto de esquadrias, inclusive ferragens", "quantidade": 2.31, "unidade": "m²"},
    {"item": "6.3.2", "descricao": "Porta de abrir - PA2 - 80x210 em chapa de alumínio com veneziana conforme projeto de esquadrias, inclusive ferragens", "quantidade": 1.68, "unidade": "m²"},
    {"item": "6.3.3", "descricao": "Porta de abrir - PA3 - 160x210 em chapa de alumínio com veneziana conforme projeto de esquadrias, inclusive ferragens", "quantidade": 6.72, "unidade": "m²"},
    {"item": "6.3.4", "descricao": "Porta de correr - PA4 - 450x210 conforme projeto de esquadrias, inclusive ferragens", "quantidade": 113.40, "unidade": "m²"},
    {"item": "6.3.5", "descricao": "Porta de correr - PA5 - 240x210 com vidro - conforme projeto de esquadrias, inclusive ferragens", "quantidade": 5.04, "unidade": "m²"},
    {"item": "6.3.6", "descricao": "Porta de abrir - PA6 - 120x185 - veneziana- conforme projeto de esquadrias, inclusive ferragens", "quantidade": 4.44, "unidade": "m²"},
    {"item": "6.3.7", "descricao": "Porta de abrir - PA7 - 160+90x210 - veneziana- conforme projeto de esquadrias, inclusive ferragens", "quantidade": 5.25, "unidade": "m²"},
    {"item": "6.4.1", "descricao": "Porta de Vidro temperado - PV1 - 175x230, com ferragens, conforme projeto de esquadrias", "quantidade": 1.00, "unidade": "und"},
    {"item": "6.4.2", "descricao": "Porta de Vidro temperado - PV2 - 110x230, de abrir, com ferragens, conforme projeto de esquadrias", "quantidade": 1.00, "unidade": "und"},
    {"item": "6.4.3", "descricao": "Bandeiras fixas de vidro para porta PV2, conforme projeto 175x35", "quantidade": 0.61, "unidade": "m²"},
    {"item": "6.5.1", "descricao": "Janela de Alumínio - JA-01, 70x125, completa conforme projeto de esquadrias - Guilhotina", "quantidade": 1.75, "unidade": "m²"},
    {"item": "6.5.2", "descricao": "Janela de Alumínio - JA-02, 110x145, completa conforme projeto de esquadrias - Guilhotina", "quantidade": 1.60, "unidade": "m²"},
    {"item": "6.5.3", "descricao": "Vidro fixo - JA-03, 140x115, completa conforme projeto de esquadrias", "quantidade": 3.22, "unidade": "m²"},
    {"item": "6.5.4", "descricao": "Janela de Alumínio - JA-04, 140x145, completa conforme projeto de esquadrias - Guilhotina", "quantidade": 2.03, "unidade": "m²"},
    {"item": "6.5.5", "descricao": "Janela de Alumínio - JA-05, 200x105, completa conforme projeto de esquadrias - Fixa", "quantidade": 2.10, "unidade": "m²"},
    {"item": "6.5.6", "descricao": "Janela de Alumínio - JA-06, 210x50, completa conforme projeto de esquadrias - Maxim-ar - incluso vidro liso incolor, espessura 6mm", "quantidade": 2.10, "unidade": "m²"},
    {"item": "6.5.7", "descricao": "Janela de Alumínio - JA-07, 210x75, completa conforme projeto de esquadrias - Maxim-ar - incluso vidro liso incolor, espessura 6mm", "quantidade": 12.60, "unidade": "m²"},
    {"item": "6.5.8", "descricao": "Janela de Alumínio - JA-08, 210x100, completa conforme projeto de esquadrias - Maxim-ar - incluso vidro liso incolor, espessura 6mm", "quantidade": 6.30, "unidade": "m²"},
    {"item": "6.5.9", "descricao": "Janela de Alumínio - JA-09, 210x150, completa conforme projeto de esquadrias - Maxim-ar - incluso vidro liso incolor, espessura 6mm", "quantidade": 18.90, "unidade": "m²"},
    {"item": "6.5.10", "descricao": "Janela de Alumínio - JA-10, 140x150, completa conforme projeto de esquadrias - Maxim-ar - incluso vidro liso incolor, espessura 6mm", "quantidade": 2.10, "unidade": "m²"},
    {"item": "6.5.11", "descricao": "Janela de Alumínio - JA-11, 140x75, completa conforme projeto de esquadrias - Maxim-ar - incluso vidro liso incolor, espessura 6mm", "quantidade": 6.30, "unidade": "m²"},
    {"item": "6.5.12", "descricao": "Janela de Alumínio - JA-12, 420x50, completa conforme projeto de esquadrias - Maxim-ar - incluso vidro liso incolor, espessura 6mm", "quantidade": 8.40, "unidade": "m²"},
    {"item": "6.5.13", "descricao": "Janela de Alumínio - JA-13, 420x150, completa conforme projeto de esquadrias - Maxim-ar - incluso vidro liso incolor, espessura 6mm", "quantidade": 12.60, "unidade": "m²"},
    {"item": "6.5.14", "descricao": "Janela de Alumínio - JA-14, 560x100, completa conforme projeto de esquadrias - Maxim-ar - incluso vidro liso incolor, espessura 6mm", "quantidade": 33.60, "unidade": "m²"},
    {"item": "6.5.15", "descricao": "Janela de Alumínio - JA-15, 560x150, completa conforme projeto de esquadrias - Maxim-ar - incluso vidro liso incolor, espessura 6mm", "quantidade": 16.80, "unidade": "m²"},
    {"item": "6.6.1", "descricao": "Vidro liso temperado incolor, espessura 6mm- fornecimento e instalação", "quantidade": 10.70, "unidade": "m²"},
    {"item": "6.7.1", "descricao": "Gradil metálico e tela de aço galvanizado, inclusive pintura - fornecimento e instalação (GR1, GR2, GR3, GR4)", "quantidade": 50.22, "unidade": "m²"},
    {"item": "6.7.4", "descricao": "Portão de abrir com gradil metálico e tela de aço galvanizado, inclusive pintura - fornecimento e instalação", "quantidade": 13.50, "unidade": "m²"},
    {"item": "10.1.2", "descricao": "Piso cerâmico antiderrapante PEI V - 40 x 40 cm - incl. rejunte - conforme projeto", "quantidade": 226.97, "unidade": "m²"},
    {"item": "10.1.3", "descricao": "Piso cerâmico antiderrapante PEI V - 60 x 60 cm - incl. rejunte - conforme projeto", "quantidade": 355.53, "unidade": "m²"},
    {"item": "10.1.5", "descricao": "Piso podotátil de alerta em borracha integrado 30x30cm, assentamento com argamassa (fornecimento e assentamento)", "quantidade": 27.90, "unidade": "m²"},
    {"item": "10.1.6", "descricao": "Piso podotátil direcional em borracha integrado 30x30cm, assentamento com argamassa (fornecimento e assentamento)", "quantidade": 22.68, "unidade": "m²"},
    {"item": "10.1.7", "descricao": "Soleira em granito cinza andorinha, L=15cm, E=2cm", "quantidade": 90.00, "unidade": "m"},
    {"item": "10.1.8", "descricao": "Soleira em granito cinza andorinha, L=30cm, E=2cm", "quantidade": 1.77, "unidade": "m"},
    {"item": "10.2.1", "descricao": "Passeio em concreto desempenado com junta plástica a cada 1,20m, e=7cm", "quantidade": 15.98, "unidade": "m²"},
    {"item": "10.2.2", "descricao": "Rampa de acesso em concreto não estrutural", "quantidade": 28.22, "unidade": "m²"},
    {"item": "10.2.3", "descricao": "Pavimentação em blocos intertravado de concreto, e= 6,0cm, FCK 35MPa, assentados sobre colchão de areia", "quantidade": 67.22, "unidade": "m²"},
    {"item": "10.2.4", "descricao": "Piso tátil de alerta em placas pré-moldadas - 5MPa", "quantidade": 4.86, "unidade": "m²"},
    {"item": "10.2.5", "descricao": "Piso tátil direcional em placas pré-moldadas - 5MPa", "quantidade": 8.64, "unidade": "m²"},
    {"item": "11.1", "descricao": "Emassamento de paredes internas com massa acrílica - 02 demãos", "quantidade": 2028.45, "unidade": "m²"},
    {"item": "11.4", "descricao": "Pintura em esmalte sintético 02 demãos em esquadrias de madeira", "quantidade": 107.10, "unidade": "m²"},
    {"item": "11.5", "descricao": "Pintura em esmalte sintético 02 demãos em rodameio de madeira", "quantidade": 19.13, "unidade": "m²"},
    {"item": "15.1", "descricao": "Bacia Sanitária Vogue Plus, Linha Conforto com abertura, cor Branco Gelo, código P.51, DECA, ou equivalente p/ descarga, com acessórios, bolsa de borracha para ligação, tubo pvc ligação - fornecimento e instalação", "quantidade": 2.00, "unidade": "und"},
    {"item": "15.2", "descricao": "Bacia Sanitária Convencional, código Izy P.11, DECA, ou equivalente com acessórios- fornecimento e instalação", "quantidade": 4.00, "unidade": "und"},
    {"item": "15.3", "descricao": "Bacia Convencional Studio Kids, código PI.16, para válvula de descarga, em louça branca, assento plástico, anel de vedação, tubo pvc ligação - fornecimento e instalação, Deca ou equivalente", "quantidade": 18.00, "unidade": "und"},
    {"item": "15.4", "descricao": "Válvula de descarga 1 1/2\", com registro, acabamento em metal cromado - fornecimento e instalação", "quantidade": 26.00, "unidade": "und"},
    {"item": "15.9", "descricao": "Lavatório de canto suspenso com mesa, linha Izy código L101.17, DECA ou equivalente, com válvula, sifão e engate flexível cromados", "quantidade": 4.00, "unidade": "und"},
    {"item": "15.10", "descricao": "Lavatório pequeno Ravena/Izy cor branco gelo, com coluna suspensa, código L915 DECA ou equivalente", "quantidade": 6.00, "unidade": "und"},
    {"item": "15.12", "descricao": "Chuveiro Maxi Ducha, LORENZETTI, com Mangueira plástica/desviador", "quantidade": 15.00, "unidade": "und"},
    {"item": "15.13", "descricao": "Assento Poliéster com abertura frontal Vogue Plus, Linha Conforto, cor", "quantidade": 2.00, "unidade": "und"},
    {"item": "15.14", "descricao": "Assento plástico Izy, código AP.01, DECA", "quantidade": 4.00, "unidade": "und"},
    {"item": "15.15", "descricao": "Papeleira Metálica Linha Izy, código 2020.C37, DECA ou equivalente", "quantidade": 26.00, "unidade": "und"},
    {"item": "15.16", "descricao": "Ducha Higiênica com registro e derivação Izy, código 1984.C37. ACT.CR, DECA, ou equivalente", "quantidade": 4.00, "unidade": "und"},
    {"item": "15.19", "descricao": "Torneira Acabamento para registro pequeno Linha Izy, código: 4900.C37.PQ, DECA ou equivalente (para chuveiros), Deca ou equivalente", "quantidade": 15.00, "unidade": "und"},
    {"item": "15.22", "descricao": "Torneira para lavatório de mesa bica baixa Izy, código 1193.C37, Deca ou equivalente", "quantidade": 32.00, "unidade": "und"},
    {"item": "15.23", "descricao": "Dispenser Saboneteira Linha Excellence, código 7009, Melhoramentos ou equivalente", "quantidade": 15.00, "unidade": "und"},
    {"item": "15.26", "descricao": "Barra de apoio, Linha conforto, código 2310.I.080.ESC, aço inox polido, DECA ou equivalente", "quantidade": 8.00, "unidade": "cj"},
    {"item": "15.27", "descricao": "Barra de apoio de canto para lavatório, aço inox polido, Celite ou equivalente", "quantidade": 4.00, "unidade": "und"},
    {"item": "15.28", "descricao": "Barra de apoio de chuveiro PNE, em \"L\", Linha conforto código 2335.I.ESC", "quantidade": 1.00, "unidade": "und"},
    {"item": "15.29", "descricao": "Gancho metálico para mochilas, fornecimento e instalação", "quantidade": 188.00, "unidade": "und"},
    {"item": "16.1", "descricao": "Abrigo para Central de GLP, em concreto", "quantidade": 1.42, "unidade": "m³"},
    {"item": "16.3", "descricao": "Tubo de Aço Galvanizado Ø 3/4\", inclusive conexões", "quantidade": 43.00, "unidade": "m"},
    {"item": "16.4", "descricao": "Envelopamento de concreto - 3cm", "quantidade": 42.00, "unidade": "m"},
    {"item": "16.5", "descricao": "Fita anticorrosiva 5cmx30m (2 camadas)", "quantidade": 3.00, "unidade": "und"},
    {"item": "17.1", "descricao": "Extintor ABC - 6KG", "quantidade": 7.00, "unidade": "und"},
    {"item": "17.2", "descricao": "Extintor CO2 - 6KG", "quantidade": 1.00, "unidade": "und"},
    {"item": "17.3", "descricao": "Cotovelo 45º galvanizado 2 1/2\"", "quantidade": 2.00, "unidade": "und"},
    {"item": "17.4", "descricao": "Cotovelo 90º galvanizado 2 1/2\"", "quantidade": 7.00, "unidade": "und"},
    {"item": "17.5", "descricao": "Tubo aço carbono 2 1/2\"", "quantidade": 1.25, "unidade": "m"},
    {"item": "17.6", "descricao": "Niple duplo aço galvanizado 2 1/2\"", "quantidade": 10.00, "unidade": "und"},
    {"item": "17.7", "descricao": "Tê aço galvanizado 2 1/2\"", "quantidade": 4.00, "unidade": "und"},
    {"item": "17.8", "descricao": "Tubo aço galvanizado 65mm - 2 1/2\"", "quantidade": 65.27, "unidade": "m"},
    {"item": "17.9", "descricao": "Adaptador storz - roscas internas 2 1/2\"", "quantidade": 3.00, "unidade": "und"},
    {"item": "17.10", "descricao": "Caixa para abrigo de mangueira - 90x60x25 cm", "quantidade": 2.00, "unidade": "und"},
    {"item": "17.11", "descricao": "Chave para conexão de mangueira tipo storz engate rápido - dupla 1 1/2\" x 1 1/2\"", "quantidade": 3.00, "unidade": "und"},
    {"item": "17.12", "descricao": "Esguicho jato regulável de 1 1/2\", para combate a incêndio - Rev. 01", "quantidade": 3.00, "unidade": "und"},
    {"item": "17.13", "descricao": "Mangueiras de incêndio de nylon - 1 1/2\" 16mm", "quantidade": 6.00, "unidade": "m"},
    {"item": "17.14", "descricao": "Niple paralelo em ferro maleável 2 1/2\"", "quantidade": 3.00, "unidade": "und"},
    {"item": "17.15", "descricao": "Redução giratória tipo Storz - 2 1/2 x 1 1/2\"", "quantidade": 3.00, "unidade": "und"},
    {"item": "17.16", "descricao": "Registro globo 2 1/2\" 45º", "quantidade": 3.00, "unidade": "und"},
    {"item": "17.17", "descricao": "Tampão cego com corrente tipo storz 1 1/2\"", "quantidade": 3.00, "unidade": "und"},
    {"item": "17.18", "descricao": "Tampão de FoFo 50x50cm", "quantidade": 1.00, "unidade": "und"},
    {"item": "17.19", "descricao": "Registro bruto de gaveta industrial 2 1/2\"", "quantidade": 5.00, "unidade": "und"},
    {"item": "17.20", "descricao": "Válvula de retenção vertical 2 1/2\"", "quantidade": 2.00, "unidade": "und"},
    {"item": "17.21", "descricao": "União assento de ferro cônico macho-fêmea 2 1/2\"", "quantidade": 4.00, "unidade": "und"},
    {"item": "17.22", "descricao": "Luminária de emergência com lâmpada fluorescente 9W de 1 hora", "quantidade": 40.00, "unidade": "und"},
    {"item": "17.24", "descricao": "Conjunto motobomba", "quantidade": 2.00, "unidade": "und"},
    {"item": "17.25", "descricao": "Placa de sinalização em pvc cod 25 - (200x200) Hidrante de incêndio", "quantidade": 2.00, "unidade": "und"},
    {"item": "17.26", "descricao": "Placa de sinalização em pvc cod 12 e 13- (250x125) Saída de emergência", "quantidade": 14.00, "unidade": "und"},
    {"item": "17.27", "descricao": "Placa de sinalização em pvc cod 17 - (250x125) Mensagem \"Saída\"", "quantidade": 3.00, "unidade": "und"},
    {"item": "17.28", "descricao": "Placa de sinalização em pvc cod 23 - (200x200) Extintor de Incêndio", "quantidade": 8.00, "unidade": "und"},
    {"item": "18.1.1", "descricao": "Quadro de Distribuição de embutir, completo, (para 08 disjuntores monopolares, com barramento para as fases, neutro e para proteção, metálico, pintura eletrostática epóxi cor bege, c/ porta, trinco e acessórios)", "quantidade": 3.00, "unidade": "und"},
    {"item": "18.1.2", "descricao": "Quadro de Distribuição de embutir, completo, (para 18 disjuntores monopolares, com barramento para as fases, neutro e para proteção, metálico, pintura eletrostática epóxi cor bege, c/ porta, trinco e acessórios)", "quantidade": 1.00, "unidade": "und"},
    {"item": "18.1.3", "descricao": "Quadro de Distribuição de embutir, completo, (para 24 disjuntores monopolares, com barramento para as fases, neutro e para proteção, metálico, pintura eletrostática epóxi cor bege, c/ porta, trinco e acessórios)", "quantidade": 3.00, "unidade": "und"},
    {"item": "18.1.4", "descricao": "Quadro de Distribuição de embutir, completo, (para 50 disjuntores monopolares, com barramento para as fases, neutro e para proteção, metálico, pintura eletrostática epóxi cor bege, c/ porta, trinco e acessórios)", "quantidade": 2.00, "unidade": "und"},
    {"item": "18.2.1", "descricao": "Disjuntor unipolar termomagnético 10A", "quantidade": 22.00, "unidade": "und"},
    {"item": "18.2.2", "descricao": "Disjuntor unipolar termomagnético 16A", "quantidade": 7.00, "unidade": "und"},
    {"item": "18.2.3", "descricao": "Disjuntor unipolar termomagnético 20A", "quantidade": 19.00, "unidade": "und"},
    {"item": "18.2.4", "descricao": "Disjuntor unipolar termomagnético 25A", "quantidade": 26.00, "unidade": "und"},
    {"item": "18.2.5", "descricao": "Disjuntor unipolar termomagnético 32A", "quantidade": 10.00, "unidade": "und"},
    {"item": "18.2.6", "descricao": "Disjuntor unipolar termomagnético 40A", "quantidade": 1.00, "unidade": "und"},
    {"item": "18.2.7", "descricao": "Disjuntor tripolar termomagnético 10A", "quantidade": 1.00, "unidade": "und"},
    {"item": "18.2.8", "descricao": "Disjuntor tripolar termomagnético 25A", "quantidade": 4.00, "unidade": "und"},
    {"item": "18.2.9", "descricao": "Disjuntor tripolar termomagnético 32A", "quantidade": 2.00, "unidade": "und"},
    {"item": "18.2.10", "descricao": "Disjuntor tripolar termomagnético 80A", "quantidade": 8.00, "unidade": "und"},
    {"item": "18.2.11", "descricao": "Disjuntor tripolar termomagnético 175A", "quantidade": 1.00, "unidade": "und"},
    {"item": "18.2.12", "descricao": "Disjuntor tripolar termomagnético 225A", "quantidade": 1.00, "unidade": "und"},
    {"item": "18.2.13", "descricao": "Interruptor bipolar DR - 100A", "quantidade": 3.00, "unidade": "und"},
    {"item": "18.2.14", "descricao": "Interruptor bipolar DR - 25A", "quantidade": 3.00, "unidade": "und"},
    {"item": "18.2.15", "descricao": "Interruptor bipolar DR -63A", "quantidade": 1.00, "unidade": "und"},
    {"item": "18.2.16", "descricao": "Interruptor bipolar DR -80A", "quantidade": 1.00, "unidade": "und"},
    {"item": "18.2.17", "descricao": "Dispositivo de proteção contra surto - 175V - 40KA", "quantidade": 28.00, "unidade": "und"},
    {"item": "18.2.18", "descricao": "Dispositivo de proteção contra surto - 175V - 80KA", "quantidade": 8.00, "unidade": "und"},
    {"item": "18.4.1", "descricao": "Condutor de cobre unipolar, isolação em PVC/70ºC, camada de proteção em PVC, não propagador de chamas, classe de tensão 750V, encordoamento classe 5, flexível, seção nominal: #2,5 mm²", "quantidade": 7957.10, "unidade": "m"},
    {"item": "18.4.2", "descricao": "Condutor de cobre unipolar, isolação em PVC/70ºC, camada de proteção em PVC, não propagador de chamas, classe de tensão 750V, encordoamento classe 5, flexível, seção nominal: #4 mm²", "quantidade": 502.00, "unidade": "m"},
    {"item": "18.4.3", "descricao": "Condutor de cobre unipolar, isolação em PVC/70ºC, camada de proteção em PVC, não propagador de chamas, classe de tensão 750V, encordoamento classe 5, flexível, seção nominal: #6 mm²", "quantidade": 2335.30, "unidade": "m"},
    {"item": "18.4.4", "descricao": "Condutor de cobre unipolar, isolação em PVC/70ºC, camada de proteção em PVC, não propagador de chamas, classe de tensão 750V, encordoamento classe 5, flexível, seção nominal: #10 mm²", "quantidade": 602.80, "unidade": "m"},
    {"item": "18.5.6", "descricao": "Eletrocalha lisa tipo U 150x50mm com tampa, inclusive conexões", "quantidade": 5.60, "unidade": "m"},
    {"item": "22.7", "descricao": "Escavação de vala para aterramento", "quantidade": 39.00, "unidade": "m³"},
    {"item": "22.8", "descricao": "Haste tipo coopperweld 5/8\" x 2,40m", "quantidade": 13.00, "unidade": "und"},
    {"item": "22.9", "descricao": "Cabo de cobre nu 16 mm²", "quantidade": 5.00, "unidade": "m"},
    {"item": "22.11", "descricao": "Cabo de cobre nu 50 mm²", "quantidade": 260.00, "unidade": "m"},
    {"item": "23.1.1", "descricao": "Conjunto de mastros para bandeiras em tubo ferro galvanizado telescópico (alt= 7m (3mx2\" + 4mx1 1/2\"))", "quantidade": 1.00, "unidade": "und"},
    {"item": "23.1.5", "descricao": "Bancos de concreto", "quantidade": 7.22, "unidade": "m"},
    {"item": "23.1.7", "descricao": "Peitoril em granito cinza, largura=17,00cm espessura variável e pingadeira", "quantidade": 106.80, "unidade": "m"},
    {"item": "23.2.1", "descricao": "Alça de içamento", "quantidade": 2.00, "unidade": "und"},
    {"item": "23.2.2", "descricao": "Suporte de luz piloto", "quantidade": 1.00, "unidade": "und"},
    {"item": "23.2.3", "descricao": "Suporte para cinto de segurança", "quantidade": 1.00, "unidade": "und"},
    {"item": "23.2.4", "descricao": "Suporte para Pára-raio", "quantidade": 1.00, "unidade": "m"},
    {"item": "23.2.5", "descricao": "Escada interna e externa tipo marinheiro, inclusive pintura", "quantidade": 9.00, "unidade": "m"},
    {"item": "23.2.6", "descricao": "Guarda corpo de 1,0m de altura", "quantidade": 6.97, "unidade": "m"},
    {"item": "23.2.7", "descricao": "Chapa de aço carbono de alta resistência a corrosão e de qualidade estrutural e solda interna e externa, para confecção do reservatório conforme projeto", "quantidade": 1702.30, "unidade": "m²"},
    {"item": "23.2.8", "descricao": "Sistema de ancoragem com 6 nichos, conforme projeto", "quantidade": 1.00, "unidade": "un"},
    {"item": "23.2.9", "descricao": "Preparo de superfície: jateamento abrasivo ao metal branco (interno e externo), padrão AS 3", "quantidade": 145.76, "unidade": "m²"},
    {"item": "23.2.10", "descricao": "Acabamento interno: duas demãos de espessura seca de primer Epóxi", "quantidade": 69.08, "unidade": "m²"},
    {"item": "23.2.11", "descricao": "Acabamento externo: uma demão de espessura seca de primer Epóxi", "quantidade": 69.08, "unidade": "m²"},
    {"item": "23.2.12", "descricao": "Pintura Externa: uma demão de poliuretano na cor amarelo", "quantidade": 69.08, "unidade": "m²"},
]


def get_user_id(db, email: Optional[str] = None) -> int:
    """Busca o primeiro usuário ou por email."""
    if email:
        user = db.query(Usuario).filter(Usuario.email == email).first()
    else:
        user = db.query(Usuario).first()

    if not user:
        raise ValueError("Nenhum usuário encontrado no banco de dados!")

    return user.id


def main():
    print("=" * 60)
    print("Inserindo Atestado: Creche Pró-Infância - Esperança/PB")
    print("=" * 60)

    with get_db_session() as db:
        # Buscar user_id (primeiro usuário do banco)
        user_id = get_user_id(db)
        print(f"Usando user_id: {user_id}")

        # Criar atestado
        atestado = Atestado(
            user_id=user_id,
            descricao_servico=DESCRICAO_GERAL,
            contratante=CONTRATANTE,
            data_emissao=DATA_EMISSAO,
            arquivo_path="manual/ATESTADO_CRECHE_ESPERANCA.pdf",
            servicos_json=SERVICOS
        )

        db.add(atestado)
        db.commit()
        db.refresh(atestado)

        print("\n✓ Atestado inserido com sucesso!")
        print(f"  ID: {atestado.id}")
        print(f"  Contratante: {atestado.contratante}")
        print(f"  Data Emissão: {atestado.data_emissao}")
        print(f"  Total de serviços: {len(SERVICOS)}")
        print("\nPrimeiros 5 serviços:")
        for s in SERVICOS[:5]:
            print(f"  - {s['item']}: {s['descricao'][:50]}... ({s['quantidade']} {s['unidade']})")


if __name__ == "__main__":
    main()
