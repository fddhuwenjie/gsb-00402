"""Tests for language analyzers — validates extract_tokens(file_path) and scan_directory."""

import pytest
from app.analyzers.base_analyzer import BaseAnalyzer
from app.analyzers.c_analyzer import CAnalyzer
from app.analyzers.python_analyzer import PythonAnalyzer
from app.analyzers.java_analyzer import JavaAnalyzer
from app.analyzers.csharp_analyzer import CSharpAnalyzer
from app.analyzers.rust_analyzer import RustAnalyzer
from app.analyzers.perl_analyzer import PerlAnalyzer
from app.analyzers import get_analyzer, ANALYZER_MAP


class TestAnalyzerRegistry:
    def test_get_analyzer_c(self):
        assert isinstance(get_analyzer("c"), CAnalyzer)

    def test_get_analyzer_cpp(self):
        assert isinstance(get_analyzer("c++"), CAnalyzer)
        assert isinstance(get_analyzer("cpp"), CAnalyzer)

    def test_get_analyzer_python(self):
        assert isinstance(get_analyzer("python"), PythonAnalyzer)

    def test_get_analyzer_java(self):
        assert isinstance(get_analyzer("java"), JavaAnalyzer)

    def test_get_analyzer_csharp(self):
        assert isinstance(get_analyzer("c#"), CSharpAnalyzer)
        assert isinstance(get_analyzer("csharp"), CSharpAnalyzer)

    def test_get_analyzer_rust(self):
        assert isinstance(get_analyzer("rust"), RustAnalyzer)

    def test_get_analyzer_perl(self):
        assert isinstance(get_analyzer("perl"), PerlAnalyzer)

    def test_get_analyzer_unknown(self):
        with pytest.raises(ValueError, match="Unsupported language"):
            get_analyzer("fortran")

    def test_all_analyzers_subclass_base(self):
        for cls in ANALYZER_MAP.values():
            assert issubclass(cls, BaseAnalyzer)


class TestCAnalyzer:
    def setup_method(self):
        self.analyzer = CAnalyzer()

    def test_properties(self):
        assert self.analyzer.language_name == "C/C++"
        assert ".c" in self.analyzer.file_extensions
        assert ".h" in self.analyzer.file_extensions

    def test_extract_tokens_from_file(self, tmp_path):
        src = tmp_path / "test.c"
        src.write_text(
            '#include "mbedtls/ssl.h"\n'
            "void foo() {\n"
            "    mbedtls_ssl_init(&ctx);\n"
            "    mbedtls_ssl_read(&ctx, buf, len);\n"
            "}\n"
        )
        tokens = self.analyzer.extract_tokens(str(src))
        assert isinstance(tokens, list)
        assert all(isinstance(t, tuple) and len(t) == 3 for t in tokens)

        names = [t[0] for t in tokens]
        assert "mbedtls_ssl_init" in names
        assert "mbedtls_ssl_read" in names

    def test_extract_tokens_line_numbers(self, tmp_path):
        src = tmp_path / "lines.c"
        src.write_text("int main() {\n    mbedtls_ssl_free(&ctx);\n}\n")
        tokens = self.analyzer.extract_tokens(str(src))
        ssl_free = [t for t in tokens if t[0] == "mbedtls_ssl_free"]
        assert len(ssl_free) >= 1
        assert ssl_free[0][1] == 2

    def test_scan_directory(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.c").write_text("void mbedtls_aes_encrypt() {}\n")
        (src / "b.py").write_text("import os\n")  # should be ignored
        results = self.analyzer.scan_directory(str(src))
        assert len(results) == 1
        assert results[0][0].endswith("a.c")

    def test_scan_directory_not_found(self):
        with pytest.raises(FileNotFoundError):
            self.analyzer.scan_directory("/nonexistent/path")

    def test_skips_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "bad.c").write_text("void test() {}\n")
        results = self.analyzer.scan_directory(str(tmp_path))
        assert len(results) == 0

    def test_scan_single_file(self, tmp_path):
        f = tmp_path / "single.c"
        f.write_text("void mbedtls_sha256_init(ctx) {}\n")
        results = self.analyzer.scan_directory(str(f))
        assert len(results) == 1

    def test_extract_includes(self, tmp_path):
        src = tmp_path / "inc.c"
        src.write_text('#include "mbedtls/ssl.h"\n')
        tokens = self.analyzer.extract_tokens(str(src))
        names = [t[0] for t in tokens]
        assert "mbedtls_ssl_h" in names


class TestPythonAnalyzer:
    def setup_method(self):
        self.analyzer = PythonAnalyzer()

    def test_properties(self):
        assert self.analyzer.language_name == "Python"
        assert ".py" in self.analyzer.file_extensions

    def test_extract_imports(self, tmp_path):
        src = tmp_path / "test.py"
        src.write_text("import hashlib\nfrom cryptography.hazmat.primitives import hashes\n")
        tokens = self.analyzer.extract_tokens(str(src))
        names = [t[0] for t in tokens]
        assert "hashlib" in names
        assert "cryptography.hazmat.primitives" in names

    def test_extract_function_calls(self, tmp_path):
        src = tmp_path / "calls.py"
        src.write_text("hashlib.sha256(data)\ncrypto.encrypt(key, plaintext)\n")
        tokens = self.analyzer.extract_tokens(str(src))
        names = [t[0] for t in tokens]
        assert "hashlib.sha256" in names


class TestJavaAnalyzer:
    def setup_method(self):
        self.analyzer = JavaAnalyzer()

    def test_extract_imports(self, tmp_path):
        src = tmp_path / "Test.java"
        src.write_text("import javax.crypto.Cipher;\nimport java.security.KeyPairGenerator;\n")
        tokens = self.analyzer.extract_tokens(str(src))
        names = [t[0] for t in tokens]
        assert "javax.crypto.Cipher" in names

    def test_extract_method_calls(self, tmp_path):
        src = tmp_path / "Main.java"
        src.write_text("Cipher cipher = Cipher.getInstance(\"AES\");\n")
        tokens = self.analyzer.extract_tokens(str(src))
        names = [t[0] for t in tokens]
        assert "Cipher.getInstance" in names


class TestRustAnalyzer:
    def setup_method(self):
        self.analyzer = RustAnalyzer()

    def test_extract_use(self, tmp_path):
        src = tmp_path / "main.rs"
        src.write_text("use ring::aead;\nuse openssl::ssl::SslMethod;\n")
        tokens = self.analyzer.extract_tokens(str(src))
        names = [t[0] for t in tokens]
        assert any("ring" in n for n in names)
        assert any("openssl" in n for n in names)


class TestCSharpAnalyzer:
    def setup_method(self):
        self.analyzer = CSharpAnalyzer()

    def test_extract_using(self, tmp_path):
        src = tmp_path / "Program.cs"
        src.write_text(
            "using System.Security.Cryptography;\n"
            "var aes = Aes.Create();\n"
        )
        tokens = self.analyzer.extract_tokens(str(src))
        names = [t[0] for t in tokens]
        assert "System.Security.Cryptography" in names


class TestPerlAnalyzer:
    def setup_method(self):
        self.analyzer = PerlAnalyzer()

    def test_extract_use(self, tmp_path):
        src = tmp_path / "test.pl"
        src.write_text("use Crypt::OpenSSL::RSA;\nuse Digest::SHA;\n")
        tokens = self.analyzer.extract_tokens(str(src))
        names = [t[0] for t in tokens]
        assert any("Crypt" in n for n in names)
        assert any("Digest" in n for n in names)
