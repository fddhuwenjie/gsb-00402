"""Tests for FuzzyMatcher — validates match_token and match_tokens_in_file."""

import pytest
from app.core.fuzzy_matcher import FuzzyMatcher, MatchResult, MatchType


class TestFuzzyMatcherMatchToken:
    def setup_method(self):
        self.matcher = FuzzyMatcher(threshold=0.6)

    def test_exact_match(self):
        results = self.matcher.match_token("mbedtls_ssl_read", ["mbedtls_ssl_read"])
        assert len(results) == 1
        assert results[0].match_type == MatchType.EXACT
        assert results[0].confidence == 1.0

    def test_exact_match_case_insensitive(self):
        results = self.matcher.match_token("MBEDTLS_SSL_READ", ["mbedtls_ssl_read"])
        assert len(results) == 1
        assert results[0].match_type == MatchType.EXACT

    def test_prefix_match(self):
        results = self.matcher.match_token(
            "mbedtls_ssl_async_cancel_t",
            ["mbedtls_ssl_async_cancel"],
        )
        assert len(results) >= 1
        best = max(results, key=lambda r: r.confidence)
        assert best.match_type in (MatchType.PREFIX, MatchType.EXACT)
        assert best.confidence >= 0.6

    def test_library_prefix_match_different_modules(self):
        """mbedtls_mpi_xxx matches against mbedtls_ssl_xxx via shared library prefix."""
        results = self.matcher.match_token(
            "mbedtls_mpi_read_string",
            ["mbedtls_ssl_read"],
        )
        assert len(results) >= 1
        found_types = {r.match_type for r in results}
        assert MatchType.LIBRARY_PREFIX in found_types or MatchType.PREFIX in found_types

    def test_substring_match(self):
        """Token contains the pattern as a substring with confidence above threshold."""
        results = self.matcher.match_token(
            "do_aes_encrypt",
            ["aes_encrypt"],
        )
        assert len(results) >= 1
        found_types = {r.match_type for r in results}
        assert MatchType.SUBSTRING in found_types or MatchType.FUZZY in found_types

    def test_fuzzy_match_typo(self):
        results = self.matcher.match_token(
            "mbedtls_ssl_resd",
            ["mbedtls_ssl_read"],
        )
        assert len(results) >= 1
        best = max(results, key=lambda r: r.confidence)
        assert best.confidence >= 0.6

    def test_no_match_below_threshold(self):
        results = self.matcher.match_token("completely_unrelated", ["mbedtls_ssl_read"])
        exact_or_high = [r for r in results if r.confidence >= 0.6]
        assert len(exact_or_high) == 0

    def test_multiple_patterns(self):
        results = self.matcher.match_token(
            "mbedtls_ssl_read",
            ["mbedtls_ssl_read", "mbedtls_ssl_write", "openssl_read"],
        )
        matched_sigs = {r.signature_pattern for r in results}
        assert "mbedtls_ssl_read" in matched_sigs

    def test_result_is_match_result(self):
        results = self.matcher.match_token("mbedtls_ssl_init", ["mbedtls_ssl_init"])
        assert all(isinstance(r, MatchResult) for r in results)

    def test_match_result_to_dict(self):
        results = self.matcher.match_token("mbedtls_ssl_init", ["mbedtls_ssl_init"])
        d = results[0].to_dict()
        assert "signature_pattern" in d
        assert "matched_text" in d
        assert "match_type" in d
        assert "confidence" in d

    def test_short_token_skipped(self):
        results = self.matcher.match_token("ab", ["abcdefgh"])
        high_conf = [r for r in results if r.confidence >= 0.6]
        assert len(high_conf) == 0

    def test_custom_threshold(self):
        strict = FuzzyMatcher(threshold=0.95)
        results = strict.match_token("mbedtls_ssl_resd", ["mbedtls_ssl_read"])
        high = [r for r in results if r.confidence >= 0.95]
        assert len(high) == 0


class TestFuzzyMatcherMatchTokensInFile:
    def setup_method(self):
        self.matcher = FuzzyMatcher(threshold=0.6)

    def test_match_tokens_in_file(self):
        tokens = [
            ("mbedtls_ssl_read", 10, "mbedtls_ssl_read(&ssl, buf, len);"),
            ("printf", 11, 'printf("hello");'),
            ("mbedtls_ssl_write", 12, "mbedtls_ssl_write(&ssl, data, n);"),
        ]
        patterns = ["mbedtls_ssl_read", "mbedtls_ssl_write"]
        results = self.matcher.match_tokens_in_file(tokens, patterns, "src/main.c")

        assert all(isinstance(r, MatchResult) for r in results)
        assert all(r.file_path == "src/main.c" for r in results)

        matched_sigs = {r.signature_pattern for r in results if r.match_type == MatchType.EXACT}
        assert "mbedtls_ssl_read" in matched_sigs
        assert "mbedtls_ssl_write" in matched_sigs

    def test_deduplication(self):
        tokens = [
            ("mbedtls_ssl_read", 10, "line1"),
            ("mbedtls_ssl_read", 10, "line1"),
        ]
        results = self.matcher.match_tokens_in_file(tokens, ["mbedtls_ssl_read"], "f.c")
        exact = [r for r in results if r.match_type == MatchType.EXACT]
        assert len(exact) == 1

    def test_line_number_and_context(self):
        tokens = [("mbedtls_sha256_init", 42, "mbedtls_sha256_init(ctx);")]
        results = self.matcher.match_tokens_in_file(tokens, ["mbedtls_sha256_init"], "crypto.c")
        assert results[0].line_number == 42
        assert "mbedtls_sha256_init(ctx)" in results[0].context

    def test_empty_tokens(self):
        results = self.matcher.match_tokens_in_file([], ["mbedtls_ssl_read"], "f.c")
        assert results == []

    def test_empty_patterns(self):
        tokens = [("mbedtls_ssl_read", 1, "line")]
        results = self.matcher.match_tokens_in_file(tokens, [], "f.c")
        assert results == []
