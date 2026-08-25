"""
Baseline diff engine.

Compares two CBOM reports (a saved baseline and a later analysis) and produces a
structured difference of cryptographic assets: added, removed and changed. Each
asset is a unique (library/algorithm, function signature) pair aggregated from
the report's components. Results are additionally classified by file, language,
algorithm name and risk level so the UI and API consumers can slice the diff.
"""

import logging

from app.core.cbom_generator import CBOMGenerator

logger = logging.getLogger(__name__)

# Fields whose change makes an asset "changed" rather than identical. "files" is
# the concrete file list: an asset that moves between files must be flagged even
# when its file count and occurrence count are unchanged.
_TRACKED_FIELDS = ("total_occurrences", "files_involved", "files", "best_confidence", "match_type", "risk_level")


class BaselineDiffEngine:
    """Computes the difference between a baseline report and a new report."""

    def __init__(self):
        # Reuse the exact deprecated-algorithm rules used to score reports so
        # per-asset risk stays consistent with the CBOM risk levels.
        self._deprecated = CBOMGenerator.DEPRECATED_INDICATORS

    def compute(self, baseline_report: dict, new_report: dict) -> dict:
        """Return a diff dict describing added/removed/changed crypto assets."""
        baseline_assets = self._extract_assets(baseline_report or {})
        new_assets = self._extract_assets(new_report or {})

        added, removed, changed = [], [], []

        for key, asset in new_assets.items():
            if key not in baseline_assets:
                added.append(asset)
            else:
                prev = baseline_assets[key]
                field_changes = self._diff_fields(prev, asset)
                if field_changes:
                    changed.append({
                        **asset,
                        "changes": field_changes,
                        "previous": {f: prev.get(f) for f in _TRACKED_FIELDS},
                        # Files present in the baseline but no longer matched.
                        "removed_files": sorted(set(prev.get("files") or []) - set(asset.get("files") or [])),
                        # Files newly matched relative to the baseline.
                        "added_files": sorted(set(asset.get("files") or []) - set(prev.get("files") or [])),
                    })

        for key, asset in baseline_assets.items():
            if key not in new_assets:
                removed.append(asset)

        # Deterministic ordering keeps stored diffs and tests stable.
        added.sort(key=lambda a: (a["algorithm"], a["signature"]))
        removed.sort(key=lambda a: (a["algorithm"], a["signature"]))
        changed.sort(key=lambda a: (a["algorithm"], a["signature"]))

        baseline_lang = (baseline_report or {}).get("metadata", {}).get("language", "")
        new_lang = (new_report or {}).get("metadata", {}).get("language", "")

        return {
            "summary": {
                "total_added": len(added),
                "total_removed": len(removed),
                "total_changed": len(changed),
                "baseline_language": baseline_lang,
                "new_language": new_lang,
                "baseline_asset_count": len(baseline_assets),
                "new_asset_count": len(new_assets),
            },
            "added": added,
            "removed": removed,
            "changed": changed,
            "by_file": self._classify_by_file(added, removed, changed),
            "by_language": self._classify_by_language(added, removed, changed),
            "by_algorithm": self._classify_by_algorithm(added, removed, changed),
            "by_risk_level": self._classify_by_risk(added, removed, changed),
        }

    def _extract_assets(self, report: dict) -> dict:
        """Flatten a CBOM report into a map of asset_key -> asset descriptor."""
        assets: dict[str, dict] = {}
        language = report.get("metadata", {}).get("language", "")
        for comp in report.get("components", []):
            algorithm = comp.get("name", comp.get("library_key", "unknown"))
            library_key = comp.get("library_key", "unknown")
            comp_type = comp.get("type", "unknown")
            for func in comp.get("functions", []):
                signature = func.get("signature", "")
                key = f"{library_key}::{signature}"
                files = sorted({loc.get("file", "") for loc in func.get("locations", [])})
                assets[key] = {
                    "key": key,
                    "algorithm": algorithm,
                    "library_key": library_key,
                    "component_type": comp_type,
                    "signature": signature,
                    "language": language,
                    "match_type": func.get("match_type", ""),
                    "best_confidence": func.get("best_confidence", 0),
                    "files": files,
                    "files_involved": len(files),
                    "total_occurrences": len(func.get("locations", [])),
                    "risk_level": self._asset_risk(signature),
                }
        return assets

    def _asset_risk(self, signature: str) -> str:
        """Classify a single asset's risk from its signature name."""
        sig_lower = signature.lower()
        if any(ind in sig_lower for ind in self._deprecated):
            return "high"
        return "info"

    def _diff_fields(self, old: dict, new: dict) -> list[dict]:
        changes = []
        for field in _TRACKED_FIELDS:
            old_val, new_val = old.get(field), new.get(field)
            if old_val != new_val:
                changes.append({"field": field, "from": old_val, "to": new_val})
        return changes

    def _empty_bucket(self) -> dict:
        return {"added": 0, "removed": 0, "changed": 0}

    def _classify(self, added, removed, changed, key_fn) -> dict:
        buckets: dict[str, dict] = {}
        for kind, items in (("added", added), ("removed", removed), ("changed", changed)):
            for asset in items:
                for group in key_fn(asset):
                    bucket = buckets.setdefault(str(group), self._empty_bucket())
                    bucket[kind] += 1
        return buckets

    def _classify_by_file(self, added, removed, changed) -> dict:
        # An asset may span multiple files; count it under each. For changed
        # assets we count the union of the original (baseline) and new files so
        # both the source and destination of a moved asset are reflected.
        def files_of(asset):
            files = set(asset.get("files") or [])
            prev = asset.get("previous")
            if prev:
                files |= set(prev.get("files") or [])
            return sorted(files) or ["(unknown)"]

        return self._classify(added, removed, changed, files_of)

    def _classify_by_language(self, added, removed, changed) -> dict:
        return self._classify(added, removed, changed, lambda a: [a.get("language") or "(unknown)"])

    def _classify_by_algorithm(self, added, removed, changed) -> dict:
        return self._classify(added, removed, changed, lambda a: [a.get("algorithm") or "(unknown)"])

    def _classify_by_risk(self, added, removed, changed) -> dict:
        return self._classify(added, removed, changed, lambda a: [a.get("risk_level") or "info"])
