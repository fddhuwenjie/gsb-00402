"""Tests for DiffEngine — baseline diff calculation, no-baseline and empty-result cases."""

import pytest

from app.core.diff_engine import DiffEngine, CHANGE_ADDED, CHANGE_REMOVED, CHANGE_CHANGED
from app.core.fuzzy_matcher import MatchResult, MatchType
from app.core.cbom_generator import CBOMGenerator


def _component(name, library_key, comp_type, functions):
    """Build a CBOM report component.

    functions: list of (signature, match_type, confidence, [(file, line, matched_text)])
    """
    func_dicts = []
    for sig, mtype, conf, locations in functions:
        func_dicts.append({
            "signature": sig,
            "match_type": mtype,
            "best_confidence": conf,
            "locations": [
                {
                    "file": fp,
                    "line": line,
                    "matched_text": text,
                    "confidence": conf,
                    "context": f"{text}(...);",
                }
                for fp, line, text in locations
            ],
        })
    files = {loc[0] for _, _, _, locs in functions for loc in locs}
    return {
        "name": name,
        "library_key": library_key,
        "type": comp_type,
        "version": "unknown",
        "total_function_matches": len(func_dicts),
        "total_occurrences": sum(len(f["locations"]) for f in func_dicts),
        "files_involved": len(files),
        "functions": func_dicts,
    }


def _report(components, language="python"):
    return {
        "cbom_version": "1.0",
        "metadata": {
            "tool": "CBOM Analyzer",
            "target_path": "/code",
            "language": language,
            "signature_files": ["test.yar"],
        },
        "summary": {
            "total_files_scanned": 3,
            "total_matches": sum(c["total_occurrences"] for c in components),
            "total_crypto_components": len(components),
            "risk_level": "none",
            "scan_duration_seconds": 0.1,
        },
        "components": components,
    }


def _make_match(sig, fp, line):
    return MatchResult(
        signature_pattern=sig,
        matched_text=sig,
        match_type=MatchType.EXACT,
        confidence=1.0,
        file_path=fp,
        line_number=line,
        context=f"{sig}(...);",
    )


class TestExtractAssets:
    def setup_method(self):
        self.engine = DiffEngine()

    def test_flatten_report_to_assets(self):
        report = _report([
            _component("Mbed TLS", "mbedtls", "tls_library", [
                ("mbedtls_ssl_read", "exact", 1.0, [
                    ("a.py", 10, "mbedtls_ssl_read"),
                    ("a.py", 20, "mbedtls_ssl_read"),
                    ("b.py", 5, "mbedtls_ssl_read"),
                ]),
            ]),
        ])
        assets = self.engine.extract_assets(report)
        # same function in two files -> two assets
        assert len(assets) == 2
        by_file = {a["file"]: a for a in assets}
        assert by_file["a.py"]["occurrences"] == 2
        assert by_file["a.py"]["lines"] == [10, 20]
        assert by_file["b.py"]["occurrences"] == 1
        assert by_file["a.py"]["algorithm"] == "mbedtls"
        assert by_file["a.py"]["algorithm_name"] == "Mbed TLS"
        assert by_file["a.py"]["language"] == "python"
        assert by_file["a.py"]["signature"] == "mbedtls_ssl_read"

    def test_deprecated_signature_gets_high_risk(self):
        report = _report([
            _component("OpenSSL", "openssl", "tls_library", [
                ("openssl_md5_init", "exact", 1.0, [("a.py", 1, "openssl_md5_init")]),
                ("openssl_encrypt", "exact", 1.0, [("a.py", 2, "openssl_encrypt")]),
            ]),
        ])
        assets = {a["signature"]: a for a in self.engine.extract_assets(report)}
        assert assets["openssl_md5_init"]["risk_level"] == "high"
        assert assets["openssl_encrypt"]["risk_level"] == "info"

    def test_none_and_empty_report(self):
        assert self.engine.extract_assets(None) == []
        assert self.engine.extract_assets({}) == []
        assert self.engine.extract_assets(_report([])) == []

    def test_works_with_real_cbom_generator_output(self):
        gen = CBOMGenerator()
        matches = [
            _make_match("mbedtls_ssl_read", "a.c", 10),
            _make_match("mbedtls_ssl_read", "a.c", 30),
            _make_match("openssl_md5_init", "b.c", 7),
        ]
        report = gen.generate(matches, "/code", "c", ["sigs.yar"], 2, 0.2)
        assets = self.engine.extract_assets(report)
        assert len(assets) == 2
        assert all(a["language"] == "c" for a in assets)
        by_sig = {a["signature"]: a for a in assets}
        assert by_sig["mbedtls_ssl_read"]["occurrences"] == 2
        assert by_sig["openssl_md5_init"]["risk_level"] == "high"


class TestComputeDiff:
    def setup_method(self):
        self.engine = DiffEngine()

    def test_added_removed_changed(self):
        baseline = _report([
            _component("Mbed TLS", "mbedtls", "tls_library", [
                # unchanged asset
                ("mbedtls_ssl_read", "exact", 1.0, [("a.py", 10, "mbedtls_ssl_read")]),
                # removed asset
                ("mbedtls_ssl_write", "exact", 1.0, [("old.py", 3, "mbedtls_ssl_write")]),
                # changed asset: gains a call site
                ("mbedtls_ssl_init", "exact", 0.9, [("a.py", 1, "mbedtls_ssl_init")]),
            ]),
        ])
        current = _report([
            _component("Mbed TLS", "mbedtls", "tls_library", [
                ("mbedtls_ssl_read", "exact", 1.0, [("a.py", 10, "mbedtls_ssl_read")]),
                ("mbedtls_ssl_init", "exact", 0.95, [
                    ("a.py", 1, "mbedtls_ssl_init"),
                    ("a.py", 8, "mbedtls_ssl_init"),
                ]),
                # added asset, deprecated -> high risk
                ("openssl_md5_init", "exact", 1.0, [("new.py", 9, "openssl_md5_init")]),
            ]),
        ])

        diff = self.engine.compute_diff(
            self.engine.extract_assets(baseline),
            self.engine.extract_assets(current),
        )

        summary = diff["summary"]
        assert summary["added"] == 1
        assert summary["removed"] == 1
        assert summary["changed"] == 1
        assert summary["unchanged"] == 1
        assert summary["baseline_asset_count"] == 3
        assert summary["current_asset_count"] == 3

        added_sigs = {a["signature"] for a in diff["added"]}
        removed_sigs = {a["signature"] for a in diff["removed"]}
        assert added_sigs == {"openssl_md5_init"}
        assert removed_sigs == {"mbedtls_ssl_write"}

        changed = diff["changed"][0]
        assert changed["current"]["signature"] == "mbedtls_ssl_init"
        assert "occurrences" in changed["changed_fields"]
        assert "lines" in changed["changed_fields"]
        assert "confidence" in changed["changed_fields"]
        assert changed["baseline"]["occurrences"] == 1
        assert changed["current"]["occurrences"] == 2

    def test_risk_level_change_detected(self):
        # baseline has a generic crypto call, current has a deprecated one at the same key
        # (simulated by same file/algorithm/signature identity but different risk is impossible
        # via signature, so verify risk change through match_type/confidence-free scenario:
        # a weak indicator appearing in signature changes asset risk -> different key instead.
        # Here we directly assert changed_fields includes risk_level when risk differs.)
        baseline_assets = [{
            "key": "a.py::openssl::openssl_digest",
            "file": "a.py", "language": "python", "algorithm": "openssl",
            "algorithm_name": "OpenSSL", "signature": "openssl_digest",
            "match_type": "exact", "confidence": 1.0,
            "occurrences": 1, "lines": [1], "risk_level": "info",
        }]
        current_assets = [dict(baseline_assets[0], risk_level="high")]
        diff = self.engine.compute_diff(baseline_assets, current_assets)
        assert diff["summary"]["changed"] == 1
        assert "risk_level" in diff["changed"][0]["changed_fields"]

    def test_categories_by_file_language_algorithm_risk(self):
        baseline = _report([
            _component("Mbed TLS", "mbedtls", "tls_library", [
                ("mbedtls_ssl_write", "exact", 1.0, [("old.py", 3, "mbedtls_ssl_write")]),
            ]),
        ], language="python")
        current = _report([
            _component("OpenSSL", "openssl", "tls_library", [
                ("openssl_md5_init", "exact", 1.0, [("new.py", 9, "openssl_md5_init")]),
            ]),
        ], language="python")

        diff = self.engine.compute_diff(
            self.engine.extract_assets(baseline),
            self.engine.extract_assets(current),
        )
        cats = diff["categories"]

        assert cats["by_file"]["new.py"][CHANGE_ADDED] == 1
        assert cats["by_file"]["old.py"][CHANGE_REMOVED] == 1
        assert cats["by_language"]["python"][CHANGE_ADDED] == 1
        assert cats["by_language"]["python"][CHANGE_REMOVED] == 1
        assert cats["by_algorithm"]["OpenSSL"][CHANGE_ADDED] == 1
        assert cats["by_algorithm"]["Mbed TLS"][CHANGE_REMOVED] == 1
        assert cats["by_risk_level"]["high"][CHANGE_ADDED] == 1
        assert cats["by_risk_level"]["info"][CHANGE_REMOVED] == 1
        # every bucket carries a total
        for group in cats.values():
            for bucket in group.values():
                assert bucket["total"] == bucket["added"] + bucket["removed"] + bucket["changed"]

    def test_diff_risk_levels(self):
        safe_report = _report([
            _component("Mbed TLS", "mbedtls", "tls_library", [
                ("mbedtls_ssl_read", "exact", 1.0, [("a.py", 10, "mbedtls_ssl_read")]),
            ]),
        ])

        # high-risk addition -> diff risk high
        with_high = _report([
            _component("OpenSSL", "openssl", "tls_library", [
                ("openssl_rc4_set_key", "exact", 1.0, [("a.py", 1, "openssl_rc4_set_key")]),
            ]),
        ])
        diff = self.engine.compute_diff(
            self.engine.extract_assets(safe_report), self.engine.extract_assets(with_high)
        )
        assert diff["summary"]["risk_level"] == "high"

        # benign addition (different safe algorithm) -> medium
        with_safe = _report([
            _component("Mbed TLS", "mbedtls", "tls_library", [
                ("mbedtls_ssl_read", "exact", 1.0, [("a.py", 10, "mbedtls_ssl_read")]),
                ("mbedtls_ssl_write", "exact", 1.0, [("a.py", 11, "mbedtls_ssl_write")]),
            ]),
        ])
        diff = self.engine.compute_diff(
            self.engine.extract_assets(safe_report), self.engine.extract_assets(with_safe)
        )
        assert diff["summary"]["risk_level"] == "medium"

    def test_no_baseline_all_assets_added(self):
        """Without a baseline (None or empty asset list) every current asset is 'added'."""
        current = _report([
            _component("Mbed TLS", "mbedtls", "tls_library", [
                ("mbedtls_ssl_read", "exact", 1.0, [("a.py", 10, "mbedtls_ssl_read")]),
            ]),
            _component("OpenSSL", "openssl", "tls_library", [
                ("openssl_md5_init", "exact", 1.0, [("b.py", 2, "openssl_md5_init")]),
            ]),
        ])

        for baseline_assets in (None, []):
            diff = self.engine.compute_diff(baseline_assets, self.engine.extract_assets(current))
            assert diff["summary"]["baseline_asset_count"] == 0
            assert diff["summary"]["added"] == 2
            assert diff["summary"]["removed"] == 0
            assert diff["summary"]["changed"] == 0
            assert diff["summary"]["unchanged"] == 0
            assert {a["signature"] for a in diff["added"]} == {
                "mbedtls_ssl_read", "openssl_md5_init"
            }
            # newly introduced weak crypto is flagged even without a baseline
            assert diff["summary"]["risk_level"] == "high"

    def test_no_baseline_and_empty_current(self):
        """No baseline plus an empty scan result -> empty diff, risk none."""
        diff = self.engine.compute_diff(None, [])
        assert diff["summary"] == {
            "baseline_asset_count": 0,
            "current_asset_count": 0,
            "added": 0,
            "removed": 0,
            "changed": 0,
            "unchanged": 0,
            "risk_level": "none",
        }
        assert diff["added"] == []
        assert diff["removed"] == []
        assert diff["changed"] == []

    def test_empty_results_identical_reports(self):
        """Two empty reports -> no differences at all."""
        diff = self.engine.compute_diff(
            self.engine.extract_assets(_report([])),
            self.engine.extract_assets(_report([])),
        )
        assert diff["summary"]["added"] == 0
        assert diff["summary"]["removed"] == 0
        assert diff["summary"]["changed"] == 0
        assert diff["summary"]["unchanged"] == 0
        assert diff["summary"]["risk_level"] == "none"
        assert diff["categories"] == {
            "by_file": {}, "by_language": {}, "by_algorithm": {}, "by_risk_level": {}
        }

    def test_identical_reports_have_no_diff(self):
        report = _report([
            _component("Mbed TLS", "mbedtls", "tls_library", [
                ("mbedtls_ssl_read", "exact", 1.0, [
                    ("a.py", 10, "mbedtls_ssl_read"),
                    ("a.py", 20, "mbedtls_ssl_read"),
                ]),
            ]),
        ])
        assets = self.engine.extract_assets(report)
        diff = self.engine.compute_diff(assets, [dict(a) for a in assets])
        assert diff["summary"]["unchanged"] == 1
        assert diff["summary"]["added"] == 0
        assert diff["summary"]["removed"] == 0
        assert diff["summary"]["changed"] == 0
        assert diff["summary"]["risk_level"] == "none"

    def test_metadata_passed_through(self):
        diff = self.engine.compute_diff(
            None, [],
            baseline_meta={"id": 1, "name": "baseline-v1"},
            current_meta={"task_id": 9, "task_name": "scan-2"},
        )
        assert diff["baseline"]["name"] == "baseline-v1"
        assert diff["current"]["task_id"] == 9
