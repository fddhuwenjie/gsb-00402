"""Tests for the baseline diff engine — added / removed / changed detection and classification."""

import pytest

from app.core.diff_engine import DiffEngine


def _component(
    library_key: str,
    name: str,
    signature: str,
    file: str,
    line: int = 1,
    comp_type: str = "crypto_library",
    match_type: str = "exact",
    confidence: float = 1.0,
    matched_text: str | None = None,
):
    """Build a single-function, single-location component for a CBOM report."""
    return {
        "name": name,
        "library_key": library_key,
        "type": comp_type,
        "version": "unknown",
        "total_function_matches": 1,
        "total_occurrences": 1,
        "files_involved": 1,
        "functions": [
            {
                "signature": signature,
                "match_type": match_type,
                "best_confidence": confidence,
                "locations": [
                    {
                        "file": file,
                        "line": line,
                        "matched_text": matched_text or signature,
                        "confidence": confidence,
                        "context": f"{signature}(...);",
                    }
                ],
            }
        ],
    }


def _report(components, language="c"):
    return {
        "cbom_version": "1.0",
        "metadata": {
            "tool": "CBOM Analyzer",
            "language": language,
            "target_path": "/code",
            "signature_files": ["test.yar"],
        },
        "summary": {
            "total_files_scanned": 1,
            "total_matches": sum(c["total_occurrences"] for c in components),
            "total_crypto_components": len(components),
            "risk_level": "none",
            "scan_duration_seconds": 0.1,
        },
        "components": components,
    }


class TestAssetExtraction:
    def setup_method(self):
        self.engine = DiffEngine()

    def test_extract_flat_per_file_assets(self):
        report = _report([
            _component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c", line=10),
            _component("openssl", "OpenSSL", "EVP_EncryptInit", "b.c", line=20),
        ])
        assets = self.engine.extract_assets(report)
        assert len(assets) == 2
        keys = {a["key"] for a in assets}
        assert "mbedtls::mbedtls_ssl_read::a.c" in keys
        assert "openssl::EVP_EncryptInit::b.c" in keys

    def test_asset_carries_language_and_algorithm(self):
        report = _report(
            [_component("aes", "AES", "AES_encrypt", "crypto.c")],
            language="python",
        )
        assets = self.engine.extract_assets(report)
        assert len(assets) == 1
        a = assets[0]
        assert a["language"] == "python"
        assert a["algorithm_name"] == "AES"
        assert a["library_key"] == "aes"
        assert a["file"] == "crypto.c"
        assert a["signature"] == "AES_encrypt"
        assert a["occurrences"] == 1
        assert a["lines"] == [1]

    def test_multiple_locations_same_file_grouped(self):
        comp = _component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c", line=1)
        comp["functions"][0]["locations"].append(
            {"file": "a.c", "line": 5, "matched_text": "mbedtls_ssl_read",
             "confidence": 0.9, "context": "x"}
        )
        comp["total_occurrences"] = 2
        report = _report([comp])
        assets = self.engine.extract_assets(report)
        assert len(assets) == 1
        assert assets[0]["occurrences"] == 2
        assert assets[0]["lines"] == [1, 5]
        assert assets[0]["confidence"] == 1.0

    def test_same_function_different_files_produces_two_assets(self):
        comp = _component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c", line=1)
        comp["functions"][0]["locations"].append(
            {"file": "b.c", "line": 2, "matched_text": "mbedtls_ssl_read",
             "confidence": 1.0, "context": "x"}
        )
        comp["total_occurrences"] = 2
        comp["files_involved"] = 2
        report = _report([comp])
        assets = self.engine.extract_assets(report)
        assert len(assets) == 2
        files = {a["file"] for a in assets}
        assert files == {"a.c", "b.c"}

    def test_deprecated_algorithm_marks_high_risk(self):
        report = _report([_component("openssl", "OpenSSL", "MD5_Init", "hash.c")])
        assets = self.engine.extract_assets(report)
        assert assets[0]["risk_level"] == "high"

    def test_non_deprecated_algorithm_marks_info_risk(self):
        report = _report([_component("mbedtls", "Mbed TLS", "mbedtls_sha256", "hash.c")])
        assets = self.engine.extract_assets(report)
        assert assets[0]["risk_level"] == "info"

    def test_empty_report_extracts_nothing(self):
        assert self.engine.extract_assets(_report([])) == []
        assert self.engine.extract_assets({}) == []


class TestDiffCalculation:
    def setup_method(self):
        self.engine = DiffEngine()

    def test_added_assets(self):
        baseline = _report([_component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c")])
        current = _report([
            _component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c"),
            _component("openssl", "OpenSSL", "RSA_new", "b.c"),
        ])
        diff = self.engine.compute_diff(baseline, current)
        assert diff["summary"]["added"] == 1
        assert diff["summary"]["removed"] == 0
        assert diff["summary"]["changed"] == 0
        assert diff["summary"]["unchanged"] == 1
        assert len(diff["added"]) == 1
        assert diff["added"][0]["signature"] == "RSA_new"

    def test_removed_assets(self):
        baseline = _report([
            _component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c"),
            _component("openssl", "OpenSSL", "RSA_new", "b.c"),
        ])
        current = _report([_component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c")])
        diff = self.engine.compute_diff(baseline, current)
        assert diff["summary"]["removed"] == 1
        assert diff["summary"]["added"] == 0
        assert diff["removed"][0]["signature"] == "RSA_new"

    def test_changed_confidence(self):
        baseline = _report([_component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c", confidence=1.0)])
        current = _report([_component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c", confidence=0.8, match_type="fuzzy")])
        diff = self.engine.compute_diff(baseline, current)
        assert diff["summary"]["changed"] == 1
        assert diff["summary"]["added"] == 0
        assert diff["summary"]["removed"] == 0
        change = diff["changed"][0]
        assert set(change["changed_fields"]) == {"match_type", "confidence"}
        assert change["before"]["confidence"] == 1.0
        assert change["after"]["confidence"] == 0.8

    def test_changed_lines(self):
        base_comp = _component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c", line=1)
        cur_comp = _component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c", line=2)
        diff = self.engine.compute_diff(_report([base_comp]), _report([cur_comp]))
        assert diff["summary"]["changed"] == 1
        assert "lines" in diff["changed"][0]["changed_fields"]

    def test_changed_occurrences(self):
        base_comp = _component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c", line=1)
        cur_comp = _component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c", line=1)
        cur_comp["functions"][0]["locations"].append(
            {"file": "a.c", "line": 9, "matched_text": "mbedtls_ssl_read",
             "confidence": 1.0, "context": "x"}
        )
        cur_comp["total_occurrences"] = 2
        diff = self.engine.compute_diff(_report([base_comp]), _report([cur_comp]))
        assert diff["summary"]["changed"] == 1
        assert "occurrences" in diff["changed"][0]["changed_fields"]
        assert "lines" in diff["changed"][0]["changed_fields"]

    def test_same_function_different_file_is_add_and_remove(self):
        baseline = _report([_component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "old.c")])
        current = _report([_component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "new.c")])
        diff = self.engine.compute_diff(baseline, current)
        assert diff["summary"]["added"] == 1
        assert diff["summary"]["removed"] == 1
        assert diff["summary"]["changed"] == 0
        assert diff["added"][0]["file"] == "new.c"
        assert diff["removed"][0]["file"] == "old.c"

    def test_unchanged_assets_tracked(self):
        report = _report([_component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c")])
        diff = self.engine.compute_diff(report, report)
        assert diff["summary"]["unchanged"] == 1
        assert diff["summary"]["added"] == 0
        assert diff["summary"]["removed"] == 0
        assert diff["summary"]["changed"] == 0

    def test_totals_in_summary(self):
        baseline = _report([
            _component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c"),
            _component("openssl", "OpenSSL", "RSA_new", "b.c"),
        ])
        current = _report([
            _component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c"),
            _component("openssl", "OpenSSL", "EVP_EncryptInit", "c.c"),
        ])
        diff = self.engine.compute_diff(baseline, current)
        assert diff["summary"]["total_baseline_assets"] == 2
        assert diff["summary"]["total_current_assets"] == 2

    def test_meta_passed_through(self):
        diff = self.engine.compute_diff(
            _report([]), _report([]),
            baseline_meta={"id": 7, "name": "base"},
            current_meta={"task_id": 9, "name": "scan"},
        )
        assert diff["baseline"] == {"id": 7, "name": "base"}
        assert diff["current"] == {"task_id": 9, "name": "scan"}


class TestDiffRiskLevel:
    def setup_method(self):
        self.engine = DiffEngine()

    def test_no_changes_is_none(self):
        report = _report([_component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c")])
        diff = self.engine.compute_diff(report, report)
        assert diff["summary"]["risk_level"] == "none"

    def test_added_deprecated_is_high(self):
        baseline = _report([])
        current = _report([_component("openssl", "OpenSSL", "MD5_Init", "hash.c")])
        diff = self.engine.compute_diff(baseline, current)
        assert diff["summary"]["risk_level"] == "high"

    def test_few_added_is_low(self):
        baseline = _report([])
        current = _report([_component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c")])
        diff = self.engine.compute_diff(baseline, current)
        assert diff["summary"]["risk_level"] == "low"

    def test_many_added_is_medium(self):
        baseline = _report([])
        comps = [
            _component("mbedtls", "Mbed TLS", f"mbedtls_func_{i}", f"f{i}.c")
            for i in range(12)
        ]
        diff = self.engine.compute_diff(baseline, _report(comps))
        assert diff["summary"]["risk_level"] == "medium"


class TestClassification:
    def setup_method(self):
        self.engine = DiffEngine()

    def test_classify_by_file(self):
        baseline = _report([_component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c")])
        current = _report([
            _component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c"),
            _component("openssl", "OpenSSL", "RSA_new", "b.c"),
        ])
        diff = self.engine.compute_diff(baseline, current)
        by_file = diff["classified"]["by_file"]
        assert "b.c" in by_file
        assert len(by_file["b.c"]["added"]) == 1
        assert by_file["b.c"]["removed"] == []
        assert by_file["b.c"]["changed"] == []
        assert "a.c" not in by_file

    def test_classify_by_language(self):
        baseline = _report([], language="c")
        current = _report(
            [_component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c")],
            language="c",
        )
        diff = self.engine.compute_diff(baseline, current)
        assert "c" in diff["classified"]["by_language"]
        assert len(diff["classified"]["by_language"]["c"]["added"]) == 1

    def test_classify_by_algorithm(self):
        baseline = _report([])
        current = _report([_component("rsa", "RSA", "RSA_new", "crypto.c")])
        diff = self.engine.compute_diff(baseline, current)
        assert "RSA" in diff["classified"]["by_algorithm"]
        assert len(diff["classified"]["by_algorithm"]["RSA"]["added"]) == 1

    def test_classify_by_risk(self):
        baseline = _report([])
        current = _report([
            _component("openssl", "OpenSSL", "MD5_Init", "hash.c"),
            _component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "ssl.c"),
        ])
        diff = self.engine.compute_diff(baseline, current)
        by_risk = diff["classified"]["by_risk"]
        assert len(by_risk["high"]["added"]) == 1
        assert len(by_risk["info"]["added"]) == 1


class TestNoBaseline:
    """When no baseline is provided the engine must treat every current asset as newly added."""

    def setup_method(self):
        self.engine = DiffEngine()

    def test_none_baseline_all_assets_added(self):
        current = _report([
            _component("mbedtls", "Mbed TLS", "mbedtls_ssl_read", "a.c"),
            _component("openssl", "OpenSSL", "RSA_new", "b.c"),
        ])
        diff = self.engine.compute_diff(None, current, baseline_meta=None,
                                        current_meta={"task_id": 1})
        assert diff["summary"]["total_baseline_assets"] == 0
        assert diff["summary"]["total_current_assets"] == 2
        assert diff["summary"]["added"] == 2
        assert diff["summary"]["removed"] == 0
        assert diff["summary"]["changed"] == 0
        assert diff["baseline"] == {}

    def test_none_baseline_empty_current(self):
        diff = self.engine.compute_diff(None, _report([]))
        assert diff["summary"]["added"] == 0
        assert diff["summary"]["removed"] == 0
        assert diff["summary"]["risk_level"] == "none"


class TestEmptyResults:
    """Both reports empty (or no crypto assets) must yield an all-zero diff."""

    def setup_method(self):
        self.engine = DiffEngine()

    def test_both_empty_reports(self):
        diff = self.engine.compute_diff(_report([]), _report([]))
        assert diff["summary"]["total_baseline_assets"] == 0
        assert diff["summary"]["total_current_assets"] == 0
        assert diff["summary"]["added"] == 0
        assert diff["summary"]["removed"] == 0
        assert diff["summary"]["changed"] == 0
        assert diff["summary"]["unchanged"] == 0
        assert diff["summary"]["risk_level"] == "none"
        assert diff["added"] == []
        assert diff["removed"] == []
        assert diff["changed"] == []
        assert diff["unchanged"] == []

    def test_classification_empty_when_no_assets(self):
        diff = self.engine.compute_diff(_report([]), _report([]))
        assert diff["classified"]["by_file"] == {}
        assert diff["classified"]["by_language"] == {}
        assert diff["classified"]["by_algorithm"] == {}
        assert diff["classified"]["by_risk"]["high"]["added"] == []

    def test_empty_components_key_also_handled(self):
        diff = self.engine.compute_diff({}, {})
        assert diff["summary"]["added"] == 0
        assert diff["summary"]["removed"] == 0
        assert diff["summary"]["risk_level"] == "none"
