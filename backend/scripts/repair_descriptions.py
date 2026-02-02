"""
Script para reparar descrições de atestados que perderam acentos.

Usa mapeamento de palavras comuns para restaurar acentos.

Uso:
    python scripts/repair_descriptions.py --dry-run  # Ver mudanças sem aplicar
    python scripts/repair_descriptions.py            # Aplicar correções
"""

import sys
import re
import argparse
from pathlib import Path

# Adicionar diretório pai ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_db_session
from models import Atestado
from logging_config import get_logger

logger = get_logger('scripts.repair_descriptions')


# Mapeamento de palavras sem acento -> com acento
# Inclui variações de case e plural
ACCENT_MAP = {
    # Palavras comuns em descrições de obras
    'execucao': 'execução',
    'construcao': 'construção',
    'reconstrucao': 'reconstrução',
    'fundacao': 'fundação',
    'instalacao': 'instalação',
    'instalacoes': 'instalações',
    'manutencao': 'manutenção',
    'operacao': 'operação',
    'recuperacao': 'recuperação',
    'ampliacao': 'ampliação',
    'pavimentacao': 'pavimentação',
    'implantacao': 'implantação',
    'urbanizacao': 'urbanização',
    'regularizacao': 'regularização',
    'canalizacao': 'canalização',
    'drenagem': 'drenagem',
    'sinalizacao': 'sinalização',
    'iluminacao': 'iluminação',
    'irrigacao': 'irrigação',
    'perfuracao': 'perfuração',
    'escavacao': 'escavação',
    'compactacao': 'compactação',
    'demolicao': 'demolição',
    'terraplanagem': 'terraplanagem',
    'concretagem': 'concretagem',
    'alvenaria': 'alvenaria',
    'pintura': 'pintura',
    'impermeabilizacao': 'impermeabilização',
    'restauracao': 'restauração',
    'conservacao': 'conservação',
    'reabilitacao': 'reabilitação',
    'adequacao': 'adequação',
    'adaptacao': 'adaptação',
    'revitalizacao': 'revitalização',
    'reurbanizacao': 'reurbanização',
    'duplicacao': 'duplicação',
    'reestruturacao': 'reestruturação',

    # Localizações e geografia
    'sao': 'são',
    'joao': 'joão',
    'paraiba': 'paraíba',
    'piaui': 'piauí',
    'ceara': 'ceará',
    'maranhao': 'maranhão',
    'goias': 'goiás',
    'amapa': 'amapá',
    # 'para': 'pará',  # NÃO incluir - conflita com preposição "para"
    'rondonia': 'rondônia',
    'espirito': 'espírito',
    'bahia': 'bahia',
    'municipio': 'município',
    'municipios': 'municípios',
    'regiao': 'região',
    'area': 'área',
    'areas': 'áreas',
    'estacao': 'estação',
    'estacoes': 'estações',

    # Termos técnicos
    'servico': 'serviço',
    'servicos': 'serviços',
    'predio': 'prédio',
    'predios': 'prédios',
    'edificio': 'edifício',
    'edificios': 'edifícios',
    'agua': 'água',
    'aguas': 'águas',
    'esgoto': 'esgoto',
    'sanitario': 'sanitário',
    'sanitaria': 'sanitária',
    'hidraulica': 'hidráulica',
    'hidraulico': 'hidráulico',
    'eletrica': 'elétrica',
    'eletrico': 'elétrico',
    'mecanica': 'mecânica',
    'mecanico': 'mecânico',
    'tecnica': 'técnica',
    'tecnico': 'técnico',
    'tecnicos': 'técnicos',
    'topograficos': 'topográficos',
    'topografico': 'topográfico',
    'pluviometrica': 'pluviométrica',
    'quilometro': 'quilômetro',
    'quilometros': 'quilômetros',
    'diametro': 'diâmetro',
    'perimetro': 'perímetro',
    'concreto': 'concreto',
    'asfaltico': 'asfáltico',
    'asfaltica': 'asfáltica',
    'graniticas': 'graníticas',
    'granitico': 'granítico',
    'ceramica': 'cerâmica',
    'ceramico': 'cerâmico',
    'metalica': 'metálica',
    'metalico': 'metálico',
    'estrutura': 'estrutura',
    'estrutural': 'estrutural',
    'locacao': 'locação',
    'fornecimento': 'fornecimento',
    'aquisicao': 'aquisição',
    'contratacao': 'contratação',
    'licitacao': 'licitação',
    'medicao': 'medição',
    'vistoria': 'vistoria',
    'fiscalizacao': 'fiscalização',
    'supervisao': 'supervisão',
    'gerenciamento': 'gerenciamento',
    'administracao': 'administração',
    'mobilizacao': 'mobilização',
    'desmobilizacao': 'desmobilização',

    # Materiais e componentes
    'tubo': 'tubo',
    'tubulacao': 'tubulação',
    'conexao': 'conexão',
    'conexoes': 'conexões',
    'juncao': 'junção',
    'reducao': 'redução',
    'valvula': 'válvula',
    'registro': 'registro',
    'caixa': 'caixa',
    'poco': 'poço',
    'pocos': 'poços',
    'reservatorio': 'reservatório',
    'elevatoria': 'elevatória',
    'elevatorio': 'elevatório',
    'uniao': 'união',
    'acoplamento': 'acoplamento',
    'fixacao': 'fixação',
    'ancoragem': 'ancoragem',
    'suporte': 'suporte',
    'apoio': 'apoio',
    'protecao': 'proteção',
    'vedacao': 'vedação',
    'isolamento': 'isolamento',
    'revestimento': 'revestimento',
    'acabamento': 'acabamento',
    'limpeza': 'limpeza',
    'remocao': 'remoção',
    'colocacao': 'colocação',
    'assentamento': 'assentamento',
    'aplicacao': 'aplicação',
    'preparacao': 'preparação',
    'nivelamento': 'nivelamento',

    # Tipos de vias e infraestrutura
    'via': 'via',
    'vias': 'vias',
    'rodovia': 'rodovia',
    'avenida': 'avenida',
    'calcada': 'calçada',
    'calcadas': 'calçadas',
    'meio-fio': 'meio-fio',
    'sarjeta': 'sarjeta',
    'bueiro': 'bueiro',
    'galeria': 'galeria',
    'ponte': 'ponte',
    'viaduto': 'viaduto',
    'passarela': 'passarela',
    'travessia': 'travessia',
    'acesso': 'acesso',
    'entrada': 'entrada',
    'saida': 'saída',
    'retorno': 'retorno',
    'rotatoria': 'rotatória',
    'intersecao': 'interseção',
    'cruzamento': 'cruzamento',

    # Adjetivos e outros
    'publico': 'público',
    'publica': 'pública',
    'publicos': 'públicos',
    'publicas': 'públicas',
    'domestico': 'doméstico',
    'domestica': 'doméstica',
    'residencial': 'residencial',
    'comercial': 'comercial',
    'industrial': 'industrial',
    'hospitalar': 'hospitalar',
    'escolar': 'escolar',
    'esportivo': 'esportivo',
    'esportiva': 'esportiva',
    'provisorio': 'provisório',
    'provisoria': 'provisória',
    'definitivo': 'definitivo',
    'definitiva': 'definitiva',
    'emergencial': 'emergencial',
    'corretiva': 'corretiva',
    'corretivo': 'corretivo',
    'preventiva': 'preventiva',
    'preventivo': 'preventivo',
    'periodica': 'periódica',
    'periodico': 'periódico',
    'continuo': 'contínuo',
    'continua': 'contínua',

    # Palavras adicionais encontradas (segunda rodada)
    'adocao': 'adoção',
    'amarracao': 'amarração',
    'armacao': 'armação',
    'caiacao': 'caiação',
    'composicao': 'composição',
    'demarcacao': 'demarcação',
    'dilatacao': 'dilatação',
    'edificacao': 'edificação',
    'edificacoes': 'edificações',
    'escovacao': 'escovação',
    'fabricacao': 'fabricação',
    'fundacoes': 'fundações',
    'inauguracao': 'inauguração',
    'interferencia': 'interferência',
    'ligacao': 'ligação',
    'ligacoes': 'ligações',
    'potencia': 'potência',
    'recomposicao': 'recomposição',
    'reconstituicao': 'reconstituição',
    'reposicao': 'reposição',
    'resistencia': 'resistência',
    'secao': 'seção',
    'secoes': 'seções',
    'sustentacao': 'sustentação',
    'utilizacao': 'utilização',
    'utilizacoes': 'utilizações',
    'vegetacao': 'vegetação',
    'zarcao': 'zarcão',

    # Terminações comuns -ência/-ância
    'frequencia': 'frequência',
    'ocorrencia': 'ocorrência',
    'referencia': 'referência',
    'existencia': 'existência',
    'permanencia': 'permanência',
    'vigilancia': 'vigilância',
    'tolerancia': 'tolerância',
    'distancia': 'distância',

    # Terminações -ório/-ória
    'divisoria': 'divisória',
    'divisorias': 'divisórias',
    'escritorio': 'escritório',
    'escritorios': 'escritórios',
    'lavatorio': 'lavatório',
    'lavatorios': 'lavatórios',
    'repositorio': 'repositório',
    'laboratorio': 'laboratório',
    'dormitorio': 'dormitório',
    'refeitorio': 'refeitório',
    'consultorio': 'consultório',
    'auditorio': 'auditório',
    'deposito': 'depósito',
    'transito': 'trânsito',

    # Palavras adicionais (terceira rodada)
    'conclusao': 'conclusão',
    'ginasio': 'ginásio',
    'ginasios': 'ginásios',
    'sitio': 'sítio',
    'sitios': 'sítios',
    'estadio': 'estádio',
    'estadios': 'estádios',
    'residuo': 'resíduo',
    'residuos': 'resíduos',
    'solido': 'sólido',
    'solidos': 'sólidos',
    'liquido': 'líquido',
    'liquidos': 'líquidos',
    'organico': 'orgânico',
    'organicos': 'orgânicos',
    'inorganico': 'inorgânico',
    'quimico': 'químico',
    'quimicos': 'químicos',
    'biologico': 'biológico',
    'biologicos': 'biológicos',

    # Palavras técnicas adicionais (quarta rodada)
    'acetico': 'acético',
    'acrilica': 'acrílica',
    'acrilico': 'acrílico',
    'acustico': 'acústico',
    'acustica': 'acústica',
    'alquidica': 'alquídica',
    'alquidico': 'alquídico',
    'arquitetonico': 'arquitetônico',
    'arquitetonica': 'arquitetônica',
    'ciclopico': 'ciclópico',
    'ciclopica': 'ciclópica',
    'elastica': 'elástica',
    'elastico': 'elástico',
    'eletromecanica': 'eletromecânica',
    'eletromecanico': 'eletromecânico',
    'eltrico': 'elétrico',  # erro comum de OCR
    'eltrica': 'elétrica',  # erro comum de OCR
    'higienica': 'higiênica',
    'higienico': 'higiênico',
    'hidienico': 'higiênico',  # erro de OCR
    'macico': 'maciço',
    'macica': 'maciça',
    'parametrica': 'paramétrica',
    'parametrico': 'paramétrico',
    'plastica': 'plástica',
    'plastico': 'plástico',
    'pneumatico': 'pneumático',
    'pneumatica': 'pneumática',
    'polimerica': 'polimérica',
    'polimerico': 'polimérico',
    'sintetico': 'sintético',
    'sintetica': 'sintética',
    'termomagnetico': 'termomagnético',
    'termomagnetica': 'termomagnética',
    'trifasica': 'trifásica',
    'trifasico': 'trifásico',
    'monofasico': 'monofásico',
    'monofasica': 'monofásica',
    'bifasico': 'bifásico',
    'bifasica': 'bifásica',
    'unica': 'única',
    'unico': 'único',

    # Correções de cedilha faltando (OCR confunde ç com c)
    # Padrão: palavra com 'cão' ao invés de 'ção'
    'recuperacao': 'recuperação',
    'execucao': 'execução',
    'construcao': 'construção',
    'instalacao': 'instalação',
    'manutencao': 'manutenção',
    'operacao': 'operação',
    'ampliacao': 'ampliação',
    'pavimentacao': 'pavimentação',
    'implantacao': 'implantação',
    'urbanizacao': 'urbanização',
    'canalizacao': 'canalização',
    'sinalizacao': 'sinalização',
    'iluminacao': 'iluminação',
    'fiscalizacao': 'fiscalização',
    'administracao': 'administração',
    'locacao': 'locação',
    'medicao': 'medição',
    'protecao': 'proteção',
    'remocao': 'remoção',
    'colocacao': 'colocação',
    'aplicacao': 'aplicação',
    'preparacao': 'preparação',
    'fixacao': 'fixação',
    'vedacao': 'vedação',
    'reducao': 'redução',
    'conexao': 'conexão',
    'juncao': 'junção',
    'tubulacao': 'tubulação',
    'fundacao': 'fundação',
    'demolicao': 'demolição',
    'escavacao': 'escavação',
    'compactacao': 'compactação',
    'perfuracao': 'perfuração',
    'irrigacao': 'irrigação',
    'regularizacao': 'regularização',
    'impermeabilizacao': 'impermeabilização',
    'restauracao': 'restauração',
    'conservacao': 'conservação',
    'reabilitacao': 'reabilitação',
    'adequacao': 'adequação',
    'adaptacao': 'adaptação',
    'revitalizacao': 'revitalização',
    'duplicacao': 'duplicação',
    'reestruturacao': 'reestruturação',
    'mobilizacao': 'mobilização',
    'desmobilizacao': 'desmobilização',
    'supervisao': 'supervisão',
    'aquisicao': 'aquisição',
    'contratacao': 'contratação',
    'licitacao': 'licitação',
    'reconstrucao': 'reconstrução',

    # Padrão: palavra com 'cão' (acento mas sem cedilha) ao invés de 'ção'
    # OCR às vezes captura o acento mas perde a cedilha
    'recuperacão': 'recuperação',
    'execucão': 'execução',
    'construcão': 'construção',
    'instalacão': 'instalação',
    'manutencão': 'manutenção',
    'operacão': 'operação',
    'ampliacão': 'ampliação',
    'pavimentacão': 'pavimentação',
    'implantacão': 'implantação',
    'urbanizacão': 'urbanização',
    'canalizacão': 'canalização',
    'sinalizacão': 'sinalização',
    'iluminacão': 'iluminação',
    'fiscalizacão': 'fiscalização',
    'administracão': 'administração',
    'locacão': 'locação',
    'medicão': 'medição',
    'protecão': 'proteção',
    'remocão': 'remoção',
    'colocacão': 'colocação',
    'aplicacão': 'aplicação',
    'preparacão': 'preparação',
    'fixacão': 'fixação',
    'vedacão': 'vedação',
    'reducão': 'redução',
    'conexão': 'conexão',
    'juncão': 'junção',
    'tubulacão': 'tubulação',
    'fundacão': 'fundação',
    'demolicão': 'demolição',
    'escavacão': 'escavação',
    'compactacão': 'compactação',
    'perfuracão': 'perfuração',
    'irrigacão': 'irrigação',
    'regularizacão': 'regularização',
    'impermeabilizacão': 'impermeabilização',
    'restauracão': 'restauração',
    'conservacão': 'conservação',
    'reabilitacão': 'reabilitação',
    'adequacão': 'adequação',
    'adaptacão': 'adaptação',
    'revitalizacão': 'revitalização',
    'duplicacão': 'duplicação',
    'reestruturacão': 'reestruturação',
    'mobilizacão': 'mobilização',
    'desmobilizacão': 'desmobilização',
    'supervisão': 'supervisão',
    'aquisicão': 'aquisição',
    'contratacão': 'contratação',
    'licitacão': 'licitação',
    'reconstrucão': 'reconstrução',
    'conclusão': 'conclusão',
    'composicão': 'composição',
    'recomposicão': 'recomposição',
    'reposicão': 'reposição',
    'secão': 'seção',
    'ligacão': 'ligação',
    'amarracão': 'amarração',
    'armacão': 'armação',
    'caiacão': 'caiação',
    'demarcacão': 'demarcação',
    'dilatacão': 'dilatação',
    'edificacão': 'edificação',
    'escovacão': 'escovação',
    'fabricacão': 'fabricação',
    'inauguracão': 'inauguração',
    'sustentacão': 'sustentação',
    'utilizacão': 'utilização',
    'vegetacão': 'vegetação',
}


def restore_accents(text: str) -> str:
    """
    Restaura acentos em um texto usando o mapeamento de palavras.

    Preserva o case original (maiúsculas/minúsculas).
    """
    if not text:
        return text

    result = text

    for unaccented, accented in ACCENT_MAP.items():
        # Padrão para encontrar a palavra (case insensitive, word boundary)
        pattern = r'\b' + re.escape(unaccented) + r'\b'

        def replace_preserving_case(match):
            original = match.group(0)
            if original.isupper():
                return accented.upper()
            elif original[0].isupper():
                return accented.capitalize()
            else:
                return accented

        result = re.sub(pattern, replace_preserving_case, result, flags=re.IGNORECASE)

    return result


def has_missing_accents(text: str) -> bool:
    """
    Verifica se o texto parece ter perdido acentos.
    """
    if not text:
        return False

    text_lower = text.lower()

    # Verificar se alguma palavra do mapeamento está presente sem acento
    for unaccented in ACCENT_MAP.keys():
        pattern = r'\b' + re.escape(unaccented) + r'\b'
        if re.search(pattern, text_lower):
            return True

    return False


def repair_atestado(atestado: Atestado, dry_run: bool = True) -> bool:
    """
    Repara a descrição de um atestado se necessário.
    """
    if not atestado.descricao_servico:
        return False

    if not has_missing_accents(atestado.descricao_servico):
        return False

    new_desc = restore_accents(atestado.descricao_servico)

    if new_desc != atestado.descricao_servico:
        logger.info(
            f"Atestado {atestado.id}: "
            f"'{atestado.descricao_servico[:60]}...' -> "
            f"'{new_desc[:60]}...'"
        )

        if not dry_run:
            atestado.descricao_servico = new_desc

        return True

    return False


def repair_servicos_json(atestado: Atestado, dry_run: bool = True) -> int:
    """
    Repara as descrições dentro de servicos_json.
    """
    if not atestado.servicos_json:
        return 0

    count = 0
    modified = False

    for servico in atestado.servicos_json:
        desc = servico.get('descricao', '')
        if not desc or not has_missing_accents(desc):
            continue

        new_desc = restore_accents(desc)
        if new_desc != desc:
            logger.info(
                f"  Serviço {servico.get('item', '?')}: "
                f"'{desc[:50]}...' -> '{new_desc[:50]}...'"
            )

            if not dry_run:
                servico['descricao'] = new_desc
                modified = True

            count += 1

    # Marcar como modificado para o SQLAlchemy detectar
    if modified and not dry_run:
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(atestado, 'servicos_json')

    return count


def main():
    parser = argparse.ArgumentParser(
        description='Repara descrições de atestados que perderam acentos'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Mostrar mudanças sem aplicar'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=0,
        help='Limitar número de atestados processados (0 = todos)'
    )
    args = parser.parse_args()

    logger.info(f"Iniciando reparo de descrições (dry_run={args.dry_run})")

    with get_db_session() as db:
        query = db.query(Atestado)
        if args.limit > 0:
            query = query.limit(args.limit)

        atestados = query.all()
        logger.info(f"Processando {len(atestados)} atestados...")

        total_desc_fixed = 0
        total_servicos_fixed = 0

        for atestado in atestados:
            # Reparar descrição principal
            if repair_atestado(atestado, args.dry_run):
                total_desc_fixed += 1

            # Reparar serviços
            servicos_fixed = repair_servicos_json(atestado, args.dry_run)
            total_servicos_fixed += servicos_fixed

        if not args.dry_run and (total_desc_fixed > 0 or total_servicos_fixed > 0):
            db.commit()
            logger.info("Alterações salvas no banco de dados")

        logger.info(
            f"Resumo: {total_desc_fixed} descrições principais e "
            f"{total_servicos_fixed} serviços reparados"
        )

        if args.dry_run:
            logger.info("(dry-run: nenhuma alteração foi salva)")


if __name__ == '__main__':
    main()
