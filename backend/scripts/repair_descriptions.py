"""
Script para reparar descrições de atestados que perderam acentos.

Usa o texto_extraido (que preserva acentos) para reconstruir
as descrições corretamente.

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


def extract_description_from_text(texto: str) -> str:
    """
    Extrai a descrição do serviço do texto extraído do PDF.

    Busca padrões comuns em atestados de capacidade técnica.
    """
    if not texto:
        return ""

    # Padrões para encontrar descrição do serviço
    patterns = [
        # "Descrição do Serviço: ..." ou "Objeto: ..."
        r'(?:descri[çc][aã]o\s+(?:do\s+)?servi[çc]o|objeto)\s*[:]\s*([^\n]+)',
        # "Serviço(s) Executado(s): ..."
        r'servi[çc]os?\s+executados?\s*[:]\s*([^\n]+)',
        # Após "ATESTAMOS" ou "DECLARAMOS"
        r'(?:atestamos|declaramos)[^:]*:\s*([^\n]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, texto, re.IGNORECASE)
        if match:
            desc = match.group(1).strip()
            # Limitar tamanho e limpar
            desc = ' '.join(desc.split())[:500]
            if len(desc) > 20:  # Descrição válida
                return desc

    return ""


def has_missing_accents(text: str) -> bool:
    """
    Verifica se o texto parece ter perdido acentos.

    Detecta palavras comuns em português que deveriam ter acentos.
    """
    if not text:
        return False

    # Palavras que frequentemente aparecem sem acento incorretamente
    accent_patterns = [
        (r'\bexecucao\b', 'execução'),
        (r'\bconstrucao\b', 'construção'),
        (r'\bfundacao\b', 'fundação'),
        (r'\binstalacao\b', 'instalação'),
        (r'\bmanutencao\b', 'manutenção'),
        (r'\boperacao\b', 'operação'),
        (r'\breforma\b', 'reforma'),  # não tem acento, ok
        (r'\brecuperacao\b', 'recuperação'),
        (r'\bampliacao\b', 'ampliação'),
        (r'\bpavimentacao\b', 'pavimentação'),
        (r'\bdrenagem\b', 'drenagem'),  # não tem acento, ok
        (r'\bsao\b', 'são'),
        (r'\bestacao\b', 'estação'),
        (r'\bservico\b', 'serviço'),
        (r'\bpredio\b', 'prédio'),
        (r'\bagua\b', 'água'),
        (r'\besgoto\b', 'esgoto'),  # não tem acento, ok
        (r'\barea\b', 'área'),
    ]

    text_lower = text.lower()
    for pattern, _ in accent_patterns:
        if re.search(pattern, text_lower):
            return True

    return False


def find_accented_version(texto_extraido: str, desc_sem_acento: str) -> str:
    """
    Busca no texto extraído a versão com acentos da descrição.
    """
    if not texto_extraido or not desc_sem_acento:
        return desc_sem_acento

    # Normalizar para comparação (remover espaços extras)
    desc_clean = ' '.join(desc_sem_acento.split()).lower()

    # Dividir texto em linhas e parágrafos
    lines = texto_extraido.split('\n')

    for line in lines:
        line_clean = ' '.join(line.split()).lower()

        # Verificar se a linha contém a descrição (ignorando acentos)
        # Usar comparação fuzzy simples
        if len(line_clean) < 20:
            continue

        # Remover acentos da linha para comparar
        import unicodedata
        line_ascii = unicodedata.normalize('NFKD', line_clean)
        line_ascii = line_ascii.encode('ASCII', 'ignore').decode('ASCII')

        # Se a versão sem acento bate, usar a versão original (com acento)
        if desc_clean in line_ascii or line_ascii in desc_clean:
            # Extrair a parte relevante da linha original
            return ' '.join(line.split())[:500]

    return desc_sem_acento


def repair_atestado(atestado: Atestado, dry_run: bool = True) -> bool:
    """
    Repara a descrição de um atestado se necessário.

    Returns:
        True se houve alteração, False caso contrário
    """
    if not atestado.descricao_servico:
        return False

    # Verificar se precisa de reparo
    if not has_missing_accents(atestado.descricao_servico):
        return False

    # Tentar encontrar versão com acentos no texto extraído
    if atestado.texto_extraido:
        new_desc = find_accented_version(
            atestado.texto_extraido,
            atestado.descricao_servico
        )

        if new_desc != atestado.descricao_servico:
            logger.info(
                f"Atestado {atestado.id}: "
                f"'{atestado.descricao_servico[:50]}...' -> "
                f"'{new_desc[:50]}...'"
            )

            if not dry_run:
                atestado.descricao_servico = new_desc

            return True

    return False


def repair_servicos_json(atestado: Atestado, dry_run: bool = True) -> int:
    """
    Repara as descrições dentro de servicos_json.

    Returns:
        Número de serviços reparados
    """
    if not atestado.servicos_json or not atestado.texto_extraido:
        return 0

    count = 0
    for servico in atestado.servicos_json:
        desc = servico.get('descricao', '')
        if not desc or not has_missing_accents(desc):
            continue

        new_desc = find_accented_version(atestado.texto_extraido, desc)
        if new_desc != desc:
            logger.info(
                f"  Serviço {servico.get('item', '?')}: "
                f"'{desc[:40]}...' -> '{new_desc[:40]}...'"
            )

            if not dry_run:
                servico['descricao'] = new_desc

            count += 1

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
