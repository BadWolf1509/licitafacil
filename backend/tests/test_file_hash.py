"""
Testes para utilitarios de hash de arquivos.

Testa compute_file_hash, compute_content_hash e funcoes de chave de cache
definidas em utils/file_hash.py.
"""
import hashlib
import pytest

from utils.file_hash import (
    compute_file_hash,
    compute_content_hash,
    get_file_cache_key,
    get_ocr_cache_key,
    get_table_extraction_cache_key,
    get_text_extraction_cache_key,
)


# =============================================================================
# compute_file_hash
# =============================================================================


class TestComputeFileHash:
    """Testes para compute_file_hash."""

    def test_compute_file_hash_sha256_default(self, tmp_path):
        """Hash SHA-256 e usado como algoritmo padrao."""
        f = tmp_path / "sample.txt"
        content = b"conteudo de teste para hash"
        f.write_bytes(content)

        result = compute_file_hash(f)

        expected = hashlib.sha256(content).hexdigest()
        assert result == expected

    def test_compute_file_hash_md5(self, tmp_path):
        """Aceita algoritmo MD5 e retorna hash correto."""
        f = tmp_path / "sample.txt"
        content = b"conteudo md5"
        f.write_bytes(content)

        result = compute_file_hash(f, algorithm="md5")

        expected = hashlib.md5(content).hexdigest()
        assert result == expected

    def test_compute_file_hash_sha1(self, tmp_path):
        """Aceita algoritmo SHA-1 e retorna hash correto."""
        f = tmp_path / "sample.txt"
        content = b"conteudo sha1"
        f.write_bytes(content)

        result = compute_file_hash(f, algorithm="sha1")

        expected = hashlib.sha1(content).hexdigest()
        assert result == expected

    def test_compute_file_hash_file_not_found(self, tmp_path):
        """Levanta FileNotFoundError quando arquivo nao existe."""
        caminho_inexistente = tmp_path / "nao_existe.txt"

        with pytest.raises(FileNotFoundError, match="Arquivo nao encontrado"):
            compute_file_hash(caminho_inexistente)

    def test_compute_file_hash_deterministic(self, tmp_path):
        """Mesmo arquivo produz sempre o mesmo hash."""
        f = tmp_path / "deterministic.txt"
        f.write_bytes(b"conteudo fixo")

        hash1 = compute_file_hash(f)
        hash2 = compute_file_hash(f)

        assert hash1 == hash2

    def test_compute_file_hash_different_content(self, tmp_path):
        """Arquivos com conteudos diferentes produzem hashes diferentes."""
        f1 = tmp_path / "file_a.txt"
        f2 = tmp_path / "file_b.txt"
        f1.write_bytes(b"conteudo A")
        f2.write_bytes(b"conteudo B")

        hash1 = compute_file_hash(f1)
        hash2 = compute_file_hash(f2)

        assert hash1 != hash2


# =============================================================================
# compute_content_hash
# =============================================================================


class TestComputeContentHash:
    """Testes para compute_content_hash."""

    def test_compute_content_hash_sha256(self):
        """Calcula SHA-256 de conteudo em bytes."""
        content = b"dados para hash"
        result = compute_content_hash(content)

        expected = hashlib.sha256(content).hexdigest()
        assert result == expected

    def test_compute_content_hash_empty_bytes(self):
        """Calcula hash de bytes vazios (hash do vazio)."""
        result = compute_content_hash(b"")

        expected = hashlib.sha256(b"").hexdigest()
        assert result == expected
        # SHA-256 do vazio e conhecido
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_compute_content_hash_deterministic(self):
        """Mesmo conteudo produz sempre o mesmo hash."""
        content = b"conteudo repetido"
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)

        assert hash1 == hash2


# =============================================================================
# Cache key functions
# =============================================================================


class TestCacheKeyFunctions:
    """Testes para funcoes de geracao de chave de cache."""

    def test_get_file_cache_key_format(self, tmp_path):
        """Chave de cache segue formato 'file:<hash[:12]>'."""
        f = tmp_path / "cache_test.txt"
        f.write_bytes(b"cache content")

        key = get_file_cache_key(f)

        assert key.startswith("file:")
        # Formato: "file:" + 12 caracteres hexadecimais
        parts = key.split(":")
        assert len(parts) == 2
        assert len(parts[1]) == 12

    def test_get_file_cache_key_custom_prefix(self, tmp_path):
        """Chave de cache aceita prefixo customizado."""
        f = tmp_path / "cache_test.txt"
        f.write_bytes(b"cache content")

        key = get_file_cache_key(f, prefix="custom")

        assert key.startswith("custom:")
        parts = key.split(":")
        assert parts[0] == "custom"

    def test_get_ocr_cache_key_default_dpi(self, tmp_path):
        """Chave OCR usa DPI padrao 300."""
        f = tmp_path / "ocr_test.pdf"
        f.write_bytes(b"%PDF-1.4 fake pdf")

        key = get_ocr_cache_key(f)

        assert key.startswith("ocr:")
        assert key.endswith(":300")
        # Formato: "ocr:<hash[:12]>:300"
        parts = key.split(":")
        assert len(parts) == 3
        assert parts[0] == "ocr"
        assert parts[2] == "300"

    def test_get_ocr_cache_key_custom_dpi(self, tmp_path):
        """Chave OCR aceita DPI customizado."""
        f = tmp_path / "ocr_test.pdf"
        f.write_bytes(b"%PDF-1.4 fake pdf")

        key_150 = get_ocr_cache_key(f, dpi=150)
        key_600 = get_ocr_cache_key(f, dpi=600)

        assert key_150.endswith(":150")
        assert key_600.endswith(":600")
        # Mesmo arquivo, DPIs diferentes = chaves diferentes
        assert key_150 != key_600

    def test_get_table_extraction_cache_key(self, tmp_path):
        """Chave de extracao de tabela segue formato 'table:<hash[:12]>'."""
        f = tmp_path / "table_test.pdf"
        f.write_bytes(b"%PDF-1.4 table data")

        key = get_table_extraction_cache_key(f)

        assert key.startswith("table:")
        parts = key.split(":")
        assert len(parts) == 2
        assert len(parts[1]) == 12

    def test_get_text_extraction_cache_key(self, tmp_path):
        """Chave de extracao de texto segue formato 'text:<hash[:12]>'."""
        f = tmp_path / "text_test.pdf"
        f.write_bytes(b"%PDF-1.4 text data")

        key = get_text_extraction_cache_key(f)

        assert key.startswith("text:")
        parts = key.split(":")
        assert len(parts) == 2
        assert len(parts[1]) == 12

    def test_cache_keys_use_12_char_hash(self, tmp_path):
        """Todas as funcoes de cache usam hash truncado em 12 caracteres."""
        f = tmp_path / "hash_len.txt"
        f.write_bytes(b"content for hash length test")

        file_key = get_file_cache_key(f)
        ocr_key = get_ocr_cache_key(f)
        table_key = get_table_extraction_cache_key(f)
        text_key = get_text_extraction_cache_key(f)

        # Extrair parte do hash de cada chave
        file_hash_part = file_key.split(":")[1]
        ocr_hash_part = ocr_key.split(":")[1]
        table_hash_part = table_key.split(":")[1]
        text_hash_part = text_key.split(":")[1]

        assert len(file_hash_part) == 12
        assert len(ocr_hash_part) == 12
        assert len(table_hash_part) == 12
        assert len(text_hash_part) == 12

        # Todos usam o mesmo hash base (mesmo arquivo)
        assert file_hash_part == ocr_hash_part == table_hash_part == text_hash_part
