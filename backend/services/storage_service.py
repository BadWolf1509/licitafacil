"""
Serviço de Storage para arquivos.

Suporta armazenamento local (desenvolvimento) e Supabase Storage (produção).
A escolha é feita automaticamente com base nas variáveis de ambiente.
"""
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Optional
from urllib.parse import urljoin

from config import UPLOAD_DIR, SUPABASE_URL, SUPABASE_SERVICE_KEY
from logging_config import get_logger

logger = get_logger('services.storage')


class StorageBackend(ABC):
    """Interface abstrata para backends de storage."""

    @abstractmethod
    def upload(self, file: BinaryIO, path: str, content_type: str = "application/octet-stream") -> str:
        """
        Faz upload de arquivo.

        Args:
            file: Arquivo como objeto binário
            path: Caminho de destino (ex: "users/1/atestados/file.pdf")
            content_type: Tipo MIME do arquivo

        Returns:
            URL pública ou caminho do arquivo salvo
        """
        pass

    @abstractmethod
    def download(self, path: str) -> Optional[bytes]:
        """
        Baixa arquivo do storage.

        Args:
            path: Caminho do arquivo

        Returns:
            Conteúdo do arquivo em bytes ou None se não existir
        """
        pass

    @abstractmethod
    def delete(self, path: str) -> bool:
        """
        Remove arquivo do storage.

        Args:
            path: Caminho do arquivo

        Returns:
            True se removido com sucesso
        """
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Verifica se arquivo existe."""
        pass

    @abstractmethod
    def get_url(self, path: str) -> str:
        """Retorna URL pública do arquivo."""
        pass


class LocalStorageBackend(StorageBackend):
    """Backend de storage local (filesystem)."""

    def __init__(self, base_dir: str = UPLOAD_DIR):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[STORAGE] Usando storage local: {self.base_dir}")

    def _get_full_path(self, path: str) -> Path:
        return self.base_dir / path

    def upload(self, file: BinaryIO, path: str, content_type: str = "application/octet-stream") -> str:
        full_path = self._get_full_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, 'wb') as f:
            f.write(file.read())

        logger.debug(f"[STORAGE] Arquivo salvo: {full_path}")
        return str(full_path)

    def download(self, path: str) -> Optional[bytes]:
        full_path = self._get_full_path(path)
        if not full_path.exists():
            return None

        with open(full_path, 'rb') as f:
            return f.read()

    def delete(self, path: str) -> bool:
        full_path = self._get_full_path(path)
        try:
            if full_path.exists():
                full_path.unlink()
                logger.debug(f"[STORAGE] Arquivo removido: {full_path}")
            return True
        except OSError as e:
            logger.warning(f"[STORAGE] Erro ao remover {full_path}: {e}")
            return False

    def exists(self, path: str) -> bool:
        return self._get_full_path(path).exists()

    def get_url(self, path: str) -> str:
        # Para storage local, retorna caminho relativo
        return str(self._get_full_path(path))


class SupabaseStorageBackend(StorageBackend):
    """Backend de storage usando Supabase Storage."""

    BUCKET_NAME = "uploads"

    def __init__(self, supabase_url: str, service_key: str):
        self.supabase_url = supabase_url.rstrip('/')
        self.service_key = service_key
        self.storage_url = f"{self.supabase_url}/storage/v1"

        # Criar bucket se não existir
        self._ensure_bucket()
        logger.info(f"[STORAGE] Usando Supabase Storage: {self.supabase_url}")

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.service_key}",
            "apikey": self.service_key,
        }

    def _ensure_bucket(self) -> None:
        """Cria bucket se não existir."""
        import urllib.request
        import json

        url = f"{self.storage_url}/bucket"
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"

        data = json.dumps({
            "id": self.BUCKET_NAME,
            "name": self.BUCKET_NAME,
            "public": False,
            "file_size_limit": 52428800  # 50MB
        }).encode('utf-8')

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            urllib.request.urlopen(req)
            logger.info(f"[STORAGE] Bucket '{self.BUCKET_NAME}' criado")
        except urllib.error.HTTPError as e:
            if e.code == 409:  # Bucket já existe
                logger.debug(f"[STORAGE] Bucket '{self.BUCKET_NAME}' já existe")
            else:
                logger.warning(f"[STORAGE] Erro ao criar bucket: {e}")

    def upload(self, file: BinaryIO, path: str, content_type: str = "application/octet-stream") -> str:
        import urllib.request

        url = f"{self.storage_url}/object/{self.BUCKET_NAME}/{path}"
        headers = self._get_headers()
        headers["Content-Type"] = content_type

        file_content = file.read()

        try:
            req = urllib.request.Request(url, data=file_content, headers=headers, method='POST')
            urllib.request.urlopen(req)
            logger.debug(f"[STORAGE] Upload concluído: {path}")
            return self.get_url(path)
        except urllib.error.HTTPError as e:
            # Se arquivo já existe, tenta atualizar
            if e.code == 409:
                req = urllib.request.Request(url, data=file_content, headers=headers, method='PUT')
                urllib.request.urlopen(req)
                logger.debug(f"[STORAGE] Arquivo atualizado: {path}")
                return self.get_url(path)
            raise

    def download(self, path: str) -> Optional[bytes]:
        import urllib.request
        import urllib.error

        url = f"{self.storage_url}/object/{self.BUCKET_NAME}/{path}"
        headers = self._get_headers()

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def delete(self, path: str) -> bool:
        import urllib.request
        import urllib.error

        url = f"{self.storage_url}/object/{self.BUCKET_NAME}/{path}"
        headers = self._get_headers()

        try:
            req = urllib.request.Request(url, headers=headers, method='DELETE')
            urllib.request.urlopen(req)
            logger.debug(f"[STORAGE] Arquivo removido: {path}")
            return True
        except urllib.error.HTTPError as e:
            logger.warning(f"[STORAGE] Erro ao remover {path}: {e}")
            return False

    def exists(self, path: str) -> bool:
        import urllib.request
        import urllib.error

        url = f"{self.storage_url}/object/{self.BUCKET_NAME}/{path}"
        headers = self._get_headers()

        try:
            req = urllib.request.Request(url, headers=headers, method='HEAD')
            urllib.request.urlopen(req)
            return True
        except urllib.error.HTTPError:
            return False

    def get_url(self, path: str) -> str:
        """Retorna URL autenticada do arquivo."""
        return f"{self.storage_url}/object/authenticated/{self.BUCKET_NAME}/{path}"

    def get_public_url(self, path: str) -> str:
        """Retorna URL pública (se bucket for público)."""
        return f"{self.storage_url}/object/public/{self.BUCKET_NAME}/{path}"


# =============================================================================
# Factory e Singleton
# =============================================================================

_storage_instance: Optional[StorageBackend] = None


def get_storage() -> StorageBackend:
    """
    Retorna instância do storage backend apropriado.

    Usa Supabase Storage se configurado, caso contrário usa storage local.
    """
    global _storage_instance

    if _storage_instance is None:
        if SUPABASE_URL and SUPABASE_SERVICE_KEY:
            _storage_instance = SupabaseStorageBackend(
                supabase_url=SUPABASE_URL,
                service_key=SUPABASE_SERVICE_KEY
            )
        else:
            _storage_instance = LocalStorageBackend(UPLOAD_DIR)

    return _storage_instance


def reset_storage() -> None:
    """Reseta instância do storage (útil para testes)."""
    global _storage_instance
    _storage_instance = None
