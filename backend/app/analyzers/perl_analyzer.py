"""
Perl source code analyzer.
Extracts use/require statements, function calls, and module references.
"""

import re
from app.analyzers.base_analyzer import BaseAnalyzer


class PerlAnalyzer(BaseAnalyzer):
    @property
    def language_name(self) -> str:
        return "Perl"

    @property
    def file_extensions(self) -> list[str]:
        return [".pl", ".pm", ".t"]

    _USE_RE = re.compile(r"^\s*(?:use|require)\s+([\w:]+)")
    _FUNC_CALL_RE = re.compile(r"\b([a-zA-Z_]\w*)\s*\(")
    _MODULE_CALL_RE = re.compile(r"\b([\w]+(?:::[\w]+)+)\s*(?:->|\(|;)")
    _METHOD_CALL_RE = re.compile(r"->\s*([a-zA-Z_]\w*)")
    _SUB_RE = re.compile(r"^\s*sub\s+(\w+)")

    def extract_tokens(self, file_path: str) -> list[tuple[str, int, str]]:
        lines = self._read_file(file_path)
        tokens = []

        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            m = self._USE_RE.match(stripped)
            if m:
                module = m.group(1)
                tokens.append((module, line_no, stripped))
                for part in module.split("::"):
                    if len(part) >= 3 and part not in _PERL_KEYWORDS:
                        tokens.append((part, line_no, stripped))

            for m in self._MODULE_CALL_RE.finditer(stripped):
                full_path = m.group(1)
                tokens.append((full_path.replace("::", "_"), line_no, stripped))
                for part in full_path.split("::"):
                    if len(part) >= 3 and part not in _PERL_KEYWORDS:
                        tokens.append((part, line_no, stripped))

            for m in self._FUNC_CALL_RE.finditer(stripped):
                func = m.group(1)
                if func not in _PERL_KEYWORDS and len(func) >= 3:
                    tokens.append((func, line_no, stripped))

            for m in self._METHOD_CALL_RE.finditer(stripped):
                method = m.group(1)
                if len(method) >= 3:
                    tokens.append((method, line_no, stripped))

            for m in self._SUB_RE.finditer(stripped):
                tokens.append((m.group(1), line_no, stripped))

        return tokens


_PERL_KEYWORDS = {
    "my", "our", "local", "sub", "use", "require", "package", "return",
    "if", "elsif", "else", "unless", "while", "until", "for", "foreach",
    "do", "last", "next", "redo", "die", "warn", "print", "say",
    "chomp", "chop", "push", "pop", "shift", "unshift", "splice",
    "open", "close", "read", "write", "seek", "tell", "eof",
    "defined", "undef", "ref", "bless", "new", "BEGIN", "END",
    "strict", "warnings", "vars",
}
