"""
Repositórios para acesso a dados.
Implementa o padrão Repository para separar lógica de acesso ao banco.
"""
from .base import BaseRepository
from .atestado_repository import atestado_repository, AtestadoRepository
from .analise_repository import analise_repository, AnaliseRepository
from .usuario_repository import usuario_repository, UsuarioRepository

__all__ = [
    'BaseRepository',
    'atestado_repository',
    'AtestadoRepository',
    'analise_repository',
    'AnaliseRepository',
    'usuario_repository',
    'UsuarioRepository',
]
