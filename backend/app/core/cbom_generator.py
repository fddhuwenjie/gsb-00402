"""
CBOM (Cryptographic Bill of Materials) report generator.
Aggregates analysis results into a standardized JSON report.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone

from app.core.fuzzy_matcher import MatchResult

logger = logging.getLogger(__name__)


class CBOMGenerator:
    """Generates CBOM reports from analysis match results."""

    KNOWN_LIBRARIES = {
        "mbedtls": {"name": "Mbed TLS", "type": "tls_library"},
        "openssl": {"name": "OpenSSL", "type": "tls_library"},
        "wolfssl": {"name": "wolfSSL", "type": "tls_library"},
        "botan": {"name": "Botan", "type": "crypto_library"},
        "libsodium": {"name": "libsodium", "type": "crypto_library"},
        "sodium": {"name": "libsodium", "type": "crypto_library"},
        "crypto": {"name": "Crypto (generic)", "type": "crypto_library"},
        "gcrypt": {"name": "Libgcrypt", "type": "crypto_library"},
        "gnutls": {"name": "GnuTLS", "type": "tls_library"},
        "nss": {"name": "NSS", "type": "tls_library"},
        "bcrypt": {"name": "bcrypt", "type": "hash_library"},
        "argon2": {"name": "Argon2", "type": "hash_library"},
        "sha": {"name": "SHA Family", "type": "hash_algorithm"},
        "aes": {"name": "AES", "type": "cipher_algorithm"},
        "rsa": {"name": "RSA", "type": "asymmetric_algorithm"},
        "ecdsa": {"name": "ECDSA", "type": "signature_algorithm"},
        "hmac": {"name": "HMAC", "type": "mac_algorithm"},
        "chacha": {"name": "ChaCha20", "type": "cipher_algorithm"},
        "poly1305": {"name": "Poly1305", "type": "mac_algorithm"},
        "ed25519": {"name": "Ed25519", "type": "signature_algorithm"},
        "x25519": {"name": "X25519", "type": "key_exchange"},
        "dh": {"name": "Diffie-Hellman", "type": "key_exchange"},
        "ecdh": {"name": "ECDH", "type": "key_exchange"},
        "pem": {"name": "PEM", "type": "encoding"},
        "asn1": {"name": "ASN.1", "type": "encoding"},
        "pkcs": {"name": "PKCS", "type": "standard"},
    }

    def generate(
        self,
        matches: list[MatchResult],
        target_path: str,
        language: str,
        signature_files: list[str],
        total_files_scanned: int,
        scan_duration: float,
    ) -> dict:
        components = self._aggregate_components(matches)
        total_matches = len(matches)
        risk_level = self._assess_risk(components, total_matches)

        report = {
            "cbom_version": "1.0",
            "metadata": {
                "tool": "CBOM Analyzer",
                "tool_version": "1.0.0",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "target_path": target_path,
                "language": language,
                "signature_files": signature_files,
            },
            "summary": {
                "total_files_scanned": total_files_scanned,
                "total_matches": total_matches,
                "total_crypto_components": len(components),
                "risk_level": risk_level,
                "scan_duration_seconds": round(scan_duration, 3),
            },
            "components": components,
        }

        return report

    def _aggregate_components(self, matches: list[MatchResult]) -> list[dict]:
        lib_groups: dict[str, list[MatchResult]] = defaultdict(list)

        for match in matches:
            lib_key = self._identify_library(match.signature_pattern)
            lib_groups[lib_key].append(match)

        components = []
        for lib_key, lib_matches in lib_groups.items():
            lib_info = self.KNOWN_LIBRARIES.get(lib_key, {"name": lib_key, "type": "unknown"})

            func_map: dict[str, dict] = {}
            for m in lib_matches:
                sig = m.signature_pattern
                if sig not in func_map:
                    func_map[sig] = {
                        "signature": sig,
                        "match_type": m.match_type.value,
                        "best_confidence": m.confidence,
                        "locations": [],
                    }
                else:
                    if m.confidence > func_map[sig]["best_confidence"]:
                        func_map[sig]["best_confidence"] = m.confidence
                        func_map[sig]["match_type"] = m.match_type.value

                func_map[sig]["locations"].append({
                    "file": m.file_path,
                    "line": m.line_number,
                    "matched_text": m.matched_text,
                    "confidence": round(m.confidence, 3),
                    "context": m.context.strip(),
                })

            functions = list(func_map.values())
            for f in functions:
                f["best_confidence"] = round(f["best_confidence"], 3)

            files_involved = set()
            for m in lib_matches:
                files_involved.add(m.file_path)

            component = {
                "name": lib_info["name"],
                "library_key": lib_key,
                "type": lib_info["type"],
                "version": "unknown",
                "total_function_matches": len(functions),
                "total_occurrences": len(lib_matches),
                "files_involved": len(files_involved),
                "functions": functions,
            }
            components.append(component)

        components.sort(key=lambda c: c["total_occurrences"], reverse=True)
        return components

    def _identify_library(self, pattern: str) -> str:
        pattern_lower = pattern.lower()
        for key in self.KNOWN_LIBRARIES:
            if key in pattern_lower:
                return key
        parts = pattern_lower.split("_")
        return parts[0] if parts else "unknown"

    def _assess_risk(self, components: list[dict], total_matches: int) -> str:
        if total_matches == 0:
            return "none"

        deprecated_indicators = {"des", "md5", "rc4", "md2", "md4", "sha1"}
        has_deprecated = False
        for comp in components:
            for func in comp.get("functions", []):
                sig_lower = func["signature"].lower()
                if any(ind in sig_lower for ind in deprecated_indicators):
                    has_deprecated = True
                    break

        if has_deprecated:
            return "high"
        elif total_matches > 50:
            return "medium"
        elif total_matches > 10:
            return "low"
        return "info"

    @staticmethod
    def to_json(report: dict, indent: int = 2) -> str:
        return json.dumps(report, indent=indent, ensure_ascii=False)
