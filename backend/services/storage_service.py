"""
Serviço de Storage para arquivos.

Suporta armazenamento local (desenvolvimento) e Supabase Storage (produção).
A escolha é feita automaticamente com base nas variáveis de ambiente.
"""
import io
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Optional

from config import SUPABASE_SERVICE_KEY, SUPABASE_URL, UPLOAD_DIR
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

    def upload_stream(
        self,
        file: BinaryIO,
        path: str,
        content_type: str = "application/octet-stream",
        chunk_size: int = 1024 * 1024  # 1MB
    ) -> str:
        """
        Faz upload de arquivo usando streaming para reduzir uso de memoria.

        Args:
            file: Arquivo como objeto binario
            path: Caminho de destino
            content_type: Tipo MIME do arquivo
            chunk_size: Tamanho do chunk em bytes (default 1MB)

        Returns:
            URL ou caminho do arquivo salvo
        """
        # Implementacao padrao usa upload normal
        # Subclasses podem otimizar se o backend suportar
        return self.upload(file, path, content_type)


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

    def upload_stream(
        self,
        file: BinaryIO,
        path: str,
        content_type: str = "application/octet-stream",
        chunk_size: int = 1024 * 1024
    ) -> str:
        """Upload usando streaming - copia em chunks sem carregar tudo em memoria."""
        import shutil

        full_path = self._get_full_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, 'wb') as f:
            shutil.copyfileobj(file, f, length=chunk_size)

        logger.debug(f"[STORAGE] Arquivo salvo (streaming): {full_path}")
        return str(full_path)


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
        import json
        import urllib.request

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
        # Mantem compatibilidade com callers existentes; usa streaming internamente.
        if hasattr(file, "seek"):
            file.seek(0)
        return self.upload_stream(file, path, content_type)

    def download(self, path: str) -> Optional[bytes]:
        import urllib.error
        import urllib.request

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
        import urllib.error
        import urllib.request

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
        import urllib.error
        import urllib.request

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

    def _upload_stream_http(
        self,
        method: str,
        path: str,
        file: BinaryIO,
        content_type: str,
        chunk_size: int,
    ) -> None:
        """Envia arquivo para o Supabase usando transfer-encoding chunked."""
        import http.client
        import urllib.error
        from urllib.parse import quote, urlparse

        encoded_path = quote(path, safe="/-_.~")
        url = f"{self.storage_url}/object/{self.BUCKET_NAME}/{encoded_path}"
        parsed = urlparse(url)
        request_path = parsed.path + (f"?{parsed.query}" if parsed.query else "")

        conn_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        conn = conn_class(parsed.netloc, timeout=120)

        try:
            conn.putrequest(method, request_path)
            headers = self._get_headers()
            headers["Content-Type"] = content_type
            headers["Transfer-Encoding"] = "chunked"
            for key, value in headers.items():
                conn.putheader(key, value)
            conn.endheaders()

            while True:
                chunk = file.read(chunk_size)
                if not chunk:
                    break
                conn.send(f"{len(chunk):X}\r\n".encode("ascii"))
                conn.send(chunk)
                conn.send(b"\r\n")

            conn.send(b"0\r\n\r\n")
            response = conn.getresponse()
            body = response.read()

            if 200 <= response.status < 300:
                return

            raise urllib.error.HTTPError(
                url=url,
                code=response.status,
                msg=response.reason,
                hdrs=response.headers,
                fp=io.BytesIO(body),
            )
        finally:
            conn.close()

    def upload_stream(
        self,
        file: BinaryIO,
        path: str,
        content_type: str = "application/octet-stream",
        chunk_size: int = 1024 * 1024,
    ) -> str:
        """
        Upload usando streaming para evitar carregar arquivo inteiro em memória.

        Faz POST e, em caso de conflito (409), repete como PUT para upsert.
        """
        import urllib.error

        if hasattr(file, "seek"):
            file.seek(0)

        try:
            self._upload_stream_http("POST", path, file, content_type, chunk_size)
            logger.debug(f"[STORAGE] Upload concluído (stream): {path}")
            return self.get_url(path)
        except urllib.error.HTTPError as e:
            if e.code != 409:
                raise
            if hasattr(file, "seek"):
                file.seek(0)
            self._upload_stream_http("PUT", path, file, content_type, chunk_size)
            logger.debug(f"[STORAGE] Arquivo atualizado (stream): {path}")
            return self.get_url(path)


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
