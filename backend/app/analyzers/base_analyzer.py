"""
Base analyzer interface for language-specific code analysis.
Each language analyzer extracts identifiers/tokens from source files.
"""

import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class BaseAnalyzer(ABC):
    """Abstract base class for language-specific code analyzers."""

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Human-readable language name."""
        ...

    @property
    @abstractmethod
    def file_extensions(self) -> list[str]:
        """File extensions this analyzer handles (e.g., ['.c', '.h'])."""
        ...

    _IDENTIFIER_RE = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b")

    def scan_directory(self, directory: str) -> list[tuple[str, list[tuple[str, int, str]]]]:
        """
        Scan a directory or single file for source files and extract tokens.
        Returns: list of (file_path, [(token, line_number, line_context), ...])
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"Path not found: {directory}")

        results = []
        
        # 支持单文件扫描
        if dir_path.is_file():
            # 检查文件扩展名是否匹配
            if dir_path.suffix in self.file_extensions:
                try:
                    tokens = self.extract_tokens(str(dir_path))
                    if tokens:
                        results.append((str(dir_path), tokens))
                except Exception as e:
                    logger.warning("Failed to analyze %s: %s", dir_path, e)
            else:
                logger.warning(
                    "File %s has extension %s, expected one of %s for %s analyzer",
                    dir_path, dir_path.suffix, self.file_extensions, self.language_name
                )
            logger.info("Scanned 1 file: %s for %s", directory, self.language_name)
            return results
        
        # 目录扫描
        for ext in self.file_extensions:
            for file_path in dir_path.rglob(f"*{ext}"):
                if self._should_skip(file_path):
                    continue
                try:
                    tokens = self.extract_tokens(str(file_path))
                    if tokens:
                        results.append((str(file_path), tokens))
                except Exception as e:
                    logger.warning("Failed to analyze %s: %s", file_path, e)

        logger.info("Scanned %d files in %s for %s", len(results), directory, self.language_name)
        return results

    @abstractmethod
    def extract_tokens(self, file_path: str) -> list[tuple[str, int, str]]:
        """
        Extract identifiers/tokens from a source file.
        Returns: list of (token, line_number, line_context)
        """
        ...

    def _read_file(self, file_path: str) -> list[str]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.readlines()
        except OSError as e:
            logger.warning("Cannot read %s: %s", file_path, e)
            return []

    def _extract_identifiers_from_line(self, line: str) -> list[str]:
        """Extract all C-style identifiers from a line."""
        return self._IDENTIFIER_RE.findall(line)

    def _should_skip(self, file_path: Path) -> bool:
        skip_dirs = {
            "node_modules", ".git", "__pycache__", ".venv", "venv",
            "build", "dist", "target", ".tox", ".mypy_cache",
            ".pytest_cache", "vendor", "third_party",
        }
        for part in file_path.parts:
            if part in skip_dirs:
                return True
        return False
