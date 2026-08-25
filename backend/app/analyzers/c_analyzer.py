"""
C/C++ source code analyzer.
Extracts function calls, declarations, includes, and macro references.
"""

import re
from app.analyzers.base_analyzer import BaseAnalyzer


class CAnalyzer(BaseAnalyzer):
    @property
    def language_name(self) -> str:
        return "C/C++"

    @property
    def file_extensions(self) -> list[str]:
        return [".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hxx", ".hh"]

    _FUNC_CALL_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
    _INCLUDE_RE = re.compile(r'#\s*include\s*[<"]([^>"]+)[>"]')
    _TYPEDEF_RE = re.compile(r"\btypedef\b.*?\b([a-zA-Z_][a-zA-Z0-9_]*)\s*;")
    _MACRO_RE = re.compile(r"#\s*define\s+([a-zA-Z_][a-zA-Z0-9_]*)")

    def extract_tokens(self, file_path: str) -> list[tuple[str, int, str]]:
        lines = self._read_file(file_path)
        tokens = []

        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue

            for m in self._FUNC_CALL_RE.finditer(line):
                func_name = m.group(1)
                if len(func_name) >= 3 and func_name not in _C_KEYWORDS:
                    tokens.append((func_name, line_no, stripped))

            for m in self._INCLUDE_RE.finditer(line):
                header = m.group(1)
                header_name = header.replace("/", "_").replace(".", "_")
                tokens.append((header_name, line_no, stripped))

            for m in self._TYPEDEF_RE.finditer(line):
                tokens.append((m.group(1), line_no, stripped))

            for m in self._MACRO_RE.finditer(line):
                tokens.append((m.group(1), line_no, stripped))

            for ident in self._extract_identifiers_from_line(line):
                if len(ident) >= 6 and ident not in _C_KEYWORDS:
                    if "_" in ident:
                        tokens.append((ident, line_no, stripped))

        return tokens


_C_KEYWORDS = {
    "auto", "break", "case", "char", "const", "continue", "default", "do",
    "double", "else", "enum", "extern", "float", "for", "goto", "if",
    "inline", "int", "long", "register", "restrict", "return", "short",
    "signed", "sizeof", "static", "struct", "switch", "typedef", "union",
    "unsigned", "void", "volatile", "while",
    "class", "namespace", "template", "typename", "virtual", "override",
    "public", "private", "protected", "throw", "catch", "try", "delete",
    "new", "nullptr", "bool", "true", "false", "using", "include",
    "define", "ifdef", "ifndef", "endif", "pragma", "string", "vector",
    "printf", "fprintf", "sprintf", "malloc", "calloc", "realloc", "free",
    "strlen", "strcpy", "strcat", "strcmp", "memcpy", "memset", "memmove",
}
