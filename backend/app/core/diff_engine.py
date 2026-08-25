"""
Baseline diff engine.

Compares two CBOM analysis reports at the crypto-asset granularity
(file + algorithm + function signature) and produces added / removed /
changed assets, categorized by file, language, algorithm and risk level.

Pure Python, no database access — safe to unit-test in isolation.
"""

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

CHANGE_ADDED = "added"
CHANGE_REMOVED = "removed"
CHANGE_CHANGED = "changed"

CHANGE_TYPES = (CHANGE_ADDED, CHANGE_REMOVED, CHANGE_CHANGED)

# Attributes that, when different between baseline and current, mark an asset as "changed".
COMPARED_FIELDS = ("occurrences", "lines", "confidence", "match_type", "risk_level")

# Substrings indicating weak/deprecated cryptography (mirrors CBOMGenerator risk logic).
DEPRECATED_INDICATORS = ("md5", "sha1", "md2", "md4", "rc4", "des")

RISK_RANK = {"none": 0, "info": 1, "low": 2, "medium": 3, "high": 4}


class DiffEngine:
    """Extracts crypto assets from CBOM reports and computes baseline diffs."""

    def __init__(self, deprecated_indicators: tuple[str, ...] = DEPRECATED_INDICATORS):
        self.deprecated_indicators = deprecated_indicators

    def asset_risk_level(self, signature: str) -> str:
        sig_lower = signature.lower()
        if any(ind in sig_lower for ind in self.deprecated_indicators):
            return "high"
        return "info"

    def extract_assets(self, report: dict | None) -> list[dict]:
        """Flatten a CBOM report into a list of crypto-asset dicts.

        One asset == one (file, algorithm/library, function signature) tuple,
        aggregating all call-site locations of that function in that file.
        Returns an empty list when the report is None or has no components.
        """
        if not report:
            return []

        language = (report.get("metadata") or {}).get("language", "unknown")
        assets: dict[str, dict] = {}

        for comp in report.get("components", []) or []:
            library_key = comp.get("library_key") or comp.get("name", "unknown")
            algorithm_name = comp.get("name", library_key)

            for func in comp.get("functions", []) or []:
                signature = func.get("signature", "")
                match_type = func.get("match_type", "unknown")
                confidence = round(float(func.get("best_confidence", 0.0)), 3)
                risk_level = self.asset_risk_level(signature)

                for loc in func.get("locations", []) or []:
                    file_path = loc.get("file", "unknown")
                    line = int(loc.get("line", 0))
                    key = self._asset_key(file_path, library_key, signature)

                    if key not in assets:
                        assets[key] = {
                            "key": key,
                            "file": file_path,
                            "language": language,
                            "algorithm": library_key,
                            "algorithm_name": algorithm_name,
                            "signature": signature,
                            "match_type": match_type,
                            "confidence": confidence,
                            "occurrences": 0,
                            "lines": [],
                            "risk_level": risk_level,
                        }

                    asset = assets[key]
                    asset["occurrences"] += 1
                    if line and line not in asset["lines"]:
                        asset["lines"].append(line)
                    loc_conf = loc.get("confidence")
                    if loc_conf is not None and round(float(loc_conf), 3) > asset["confidence"]:
                        asset["confidence"] = round(float(loc_conf), 3)
                    asset["risk_level"] = self._max_risk(asset["risk_level"], risk_level)

        result = list(assets.values())
        for asset in result:
            asset["lines"].sort()
        result.sort(key=self._sort_key)
        return result

    def compute_diff(
        self,
        baseline_assets: list[dict] | None,
        current_assets: list[dict] | None,
        baseline_meta: dict | None = None,
        current_meta: dict | None = None,
    ) -> dict:
        """Compute the diff between baseline assets and current assets.

        ``baseline_assets`` may be None/empty (no baseline): every current
        asset is reported as added.
        """
        baseline_map = {a["key"]: a for a in (baseline_assets or [])}
        current_map = {a["key"]: a for a in (current_assets or [])}

        added: list[dict] = []
        removed: list[dict] = []
        changed: list[dict] = []
        unchanged_count = 0

        for key, cur in current_map.items():
            if key not in baseline_map:
                added.append(cur)
            else:
                base = baseline_map[key]
                changed_fields = [
                    field for field in COMPARED_FIELDS
                    if not self._field_equal(field, base, cur)
                ]
                if changed_fields:
                    changed.append({
                        "key": key,
                        "baseline": base,
                        "current": cur,
                        "changed_fields": changed_fields,
                    })
                else:
                    unchanged_count += 1

        for key, base in baseline_map.items():
            if key not in current_map:
                removed.append(base)

        added.sort(key=self._sort_key)
        removed.sort(key=self._sort_key)
        changed.sort(key=lambda c: self._sort_key(c["current"]))

        diff_risk = self._diff_risk_level(added, removed, changed)

        return {
            "baseline": baseline_meta or {},
            "current": current_meta or {},
            "summary": {
                "baseline_asset_count": len(baseline_map),
                "current_asset_count": len(current_map),
                "added": len(added),
                "removed": len(removed),
                "changed": len(changed),
                "unchanged": unchanged_count,
                "risk_level": diff_risk,
            },
            "added": added,
            "removed": removed,
            "changed": changed,
            "categories": self._build_categories(added, removed, changed),
        }

    @staticmethod
    def _asset_key(file_path: str, algorithm: str, signature: str) -> str:
        return f"{file_path}::{algorithm}::{signature}"

    @staticmethod
    def _field_equal(field: str, base: dict, cur: dict) -> bool:
        if field == "lines":
            return sorted(base.get("lines", [])) == sorted(cur.get("lines", []))
        if field == "confidence":
            return round(float(base.get("confidence", 0.0)), 3) == round(float(cur.get("confidence", 0.0)), 3)
        return base.get(field) == cur.get(field)

    @staticmethod
    def _max_risk(a: str, b: str) -> str:
        return a if RISK_RANK.get(a, 0) >= RISK_RANK.get(b, 0) else b

    @staticmethod
    def _sort_key(asset: dict) -> tuple:
        return (
            -RISK_RANK.get(asset.get("risk_level", "none"), 0),
            asset.get("file", ""),
            asset.get("algorithm", ""),
            asset.get("signature", ""),
        )

    def _diff_risk_level(self, added: list[dict], removed: list[dict], changed: list[dict]) -> str:
        if not added and not removed and not changed:
            return "none"
        high_scopes = added + [c["current"] for c in changed]
        if any(a.get("risk_level") == "high" for a in high_scopes):
            return "high"
        return "medium"

    def _build_categories(self, added: list[dict], removed: list[dict], changed: list[dict]) -> dict:
        def empty_bucket():
            return {CHANGE_ADDED: 0, CHANGE_REMOVED: 0, CHANGE_CHANGED: 0, "total": 0}

        by_file: dict[str, dict] = defaultdict(empty_bucket)
        by_language: dict[str, dict] = defaultdict(empty_bucket)
        by_algorithm: dict[str, dict] = defaultdict(empty_bucket)
        by_risk: dict[str, dict] = defaultdict(empty_bucket)

        def bump(buckets: dict, name: str, change_type: str):
            bucket = buckets[name]
            bucket[change_type] += 1
            bucket["total"] += 1

        for asset in added:
            bump(by_file, asset["file"], CHANGE_ADDED)
            bump(by_language, asset["language"], CHANGE_ADDED)
            bump(by_algorithm, asset["algorithm_name"], CHANGE_ADDED)
            bump(by_risk, asset["risk_level"], CHANGE_ADDED)

        for asset in removed:
            bump(by_file, asset["file"], CHANGE_REMOVED)
            bump(by_language, asset["language"], CHANGE_REMOVED)
            bump(by_algorithm, asset["algorithm_name"], CHANGE_REMOVED)
            bump(by_risk, asset["risk_level"], CHANGE_REMOVED)

        for change in changed:
            asset = change["current"]
            bump(by_file, asset["file"], CHANGE_CHANGED)
            bump(by_language, asset["language"], CHANGE_CHANGED)
            bump(by_algorithm, asset["algorithm_name"], CHANGE_CHANGED)
            bump(by_risk, asset["risk_level"], CHANGE_CHANGED)

        return {
            "by_file": dict(sorted(by_file.items())),
            "by_language": dict(sorted(by_language.items())),
            "by_algorithm": dict(sorted(by_algorithm.items())),
            "by_risk_level": dict(sorted(by_risk.items())),
        }
