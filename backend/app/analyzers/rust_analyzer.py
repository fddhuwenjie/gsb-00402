"""
Rust source code analyzer.
Extracts use statements, function calls, macro invocations, and trait references.
"""

import re
from app.analyzers.base_analyzer import BaseAnalyzer


class RustAnalyzer(BaseAnalyzer):
    @property
    def language_name(self) -> str:
        return "Rust"

    @property
    def file_extensions(self) -> list[str]:
        return [".rs"]

    _USE_RE = re.compile(r"^\s*use\s+([\w:]+(?:::\{[^}]+\})?)\s*;")
    _FUNC_CALL_RE = re.compile(r"\b([a-zA-Z_]\w*)\s*\(")
    _PATH_CALL_RE = re.compile(r"\b([\w]+(?:::[\w]+)+)\s*\(")
    _MACRO_RE = re.compile(r"\b([a-zA-Z_]\w*)!\s*[\(\[\{]")
    _TRAIT_IMPL_RE = re.compile(r"\bimpl\s+(?:<[^>]+>\s+)?(\w+)\s+for")
    _STRUCT_RE = re.compile(r"\b(?:struct|enum)\s+(\w+)")

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

            m = self._USE_RE.match(stripped)
            if m:
                use_path = m.group(1)
                tokens.append((use_path, line_no, stripped))
                for part in re.split(r"[::{},\s]+", use_path):
                    if len(part) >= 3 and part not in _RUST_KEYWORDS:
                        tokens.append((part, line_no, stripped))
                continue

            for m in self._PATH_CALL_RE.finditer(stripped):
                full_path = m.group(1)
                tokens.append((full_path.replace("::", "_"), line_no, stripped))
                for part in full_path.split("::"):
                    if len(part) >= 3 and part not in _RUST_KEYWORDS:
                        tokens.append((part, line_no, stripped))

            for m in self._FUNC_CALL_RE.finditer(stripped):
                func = m.group(1)
                if func not in _RUST_KEYWORDS and len(func) >= 3:
                    tokens.append((func, line_no, stripped))

            for m in self._MACRO_RE.finditer(stripped):
                tokens.append((m.group(1), line_no, stripped))

            for m in self._TRAIT_IMPL_RE.finditer(stripped):
                tokens.append((m.group(1), line_no, stripped))

            for ident in self._extract_identifiers_from_line(stripped):
                if len(ident) >= 6 and ident not in _RUST_KEYWORDS and "_" in ident:
                    tokens.append((ident, line_no, stripped))

        return tokens


_RUST_KEYWORDS = {
    "as", "async", "await", "break", "const", "continue", "crate", "dyn",
    "else", "enum", "extern", "false", "fn", "for", "if", "impl", "in",
    "let", "loop", "match", "mod", "move", "mut", "pub", "ref", "return",
    "self", "Self", "static", "struct", "super", "trait", "true", "type",
    "unsafe", "use", "where", "while", "yield",
    "String", "Vec", "Option", "Result", "Box", "println", "eprintln",
    "format", "write", "writeln", "todo", "unimplemented", "unreachable",
}
