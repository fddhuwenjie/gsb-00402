"""
Java source code analyzer.
Extracts import statements, method calls, class references, and annotations.
"""

import re
from app.analyzers.base_analyzer import BaseAnalyzer


class JavaAnalyzer(BaseAnalyzer):
    @property
    def language_name(self) -> str:
        return "Java"

    @property
    def file_extensions(self) -> list[str]:
        return [".java"]

    _IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+(?:\.\*)?)\s*;")
    _METHOD_CALL_RE = re.compile(r"\b([a-zA-Z_]\w*)\s*\(")
    _CLASS_REF_RE = re.compile(r"\bnew\s+([A-Z]\w*)")
    _ANNOTATION_RE = re.compile(r"@([A-Z]\w*)")
    _STATIC_CALL_RE = re.compile(r"\b([A-Z]\w*)\s*\.\s*([a-zA-Z_]\w*)\s*\(")

    def extract_tokens(self, file_path: str) -> list[tuple[str, int, str]]:
        lines = self._read_file(file_path)
        tokens = []
        in_block_comment = False

        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()

            if "/*" in stripped:
                in_block_comment = True
            if "*/" in stripped:
                in_block_comment = False
                continue
            if in_block_comment or stripped.startswith("//") or not stripped:
                continue

            m = self._IMPORT_RE.match(stripped)
            if m:
                full_import = m.group(1)
                tokens.append((full_import, line_no, stripped))
                parts = full_import.split(".")
                for part in parts:
                    if len(part) >= 3 and part != "*":
                        tokens.append((part, line_no, stripped))
                continue

            for m in self._STATIC_CALL_RE.finditer(stripped):
                cls_name = m.group(1)
                method = m.group(2)
                combined = f"{cls_name}.{method}"
                tokens.append((combined, line_no, stripped))
                tokens.append((cls_name, line_no, stripped))
                if len(method) >= 3:
                    tokens.append((method, line_no, stripped))

            for m in self._METHOD_CALL_RE.finditer(stripped):
                method = m.group(1)
                if method not in _JAVA_KEYWORDS and len(method) >= 3:
                    tokens.append((method, line_no, stripped))

            for m in self._CLASS_REF_RE.finditer(stripped):
                tokens.append((m.group(1), line_no, stripped))

            for m in self._ANNOTATION_RE.finditer(stripped):
                tokens.append((m.group(1), line_no, stripped))

            for ident in self._extract_identifiers_from_line(stripped):
                if len(ident) >= 6 and ident not in _JAVA_KEYWORDS and ("." in stripped or "_" in ident):
                    tokens.append((ident, line_no, stripped))

        return tokens


_JAVA_KEYWORDS = {
    "abstract", "assert", "boolean", "break", "byte", "case", "catch",
    "char", "class", "const", "continue", "default", "do", "double",
    "else", "enum", "extends", "final", "finally", "float", "for",
    "goto", "if", "implements", "import", "instanceof", "int", "interface",
    "long", "native", "new", "package", "private", "protected", "public",
    "return", "short", "static", "strictfp", "super", "switch",
    "synchronized", "this", "throw", "throws", "transient", "try",
    "void", "volatile", "while", "var", "record", "sealed", "permits",
    "String", "System", "Integer", "Object", "Override", "List", "Map",
}
