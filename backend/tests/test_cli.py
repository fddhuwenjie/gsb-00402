"""Tests for CLI — validates end-to-end command-line analysis."""

import json
import subprocess
import sys
import pytest
from pathlib import Path


CLI_PATH = Path(__file__).parent.parent / "cli.py"

SAMPLE_YARA = """
rule Func_test
{
    meta:
        description = "Test sigs"
    strings:
        $f1 = "mbedtls_ssl_read"
        $f2 = "mbedtls_ssl_write"
}
"""

SAMPLE_C = """
#include "mbedtls/ssl.h"

void do_stuff() {
    mbedtls_ssl_read(&ctx, buf, len);
    mbedtls_ssl_write(&ctx, data, n);
}
"""


@pytest.fixture
def cli_env(tmp_path):
    yar = tmp_path / "test.yar"
    yar.write_text(SAMPLE_YARA)

    src_dir = tmp_path / "code"
    src_dir.mkdir()
    (src_dir / "main.c").write_text(SAMPLE_C)

    return yar, src_dir


class TestCli:
    def _run(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(CLI_PATH), *args],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_json_output(self, cli_env):
        yar, src_dir = cli_env
        result = self._run("-y", str(yar), "-c", str(src_dir), "-l", "c")
        assert result.returncode == 0
        report = json.loads(result.stdout)
        assert "cbom_version" in report
        assert "summary" in report
        assert "components" in report
        assert report["summary"]["total_crypto_components"] >= 0

    def test_summary_mode(self, cli_env):
        yar, src_dir = cli_env
        result = self._run("-y", str(yar), "-c", str(src_dir), "-l", "c", "--summary")
        assert result.returncode == 0
        assert "CBOM" in result.stdout
        assert "密码组件数" in result.stdout

    def test_output_to_file(self, cli_env, tmp_path):
        yar, src_dir = cli_env
        out = tmp_path / "report.json"
        result = self._run("-y", str(yar), "-c", str(src_dir), "-l", "c", "-o", str(out))
        assert result.returncode == 0
        assert out.exists()
        report = json.loads(out.read_text())
        assert report["cbom_version"] == "1.0"

    def test_verbose(self, cli_env):
        yar, src_dir = cli_env
        result = self._run("-y", str(yar), "-c", str(src_dir), "-l", "c", "-v")
        assert result.returncode == 0
        assert "[INFO]" in result.stderr

    def test_bad_yara_path(self, tmp_path):
        src = tmp_path / "code"
        src.mkdir()
        result = self._run("-y", "/nonexistent.yar", "-c", str(src), "-l", "c")
        assert result.returncode == 2

    def test_bad_code_path(self, tmp_path):
        yar = tmp_path / "test.yar"
        yar.write_text(SAMPLE_YARA)
        result = self._run("-y", str(yar), "-c", "/nonexistent/path", "-l", "c")
        assert result.returncode == 2

    def test_version(self):
        result = self._run("--version")
        assert "1.0.0" in result.stdout

    def test_custom_threshold(self, cli_env):
        yar, src_dir = cli_env
        result = self._run("-y", str(yar), "-c", str(src_dir), "-l", "c", "-t", "0.9")
        assert result.returncode == 0
