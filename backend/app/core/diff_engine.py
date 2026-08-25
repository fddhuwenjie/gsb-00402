"""
Diff engine for comparing CBOM analysis results against a saved baseline.

A "crypto asset" is the usage of a cryptographic function (signature) from a
known algorithm/library within a single source file. Assets are keyed by
``(library_key, signature, file)`` so that a function moving between files is
reported as a removal + addition rather than a property change.
"""

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


DEPRECATED_INDICATORS = ("des", "md5", "rc4", "md2", "md4", "sha1")

CHANGEABLE_FIELDS = ("match_type", "confidence", "occurrences", "risk_level", "lines")


class DiffEngine:
    """Computes added / removed / changed crypto assets between two CBOM reports."""

    def extract_assets(self, report: dict[str, Any]) -> list[dict[str, Any]]:
        """Flatten a CBOM report into a list of per-file crypto asset records."""
        assets: list[dict[str, Any]] = []
        language = (report.get("metadata") or {}).get("language", "")

        for comp in report.get("components", []) or []:
            library_key = comp.get("library_key") or comp.get("name", "unknown")
            algorithm_name = comp.get("name", library_key)
            component_type = comp.get("type", "unknown")

            for func in comp.get("functions", []) or []:
                signature = func.get("signature", "")
                match_type = func.get("match_type", "unknown")
                best_confidence = round(float(func.get("best_confidence", 0.0)), 3)
                risk_level = self._assess_asset_risk(signature)

                file_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
                for loc in func.get("locations", []) or []:
                    file_path = loc.get("file", "")
                    file_groups[file_path].append(loc)

                for file_path, locations in file_groups.items():
                    lines = sorted({int(loc.get("line", 0)) for loc in locations})
                    file_confidence = max(
                        (round(float(loc.get("confidence", best_confidence)), 3) for loc in locations),
                        default=best_confidence,
                    )
                    asset = {
                        "library_key": library_key,
                        "algorithm_name": algorithm_name,
                        "component_type": component_type,
                        "signature": signature,
                        "file": file_path,
                        "language": language,
                        "match_type": match_type,
                        "confidence": file_confidence,
                        "occurrences": len(locations),
                        "lines": lines,
                        "risk_level": risk_level,
                    }
                    asset["key"] = self.asset_key(asset)
                    assets.append(asset)

        return assets

    @staticmethod
    def asset_key(asset: dict[str, Any]) -> str:
        return f"{asset.get('library_key', '')}::{asset.get('signature', '')}::{asset.get('file', '')}"

    def compute_diff(
        self,
        baseline_report: dict[str, Any] | None,
        current_report: dict[str, Any],
        baseline_meta: dict[str, Any] | None = None,
        current_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Compute the diff between a baseline report and the current report."""
        baseline_assets = self._index_assets(baseline_report)
        current_assets = self._index_assets(current_report)

        added: list[dict[str, Any]] = []
        removed: list[dict[str, Any]] = []
        changed: list[dict[str, Any]] = []
        unchanged: list[dict[str, Any]] = []

        for key, cur in current_assets.items():
            if key not in baseline_assets:
                added.append(cur)
            else:
                base = baseline_assets[key]
                changed_fields = self._diff_attributes(base, cur)
                if changed_fields:
                    changed.append({
                        "before": base,
                        "after": cur,
                        "changed_fields": changed_fields,
                    })
                else:
                    unchanged.append(cur)

        for key, base in baseline_assets.items():
            if key not in current_assets:
                removed.append(base)

        added.sort(key=lambda a: (a["file"], a["signature"]))
        removed.sort(key=lambda a: (a["file"], a["signature"]))
        changed.sort(key=lambda c: (c["after"]["file"], c["after"]["signature"]))
        unchanged.sort(key=lambda a: (a["file"], a["signature"]))

        diff_risk = self._assess_diff_risk(added, changed)

        diff = {
            "baseline": baseline_meta or {},
            "current": current_meta or {},
            "summary": {
                "total_baseline_assets": len(baseline_assets),
                "total_current_assets": len(current_assets),
                "added": len(added),
                "removed": len(removed),
                "changed": len(changed),
                "unchanged": len(unchanged),
                "risk_level": diff_risk,
            },
            "added": added,
            "removed": removed,
            "changed": changed,
            "unchanged": unchanged,
            "classified": self._classify(added, removed, changed),
        }
        return diff

    def _index_assets(self, report: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        if not report:
            return {}
        assets = self.extract_assets(report)
        return {a["key"]: a for a in assets}

    @staticmethod
    def _diff_attributes(base: dict[str, Any], cur: dict[str, Any]) -> list[str]:
        changed_fields: list[str] = []
        for field in CHANGEABLE_FIELDS:
            if field == "lines":
                if set(base.get("lines", [])) != set(cur.get("lines", [])):
                    changed_fields.append("lines")
            elif base.get(field) != cur.get(field):
                changed_fields.append(field)
        return changed_fields

    @staticmethod
    def _assess_asset_risk(signature: str) -> str:
        sig_lower = (signature or "").lower()
        if any(ind in sig_lower for ind in DEPRECATED_INDICATORS):
            return "high"
        return "info"

    @staticmethod
    def _assess_diff_risk(added: list[dict], changed: list[dict]) -> str:
        high_present = any(a.get("risk_level") == "high" for a in added)
        high_present = high_present or any(
            c["after"].get("risk_level") == "high" for c in changed
        )
        if high_present:
            return "high"

        change_count = len(added) + len(changed)
        if change_count == 0:
            return "none"
        if change_count > 10:
            return "medium"
        return "low"

    def _classify(
        self,
        added: list[dict[str, Any]],
        removed: list[dict[str, Any]],
        changed: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "by_file": self._classify_by_key(added, removed, changed, "file"),
            "by_language": self._classify_by_key(added, removed, changed, "language"),
            "by_algorithm": self._classify_by_key(added, removed, changed, "algorithm_name"),
            "by_risk": self._classify_by_risk(added, removed, changed),
        }

    @staticmethod
    def _classify_by_key(
        added: list[dict],
        removed: list[dict],
        changed: list[dict],
        key: str,
    ) -> dict[str, dict[str, list]]:
        buckets: dict[str, dict[str, list]] = defaultdict(lambda: {"added": [], "removed": [], "changed": []})
        for asset in added:
            buckets[asset.get(key, "") or "(unknown)"]["added"].append(asset)
        for asset in removed:
            buckets[asset.get(key, "") or "(unknown)"]["removed"].append(asset)
        for change in changed:
            buckets[change["after"].get(key, "") or "(unknown)"]["changed"].append(change)
        return dict(buckets)

    @staticmethod
    def _classify_by_risk(
        added: list[dict],
        removed: list[dict],
        changed: list[dict],
    ) -> dict[str, dict[str, list]]:
        order = ("high", "medium", "low", "info", "none")
        buckets: dict[str, dict[str, list]] = {
            level: {"added": [], "removed": [], "changed": []} for level in order
        }
        for asset in added:
            buckets.setdefault(asset.get("risk_level", "info"), {"added": [], "removed": [], "changed": []})
            buckets[asset.get("risk_level", "info")]["added"].append(asset)
        for asset in removed:
            level = asset.get("risk_level", "info")
            buckets.setdefault(level, {"added": [], "removed": [], "changed": []})
            buckets[level]["removed"].append(asset)
        for change in changed:
            level = change["after"].get("risk_level", "info")
            buckets.setdefault(level, {"added": [], "removed": [], "changed": []})
            buckets[level]["changed"].append(change)
        return buckets
