"""
Fuzzy matching engine for cryptographic function signatures.
Supports exact, prefix, substring, and Levenshtein distance matching.
"""

import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum

logger = logging.getLogger(__name__)


class MatchType(str, Enum):
    EXACT = "exact"
    PREFIX = "prefix"
    LIBRARY_PREFIX = "library_prefix"  # 新增：库级别前缀匹配
    SUBSTRING = "substring"
    FUZZY = "fuzzy"


@dataclass
class MatchResult:
    signature_pattern: str
    matched_text: str
    match_type: MatchType
    confidence: float
    file_path: str
    line_number: int
    context: str

    def to_dict(self) -> dict:
        return {
            "signature_pattern": self.signature_pattern,
            "matched_text": self.matched_text,
            "match_type": self.match_type.value,
            "confidence": round(self.confidence, 3),
            "file_path": self.file_path,
            "line_number": self.line_number,
            "context": self.context.strip(),
        }


class FuzzyMatcher:
    """
    Matches code tokens against cryptographic function signatures
    using multiple strategies with configurable thresholds.
    """

    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold

    def match_token(self, token: str, patterns: list[str]) -> list[MatchResult]:
        """Match a single token against all patterns, returning all qualifying matches."""
        results = []
        token_lower = token.lower()

        for pattern in patterns:
            pattern_lower = pattern.lower()

            # 1. 精确匹配
            if token_lower == pattern_lower:
                results.append(self._make_partial(pattern, token, MatchType.EXACT, 1.0))
                continue

            # 2. 前缀匹配（完整前缀）
            if token_lower.startswith(pattern_lower) or pattern_lower.startswith(token_lower):
                overlap = min(len(token_lower), len(pattern_lower))
                max_len = max(len(token_lower), len(pattern_lower))
                conf = overlap / max_len if max_len > 0 else 0
                if conf >= self.threshold:
                    results.append(self._make_partial(pattern, token, MatchType.PREFIX, conf))
                    continue

            # 3. 库级别前缀匹配（如 mbedtls_ssl_ 和 mbedtls_mpi_ 都属于 mbedtls_ 库）
            lib_prefix = self._extract_library_prefix(pattern_lower)
            token_lib_prefix = self._extract_library_prefix(token_lower)
            if lib_prefix and token_lib_prefix and lib_prefix == token_lib_prefix:
                # 同一库的不同模块，给予较高置信度
                conf = 0.75
                results.append(self._make_partial(pattern, token, MatchType.LIBRARY_PREFIX, conf))
                continue

            # 4. 模块前缀匹配（向后兼容）
            prefix = self._extract_prefix(pattern_lower)
            if prefix and len(prefix) >= 4 and token_lower.startswith(prefix):
                conf = len(prefix) / max(len(token_lower), len(pattern_lower))
                conf = max(conf, 0.7)
                results.append(self._make_partial(pattern, token, MatchType.PREFIX, min(conf, 0.95)))
                continue

            # 5. 子串匹配
            if len(pattern_lower) >= 6 and pattern_lower in token_lower:
                conf = len(pattern_lower) / len(token_lower)
                if conf >= self.threshold:
                    results.append(self._make_partial(pattern, token, MatchType.SUBSTRING, conf))
                    continue

            if len(token_lower) >= 6 and token_lower in pattern_lower:
                conf = len(token_lower) / len(pattern_lower)
                if conf >= self.threshold:
                    results.append(self._make_partial(pattern, token, MatchType.SUBSTRING, conf))
                    continue

            # 6. 模糊匹配（Levenshtein距离）
            if abs(len(token_lower) - len(pattern_lower)) < max(len(token_lower), len(pattern_lower)) * 0.4:
                ratio = SequenceMatcher(None, token_lower, pattern_lower).ratio()
                if ratio >= self.threshold:
                    results.append(self._make_partial(pattern, token, MatchType.FUZZY, ratio))

        return results

    def match_tokens_in_file(
        self,
        tokens_with_locations: list[tuple[str, int, str]],
        patterns: list[str],
        file_path: str,
    ) -> list[MatchResult]:
        """
        Match tokens extracted from a file against patterns.
        tokens_with_locations: list of (token, line_number, line_context)
        """
        results = []
        seen = set()

        for token, line_no, context in tokens_with_locations:
            matches = self.match_token(token, patterns)
            for m in matches:
                key = (m.signature_pattern, token, file_path, line_no)
                if key in seen:
                    continue
                seen.add(key)
                m.file_path = file_path
                m.line_number = line_no
                m.context = context
                results.append(m)

        return results

    def _extract_library_prefix(self, pattern: str) -> str:
        """
        Extract the library-level prefix (e.g., 'mbedtls_' from 'mbedtls_ssl_async_cancel_t').
        This allows matching different modules within the same library.
        Example: mbedtls_ssl_ and mbedtls_mpi_ both have library prefix 'mbedtls_'
        """
        parts = pattern.split("_")
        if len(parts) >= 2:
            return parts[0] + "_"
        return ""

    def _extract_prefix(self, pattern: str) -> str:
        """Extract the module prefix (e.g., 'mbedtls_ssl_' from 'mbedtls_ssl_async_cancel_t')."""
        parts = pattern.split("_")
        if len(parts) >= 3:
            return "_".join(parts[:2]) + "_"
        elif len(parts) == 2:
            return parts[0] + "_"
        return ""

    def _make_partial(self, pattern: str, token: str, match_type: MatchType, confidence: float) -> MatchResult:
        return MatchResult(
            signature_pattern=pattern,
            matched_text=token,
            match_type=match_type,
            confidence=confidence,
            file_path="",
            line_number=0,
            context="",
        )
