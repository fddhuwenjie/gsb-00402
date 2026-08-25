"""Tests for the baseline diff engine (BaselineDiffer)."""

from app.core.baseline_differ import BaselineDiffer, assess_asset_risk


def make_report(components, language="c"):
    return {
        "cbom_version": "1.0",
        "metadata": {"tool": "CBOM Analyzer", "language": language},
        "summary": {"total_matches": 0, "risk_level": "low"},
        "components": components,
    }


def make_component(name, library_key, functions, comp_type="tls_library"):
    return {
        "name": name,
        "library_key": library_key,
        "type": comp_type,
        "functions": functions,
    }


def make_function(signature, files, confidence=1.0, match_type="exact"):
    locations = []
    for i, f in enumerate(files):
        locations.append({
            "file": f,
            "line": i + 1,
            "matched_text": signature,
            "confidence": confidence,
            "context": f"{signature}();",
        })
    return {
        "signature": signature,
        "match_type": match_type,
        "best_confidence": confidence,
        "locations": locations,
    }


class TestAssessAssetRisk:
    def test_deprecated_algorithm_is_high_risk(self):
        assert assess_asset_risk("MD5_Init", 1) == "high"
        assert assess_asset_risk("mbedtls_sha1_update", 1) == "high"

    def test_occurrence_thresholds(self):
        assert assess_asset_risk("aes_encrypt", 60) == "medium"
        assert assess_asset_risk("aes_encrypt", 20) == "low"
        assert assess_asset_risk("aes_encrypt", 1) == "info"


class TestExtractAssets:
    def setup_method(self):
        self.differ = BaselineDiffer()

    def test_extract_assets_from_report(self):
        report = make_report([
            make_component("Mbed TLS", "mbedtls", [
                make_function("mbedtls_ssl_init", ["src/main.c", "src/net.c"]),
            ]),
        ])
        assets = self.differ.extract_assets(report)
        assert len(assets) == 1
        asset = assets["mbedtls:mbedtls_ssl_init"]
        assert asset["algorithm"] == "Mbed TLS"
        assert asset["language"] == "c"
        assert asset["files"] == ["src/main.c", "src/net.c"]
        assert asset["occurrences"] == 2
        assert asset["risk_level"] == "info"

    def test_extract_assets_from_empty_report(self):
        report = make_report([], language="python")
        assert self.differ.extract_assets(report) == {}

    def test_extract_assets_skips_function_without_signature(self):
        report = make_report([
            make_component("AES", "aes", [{"signature": "", "locations": []}]),
        ])
        assert self.differ.extract_assets(report) == {}


class TestDiffComputation:
    def setup_method(self):
        self.differ = BaselineDiffer()

    def _assets(self, report):
        return self.differ.extract_assets(report)

    def test_diff_added_assets(self):
        baseline = self._assets(make_report([
            make_component("AES", "aes", [make_function("aes_encrypt", ["a.c"])]),
        ]))
        current = self._assets(make_report([
            make_component("AES", "aes", [make_function("aes_encrypt", ["a.c"])]),
            make_component("RSA", "rsa", [make_function("rsa_sign", ["b.c"])]),
        ]))
        diff = self.differ.compute(baseline, current)
        assert diff["summary"]["added"] == 1
        assert diff["summary"]["removed"] == 0
        assert diff["summary"]["changed"] == 0
        assert diff["summary"]["unchanged"] == 1
        assert diff["added"][0]["signature"] == "rsa_sign"

    def test_diff_removed_assets(self):
        baseline = self._assets(make_report([
            make_component("AES", "aes", [make_function("aes_encrypt", ["a.c"])]),
            make_component("SHA Family", "sha", [make_function("sha1_digest", ["b.c"])]),
        ]))
        current = self._assets(make_report([
            make_component("AES", "aes", [make_function("aes_encrypt", ["a.c"])]),
        ]))
        diff = self.differ.compute(baseline, current)
        assert diff["summary"]["added"] == 0
        assert diff["summary"]["removed"] == 1
        assert diff["removed"][0]["signature"] == "sha1_digest"
        assert diff["removed"][0]["risk_level"] == "high"

    def test_diff_changed_attributes(self):
        baseline = self._assets(make_report([
            make_component("AES", "aes", [make_function("aes_encrypt", ["a.c"])]),
        ]))
        current = self._assets(make_report([
            make_component("AES", "aes", [
                make_function("aes_encrypt", ["a.c", "b.c", "c.c"]),
            ]),
        ]))
        diff = self.differ.compute(baseline, current)
        assert diff["summary"]["changed"] == 1
        assert diff["summary"]["unchanged"] == 0
        entry = diff["changed"][0]
        assert entry["changes"]["occurrences"] == {"before": 1, "after": 3}
        assert entry["changes"]["files"] == {"before": ["a.c"], "after": ["a.c", "b.c", "c.c"]}

    def test_diff_unchanged_when_identical(self):
        report = make_report([
            make_component("AES", "aes", [make_function("aes_encrypt", ["a.c"])]),
        ])
        diff = self.differ.compute(self._assets(report), self._assets(report))
        assert diff["summary"]["added"] == 0
        assert diff["summary"]["removed"] == 0
        assert diff["summary"]["changed"] == 0
        assert diff["summary"]["unchanged"] == 1
        assert diff["summary"]["total_changes"] == 0

    def test_diff_grouped_classification(self):
        baseline = self._assets(make_report([]))
        current = self._assets(make_report([
            make_component("SHA Family", "sha", [
                make_function("sha1_digest", ["src/hash.c", "src/util.c"]),
            ]),
            make_component("AES", "aes", [make_function("aes_encrypt", ["src/hash.c"])]),
        ]))
        diff = self.differ.compute(baseline, current)
        grouped = diff["grouped"]

        assert grouped["by_file"]["src/hash.c"]["added"] == 2
        assert grouped["by_file"]["src/util.c"]["added"] == 1
        assert grouped["by_language"]["c"]["added"] == 2
        assert grouped["by_algorithm"]["SHA Family"]["added"] == 1
        assert grouped["by_algorithm"]["AES"]["added"] == 1
        assert grouped["by_risk"]["high"]["added"] == 1
        assert grouped["by_risk"]["info"]["added"] == 1


class TestDiffEdgeCases:
    def setup_method(self):
        self.differ = BaselineDiffer()

    def test_diff_with_no_baseline_snapshot(self):
        """无基线（空快照）时，当前所有资产都计为新增。"""
        current = self.differ.extract_assets(make_report([
            make_component("AES", "aes", [make_function("aes_encrypt", ["a.c"])]),
            make_component("RSA", "rsa", [make_function("rsa_sign", ["b.c"])]),
        ]))
        diff = self.differ.compute({}, current)
        assert diff["summary"]["added"] == 2
        assert diff["summary"]["removed"] == 0
        assert diff["summary"]["changed"] == 0
        assert diff["summary"]["unchanged"] == 0
        assert diff["summary"]["total_changes"] == 2
        assert diff["grouped"]["by_algorithm"]["AES"]["added"] == 1
        assert diff["grouped"]["by_algorithm"]["RSA"]["added"] == 1

    def test_diff_with_empty_current_report(self):
        """当前分析无结果（空报告）时，基线所有资产都计为移除。"""
        baseline = self.differ.extract_assets(make_report([
            make_component("AES", "aes", [make_function("aes_encrypt", ["a.c"])]),
        ]))
        current = self.differ.extract_assets(make_report([]))
        diff = self.differ.compute(baseline, current)
        assert diff["summary"]["added"] == 0
        assert diff["summary"]["removed"] == 1
        assert diff["summary"]["changed"] == 0
        assert diff["summary"]["total_changes"] == 1

    def test_diff_both_empty(self):
        """基线与当前均为空时，差异为空。"""
        diff = self.differ.compute({}, {})
        assert diff["summary"]["added"] == 0
        assert diff["summary"]["removed"] == 0
        assert diff["summary"]["changed"] == 0
        assert diff["summary"]["unchanged"] == 0
        assert diff["summary"]["total_changes"] == 0
        assert diff["grouped"]["by_file"] == {}
        assert diff["grouped"]["by_language"] == {}
        assert diff["grouped"]["by_algorithm"] == {}
        assert diff["grouped"]["by_risk"] == {}
