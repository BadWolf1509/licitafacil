"""
Re-export de repositories.job_repository para compatibilidade.

O modulo canonico agora esta em repositories/job_repository.py.
"""
from repositories.job_repository import JobRepository, _now_iso  # noqa: F401
