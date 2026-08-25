"""Tests for CBOMGenerator — validates report structure and field naming."""

import json
import pytest
from app.core.fuzzy_matcher import MatchResult, MatchType
from app.core.cbom_generator import CBOMGenerator


def _make_match(sig: str, text: str, mtype: MatchType, conf: float, fp: str, line: int) -> MatchResult:
    return MatchResult(
        signature_pattern=sig,
        matched_text=text,
        match_type=mtype,
        confidence=conf,
        file_path=fp,
        line_number=line,
        context=f"{text}(...);",
    )


class TestCBOMGenerator:
    def setup_method(self):
        self.gen = CBOMGenerator()

    def test_empty_matches(self):
        report = self.gen.generate([], "/code", "c", ["test.yar"], 10, 1.5)
        assert report["summary"]["total_matches"] == 0
        assert report["summary"]["total_crypto_components"] == 0
        assert report["summary"]["risk_level"] == "none"
        assert report["components"] == []

    def test_report_structure(self):
        matches = [
            _make_match("mbedtls_ssl_read", "mbedtls_ssl_read", MatchType.EXACT, 1.0, "a.c", 10),
        ]
        report = self.gen.generate(matches, "/code", "c", ["sigs.yar"], 5, 0.5)

        assert "cbom_version" in report
        assert "metadata" in report
        assert "summary" in report
        assert "components" in report

        meta = report["metadata"]
        assert meta["tool"] == "CBOM Analyzer"
        assert meta["target_path"] == "/code"
        assert meta["language"] == "c"
        assert meta["signature_files"] == ["sigs.yar"]

    def test_summary_field_naming(self):
        """Verify summary uses 'total_crypto_components', not 'total_components'."""
        matches = [
            _make_match("mbedtls_ssl_read", "mbedtls_ssl_read", MatchType.EXACT, 1.0, "a.c", 1),
        ]
        report = self.gen.generate(matches, "/code", "c", ["f.yar"], 1, 0.1)
        summary = report["summary"]

        assert "total_crypto_components" in summary
        assert "total_files_scanned" in summary
        assert "total_matches" in summary
        assert "risk_level" in summary
        assert "scan_duration_seconds" in summary

    def test_component_aggregation(self):
        matches = [
            _make_match("mbedtls_ssl_read", "mbedtls_ssl_read", MatchType.EXACT, 1.0, "a.c", 1),
            _make_match("mbedtls_ssl_write", "mbedtls_ssl_write", MatchType.EXACT, 1.0, "a.c", 2),
            _make_match("openssl_encrypt", "openssl_encrypt", MatchType.EXACT, 1.0, "b.c", 3),
        ]
        report = self.gen.generate(matches, "/code", "c", ["f.yar"], 2, 0.1)
        assert report["summary"]["total_crypto_components"] == 2
        names = {c["name"] for c in report["components"]}
        assert "Mbed TLS" in names
        assert "OpenSSL" in names

    def test_component_fields(self):
        matches = [
            _make_match("mbedtls_ssl_read", "mbedtls_ssl_read", MatchType.EXACT, 1.0, "a.c", 1),
            _make_match("mbedtls_ssl_read", "mbedtls_ssl_read", MatchType.EXACT, 1.0, "b.c", 5),
        ]
        report = self.gen.generate(matches, "/code", "c", ["f.yar"], 2, 0.1)
        comp = report["components"][0]

        assert comp["name"] == "Mbed TLS"
        assert comp["library_key"] == "mbedtls"
        assert comp["type"] == "tls_library"
        assert comp["total_function_matches"] == 1
        assert comp["total_occurrences"] == 2
        assert comp["files_involved"] == 2

    def test_function_locations(self):
        matches = [
            _make_match("mbedtls_ssl_read", "mbedtls_ssl_read", MatchType.EXACT, 1.0, "a.c", 10),
        ]
        report = self.gen.generate(matches, "/code", "c", ["f.yar"], 1, 0.1)
        func = report["components"][0]["functions"][0]
        assert func["signature"] == "mbedtls_ssl_read"
        assert func["best_confidence"] == 1.0
        assert len(func["locations"]) == 1
        loc = func["locations"][0]
        assert loc["file"] == "a.c"
        assert loc["line"] == 10

    def test_risk_high_for_deprecated(self):
        matches = [
            _make_match("openssl_md5_init", "openssl_md5_init", MatchType.EXACT, 1.0, "a.c", 1),
        ]
        report = self.gen.generate(matches, "/code", "c", ["f.yar"], 1, 0.1)
        assert report["summary"]["risk_level"] == "high"

    def test_risk_medium_for_many_matches(self):
        matches = [
            _make_match(f"mbedtls_func_{i}", f"mbedtls_func_{i}", MatchType.EXACT, 1.0, "a.c", i)
            for i in range(60)
        ]
        report = self.gen.generate(matches, "/code", "c", ["f.yar"], 1, 0.1)
        assert report["summary"]["risk_level"] == "medium"

    def test_risk_info_for_few(self):
        matches = [
            _make_match("mbedtls_ssl_init", "mbedtls_ssl_init", MatchType.EXACT, 1.0, "a.c", 1),
        ]
        report = self.gen.generate(matches, "/code", "c", ["f.yar"], 1, 0.1)
        assert report["summary"]["risk_level"] == "info"

    def test_to_json(self):
        matches = [
            _make_match("mbedtls_ssl_read", "mbedtls_ssl_read", MatchType.EXACT, 1.0, "a.c", 1),
        ]
        report = self.gen.generate(matches, "/code", "c", ["f.yar"], 1, 0.1)
        json_str = CBOMGenerator.to_json(report)
        parsed = json.loads(json_str)
        assert parsed["cbom_version"] == "1.0"
