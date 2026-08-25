"""
Baseline diff engine for CBOM reports.
Extracts crypto assets from a CBOM report and computes added / removed /
attribute-changed assets between a baseline snapshot and a current report.
Pure functions, no database access.
"""

import logging

logger = logging.getLogger(__name__)

# Mirrors CBOMGenerator._assess_risk deprecated indicators
DEPRECATED_INDICATORS = {"des", "md5", "rc4", "md2", "md4", "sha1"}

# Attributes compared to detect property changes
COMPARED_ATTRS = ("risk_level", "occurrences", "files", "best_confidence", "type")


def assess_asset_risk(signature: str, occurrences: int) -> str:
    """Per-asset risk level, consistent with CBOMGenerator rules."""
    sig_lower = signature.lower()
    if any(ind in sig_lower for ind in DEPRECATED_INDICATORS):
        return "high"
    if occurrences > 50:
        return "medium"
    if occurrences > 10:
        return "low"
    return "info"


class BaselineDiffer:
    """Extracts crypto assets from CBOM reports and diffs two asset sets."""

    @staticmethod
    def extract_assets(report: dict) -> dict:
        """
        Flatten a CBOM report into crypto assets keyed by "library_key:signature".
        Each asset carries file / language / algorithm / risk classification data.
        """
        language = (report.get("metadata") or {}).get("language", "")
        assets = {}
        for comp in report.get("components") or []:
            algorithm = comp.get("name", "")
            library_key = comp.get("library_key", "")
            comp_type = comp.get("type", "unknown")
            for func in comp.get("functions") or []:
                signature = func.get("signature", "")
                if not signature:
                    continue
                locations = func.get("locations") or []
                files = sorted({loc.get("file", "") for loc in locations if loc.get("file")})
                occurrences = len(locations)
                key = f"{library_key}:{signature}"
                assets[key] = {
                    "key": key,
                    "algorithm": algorithm,
                    "library_key": library_key,
                    "signature": signature,
                    "type": comp_type,
                    "language": language,
                    "files": files,
                    "occurrences": occurrences,
                    "best_confidence": func.get("best_confidence", 0.0),
                    "risk_level": assess_asset_risk(signature, occurrences),
                }
        return assets

    @classmethod
    def compute(cls, baseline_assets: dict, current_assets: dict) -> dict:
        """
        Compute the diff between a baseline asset snapshot and current assets.
        Returns added / removed / changed entries plus grouped classifications
        by file, language, algorithm name and risk level.
        """
        added, removed, changed = [], [], []
        unchanged = 0

        for key, asset in sorted(current_assets.items()):
            if key not in baseline_assets:
                added.append(asset)
                continue
            old = baseline_assets[key]
            attr_changes = {}
            for attr in COMPARED_ATTRS:
                if old.get(attr) != asset.get(attr):
                    attr_changes[attr] = {"before": old.get(attr), "after": asset.get(attr)}
            if attr_changes:
                changed.append({
                    "key": key,
                    "algorithm": asset["algorithm"],
                    "signature": asset["signature"],
                    "language": asset["language"],
                    "files": asset["files"],
                    "risk_level": asset["risk_level"],
                    "changes": attr_changes,
                })
            else:
                unchanged += 1

        for key, asset in sorted(baseline_assets.items()):
            if key not in current_assets:
                removed.append(asset)

        entries = (
            [("added", a) for a in added]
            + [("removed", r) for r in removed]
            + [("changed", c) for c in changed]
        )

        return {
            "summary": {
                "added": len(added),
                "removed": len(removed),
                "changed": len(changed),
                "unchanged": unchanged,
                "total_changes": len(added) + len(removed) + len(changed),
            },
            "added": added,
            "removed": removed,
            "changed": changed,
            "grouped": cls._group(entries),
        }

    @staticmethod
    def _group(entries: list) -> dict:
        """Classify diff entries by file, language, algorithm name and risk level."""
        by_file, by_language, by_algorithm, by_risk = {}, {}, {}, {}

        def _bump(bucket: dict, name: str, change_type: str):
            group = bucket.setdefault(name, {"added": 0, "removed": 0, "changed": 0, "total": 0})
            group[change_type] += 1
            group["total"] += 1

        for change_type, entry in entries:
            files = entry.get("files") or ["(unknown)"]
            for f in files:
                _bump(by_file, f, change_type)
            _bump(by_language, entry.get("language") or "(unknown)", change_type)
            _bump(by_algorithm, entry.get("algorithm") or "(unknown)", change_type)
            _bump(by_risk, entry.get("risk_level") or "(unknown)", change_type)

        return {
            "by_file": by_file,
            "by_language": by_language,
            "by_algorithm": by_algorithm,
            "by_risk": by_risk,
        }
