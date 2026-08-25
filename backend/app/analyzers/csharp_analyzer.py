"""
C# source code analyzer.
Extracts using statements, method calls, class references, and attributes.
"""

import re
from app.analyzers.base_analyzer import BaseAnalyzer


class CSharpAnalyzer(BaseAnalyzer):
    @property
    def language_name(self) -> str:
        return "C#"

    @property
    def file_extensions(self) -> list[str]:
        return [".cs"]

    _USING_RE = re.compile(r"^\s*using\s+(?:static\s+)?([\w.]+)\s*;")
    _METHOD_CALL_RE = re.compile(r"\b([a-zA-Z_]\w*)\s*\(")
    _CLASS_REF_RE = re.compile(r"\bnew\s+([A-Z]\w*)")
    _ATTRIBUTE_RE = re.compile(r"\[([A-Z]\w*)")
    _STATIC_CALL_RE = re.compile(r"\b([A-Z]\w*)\s*\.\s*([a-zA-Z_]\w*)\s*\(")
    _GENERIC_RE = re.compile(r"\b([A-Z]\w*)<")

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

            m = self._USING_RE.match(stripped)
            if m:
                namespace = m.group(1)
                tokens.append((namespace, line_no, stripped))
                for part in namespace.split("."):
                    if len(part) >= 3:
                        tokens.append((part, line_no, stripped))
                continue

            for m in self._STATIC_CALL_RE.finditer(stripped):
                cls_name = m.group(1)
                method = m.group(2)
                tokens.append((f"{cls_name}.{method}", line_no, stripped))
                tokens.append((cls_name, line_no, stripped))
                if len(method) >= 3:
                    tokens.append((method, line_no, stripped))

            for m in self._METHOD_CALL_RE.finditer(stripped):
                method = m.group(1)
                if method not in _CS_KEYWORDS and len(method) >= 3:
                    tokens.append((method, line_no, stripped))

            for m in self._CLASS_REF_RE.finditer(stripped):
                tokens.append((m.group(1), line_no, stripped))

            for m in self._ATTRIBUTE_RE.finditer(stripped):
                tokens.append((m.group(1), line_no, stripped))

            for m in self._GENERIC_RE.finditer(stripped):
                tokens.append((m.group(1), line_no, stripped))

        return tokens


_CS_KEYWORDS = {
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch",
    "char", "checked", "class", "const", "continue", "decimal", "default",
    "delegate", "do", "double", "else", "enum", "event", "explicit",
    "extern", "false", "finally", "fixed", "float", "for", "foreach",
    "goto", "if", "implicit", "in", "int", "interface", "internal",
    "is", "lock", "long", "namespace", "new", "null", "object", "operator",
    "out", "override", "params", "private", "protected", "public",
    "readonly", "ref", "return", "sbyte", "sealed", "short", "sizeof",
    "stackalloc", "static", "string", "struct", "switch", "this", "throw",
    "true", "try", "typeof", "uint", "ulong", "unchecked", "unsafe",
    "ushort", "using", "var", "virtual", "void", "volatile", "while",
    "String", "Console", "Math",
}
