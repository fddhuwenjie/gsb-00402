"""Tests for the BaselineDiffEngine — added/removed/changed assets and categories."""

from app.core.baseline_diff import BaselineDiffEngine


def _report(language, components):
    return {"metadata": {"language": language}, "components": components}


def _component(name, library_key, comp_type, functions):
    return {"name": name, "library_key": library_key, "type": comp_type, "functions": functions}


def _func(signature, locations, match_type="exact", best_confidence=1.0):
    return {
        "signature": signature,
        "match_type": match_type,
        "best_confidence": best_confidence,
        "locations": locations,
    }


def _loc(file, line):
    return {"file": file, "line": line, "matched_text": "x", "confidence": 1.0, "context": ""}


class TestBaselineDiffEngine:
    def setup_method(self):
        self.engine = BaselineDiffEngine()

    def test_added_removed_changed(self):
        baseline = _report("c", [
            _component("Mbed TLS", "mbedtls", "tls_library", [
                _func("mbedtls_ssl_read", [_loc("a.c", 10)]),
                _func("mbedtls_ssl_write", [_loc("a.c", 20)]),
            ]),
        ])
        new = _report("c", [
            _component("Mbed TLS", "mbedtls", "tls_library", [
                # mbedtls_ssl_read now appears in two files -> changed
                _func("mbedtls_ssl_read", [_loc("a.c", 10), _loc("b.c", 5)]),
                # mbedtls_ssl_write removed
            ]),
            _component("OpenSSL", "openssl", "tls_library", [
                _func("openssl_encrypt", [_loc("c.c", 1)]),  # added
            ]),
        ])

        diff = self.engine.compute(baseline, new)

        assert diff["summary"]["total_added"] == 1
        assert diff["summary"]["total_removed"] == 1
        assert diff["summary"]["total_changed"] == 1

        assert diff["added"][0]["signature"] == "openssl_encrypt"
        assert diff["removed"][0]["signature"] == "mbedtls_ssl_write"

        changed = diff["changed"][0]
        assert changed["signature"] == "mbedtls_ssl_read"
        fields = {c["field"] for c in changed["changes"]}
        assert "files_involved" in fields
        assert "total_occurrences" in fields
        assert changed["previous"]["files_involved"] == 1

    def test_classification_buckets(self):
        baseline = _report("c", [])
        new = _report("c", [
            _component("MD5 (deprecated)", "md5", "hash_algorithm", [
                _func("openssl_md5_init", [_loc("weak.c", 3)]),
            ]),
            _component("AES", "aes", "cipher_algorithm", [
                _func("aes_encrypt", [_loc("crypto.c", 8)]),
            ]),
        ])

        diff = self.engine.compute(baseline, new)

        # by risk: md5 asset is high, aes asset is info
        assert diff["by_risk_level"]["high"]["added"] == 1
        assert diff["by_risk_level"]["info"]["added"] == 1
        # by file
        assert diff["by_file"]["weak.c"]["added"] == 1
        assert diff["by_file"]["crypto.c"]["added"] == 1
        # by language
        assert diff["by_language"]["c"]["added"] == 2
        # by algorithm
        assert diff["by_algorithm"]["AES"]["added"] == 1
        assert diff["by_algorithm"]["MD5 (deprecated)"]["added"] == 1

    def test_deprecated_asset_risk_high(self):
        """Per-asset risk reuses CBOM deprecated-algorithm indicators."""
        assets = self.engine._extract_assets(_report("c", [
            _component("SHA-1", "sha1", "hash_algorithm", [
                _func("sha1_update", [_loc("a.c", 1)]),
            ]),
        ]))
        assert list(assets.values())[0]["risk_level"] == "high"

    def test_file_move_flagged_as_changed(self):
        """An asset moving files (same counts) must be a change, and by_file must
        reflect both the original and the new file."""
        baseline = _report("c", [
            _component("Mbed TLS", "mbedtls", "tls_library", [
                _func("mbedtls_ssl_read", [_loc("old.c", 10)]),
            ]),
        ])
        new = _report("c", [
            _component("Mbed TLS", "mbedtls", "tls_library", [
                _func("mbedtls_ssl_read", [_loc("new.c", 10)]),
            ]),
        ])

        diff = self.engine.compute(baseline, new)

        # File count (1) and occurrence count (1) are unchanged, but the file
        # list differs -> must be flagged as changed, not identical.
        assert diff["summary"]["total_changed"] == 1
        assert diff["summary"]["total_added"] == 0
        assert diff["summary"]["total_removed"] == 0

        changed = diff["changed"][0]
        assert changed["signature"] == "mbedtls_ssl_read"
        fields = {c["field"] for c in changed["changes"]}
        assert "files" in fields
        assert "files_involved" not in fields  # count unchanged
        assert "total_occurrences" not in fields  # count unchanged
        assert changed["removed_files"] == ["old.c"]
        assert changed["added_files"] == ["new.c"]
        assert changed["previous"]["files"] == ["old.c"]

        # by_file surfaces both the original and new files for the moved asset.
        assert diff["by_file"]["old.c"]["changed"] == 1
        assert diff["by_file"]["new.c"]["changed"] == 1

    def test_file_added_to_asset_flagged_as_changed(self):
        """Adding a second file to an asset changes both files and file count."""
        baseline = _report("c", [
            _component("AES", "aes", "cipher_algorithm", [
                _func("aes_encrypt", [_loc("a.c", 1)]),
            ]),
        ])
        new = _report("c", [
            _component("AES", "aes", "cipher_algorithm", [
                _func("aes_encrypt", [_loc("a.c", 1), _loc("b.c", 2)]),
            ]),
        ])

        diff = self.engine.compute(baseline, new)
        assert diff["summary"]["total_changed"] == 1
        changed = diff["changed"][0]
        assert changed["added_files"] == ["b.c"]
        assert changed["removed_files"] == []
        # Original file still counts, plus the newly added one.
        assert diff["by_file"]["a.c"]["changed"] == 1
        assert diff["by_file"]["b.c"]["changed"] == 1

    def test_baseline_has_assets_new_empty(self):
        """Baseline with assets vs. an empty new report -> all removed."""
        baseline = _report("c", [
            _component("Mbed TLS", "mbedtls", "tls_library", [
                _func("mbedtls_ssl_read", [_loc("a.c", 1)]),
                _func("mbedtls_ssl_write", [_loc("a.c", 2)]),
            ]),
        ])
        new = _report("c", [])

        diff = self.engine.compute(baseline, new)
        assert diff["summary"]["total_removed"] == 2
        assert diff["summary"]["total_added"] == 0
        assert diff["summary"]["total_changed"] == 0
        assert {a["signature"] for a in diff["removed"]} == {"mbedtls_ssl_read", "mbedtls_ssl_write"}
        assert diff["by_file"]["a.c"]["removed"] == 2

    def test_empty_result_no_changes(self):
        """Identical reports produce an empty diff across every category."""
        report = _report("c", [
            _component("Mbed TLS", "mbedtls", "tls_library", [
                _func("mbedtls_ssl_read", [_loc("a.c", 10)]),
            ]),
        ])

        diff = self.engine.compute(report, report)

        assert diff["summary"]["total_added"] == 0
        assert diff["summary"]["total_removed"] == 0
        assert diff["summary"]["total_changed"] == 0
        assert diff["added"] == []
        assert diff["removed"] == []
        assert diff["changed"] == []
        assert diff["by_file"] == {}
        assert diff["by_language"] == {}
        assert diff["by_algorithm"] == {}
        assert diff["by_risk_level"] == {}

    def test_both_empty_reports(self):
        diff = self.engine.compute({}, {})
        assert diff["summary"]["total_added"] == 0
        assert diff["summary"]["total_removed"] == 0
        assert diff["summary"]["total_changed"] == 0
        assert diff["summary"]["baseline_asset_count"] == 0
        assert diff["summary"]["new_asset_count"] == 0
