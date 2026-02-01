"""
Corretor de descrições para garantir 100% de fidelidade ao PDF original.

NOTA: Este módulo foi refatorado e dividido em submódulos.
Este arquivo mantém compatibilidade com imports existentes.

Para novos imports, use:
    from services.description_fixer import fix_descriptions
"""

# Re-exportar função principal do novo módulo
from services.description_fixer.core import fix_descriptions

# Re-exportar constantes para compatibilidade

# Re-exportar funções auxiliares para compatibilidade (uso interno)




__all__ = ['fix_descriptions']
