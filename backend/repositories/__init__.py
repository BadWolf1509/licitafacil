"""
Repositórios para acesso a dados.
Implementa o padrão Repository para separar lógica de acesso ao banco.
"""
from .analise_repository import AnaliseRepository, analise_repository
from .atestado_repository import AtestadoRepository, atestado_repository
from .base import BaseRepository
from .job_repository import JobRepository
from .usuario_repository import UsuarioRepository, usuario_repository

__all__ = [
    'BaseRepository',
    'atestado_repository',
    'AtestadoRepository',
    'analise_repository',
    'AnaliseRepository',
    'usuario_repository',
    'UsuarioRepository',
    'JobRepository',
]
