"""Tests for YaraParser — validates parse_content and parse_file return YaraRule dataclasses."""

import pytest
from app.core.yara_parser import YaraParser, YaraRule, YaraSignature


SAMPLE_YARA = """
rule Func_embedssl
{
    meta:
        description = "Functions extracted from embedssl.h"
        extraction_method = "AST_parser_standalone"
        generated = "2025-12-24 14:59:54"
        total_functions = 93

    strings:
        $func002 = "mbedtls_ssl_async_cancel_t"
        $func003 = "mbedtls_ssl_async_resume_t"
        $func004 = "mbedtls_ssl_cache_set_t"
}
"""

MULTI_RULE_YARA = """
rule Func_openssl
{
    meta:
        description = "OpenSSL functions"
    strings:
        $f1 = "SSL_CTX_new"
        $f2 = "EVP_EncryptInit"
}

rule Func_sodium
{
    meta:
        description = "libsodium functions"
    strings:
        $s1 = "crypto_secretbox_open"
}
"""


class TestYaraParser:
    def setup_method(self):
        self.parser = YaraParser()

    def test_parse_content_returns_list_of_yara_rules(self):
        rules = self.parser.parse_content(SAMPLE_YARA)
        assert isinstance(rules, list)
        assert len(rules) == 1
        assert isinstance(rules[0], YaraRule)

    def test_parse_content_extracts_meta(self):
        rule = self.parser.parse_content(SAMPLE_YARA)[0]
        assert rule.name == "Func_embedssl"
        assert rule.description == "Functions extracted from embedssl.h"
        assert rule.extraction_method == "AST_parser_standalone"
        assert rule.generated == "2025-12-24 14:59:54"
        assert rule.total_functions == 93

    def test_parse_content_extracts_signatures(self):
        rule = self.parser.parse_content(SAMPLE_YARA)[0]
        assert len(rule.signatures) == 3
        assert all(isinstance(s, YaraSignature) for s in rule.signatures)

        patterns = [s.pattern for s in rule.signatures]
        assert "mbedtls_ssl_async_cancel_t" in patterns
        assert "mbedtls_ssl_async_resume_t" in patterns
        assert "mbedtls_ssl_cache_set_t" in patterns

    def test_signature_identifiers(self):
        rule = self.parser.parse_content(SAMPLE_YARA)[0]
        identifiers = [s.identifier for s in rule.signatures]
        assert "func002" in identifiers
        assert "func003" in identifiers

    def test_signature_prefix_extraction(self):
        rule = self.parser.parse_content(SAMPLE_YARA)[0]
        sig = next(s for s in rule.signatures if s.pattern == "mbedtls_ssl_async_cancel_t")
        assert sig.prefix == "mbedtls_ssl_async_cancel_"

    def test_parse_multiple_rules(self):
        rules = self.parser.parse_content(MULTI_RULE_YARA)
        assert len(rules) == 2
        names = {r.name for r in rules}
        assert names == {"Func_openssl", "Func_sodium"}
        assert len(rules[0].signatures) == 2
        assert len(rules[1].signatures) == 1

    def test_parse_content_empty_returns_empty(self):
        assert self.parser.parse_content("") == []
        assert self.parser.parse_content("no rules here") == []

    def test_parse_content_no_strings(self):
        yara = 'rule Empty { meta: description = "none" }'
        rules = self.parser.parse_content(yara)
        assert len(rules) == 1
        assert rules[0].signatures == []

    def test_parse_content_with_hex_strings(self):
        yara = 'rule Hex { strings: $h1 = { AA BB CC } }'
        rules = self.parser.parse_content(yara)
        assert len(rules) == 1
        assert rules[0].signatures[0].pattern.startswith("hex:")

    def test_parse_content_total_functions_fallback(self):
        yara = 'rule NoMeta { strings: $a = "func_a" $b = "func_b" }'
        rule = self.parser.parse_content(yara)[0]
        assert rule.total_functions == 2

    def test_parse_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            self.parser.parse_file("/nonexistent/path.yar")

    def test_parse_file_real(self, tmp_path):
        yar_file = tmp_path / "test.yar"
        yar_file.write_text(SAMPLE_YARA)
        rules = self.parser.parse_file(str(yar_file))
        assert len(rules) == 1
        assert rules[0].name == "Func_embedssl"

    def test_parse_multiple_files(self, tmp_path):
        f1 = tmp_path / "a.yar"
        f2 = tmp_path / "b.yar"
        f1.write_text(SAMPLE_YARA)
        f2.write_text(MULTI_RULE_YARA)
        rules = self.parser.parse_multiple_files([str(f1), str(f2)])
        assert len(rules) == 3

    def test_parse_multiple_files_skips_bad(self, tmp_path):
        f1 = tmp_path / "good.yar"
        f1.write_text(SAMPLE_YARA)
        rules = self.parser.parse_multiple_files([str(f1), "/bad/path.yar"])
        assert len(rules) == 1
