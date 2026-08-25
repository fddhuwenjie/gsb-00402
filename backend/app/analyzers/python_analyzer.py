"""
Python source code analyzer.
Extracts import statements, function calls, and decorator references.
Supports both AST parsing (preferred) and regex fallback.
"""

import ast
import logging
import re
from app.analyzers.base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)


class PythonAnalyzer(BaseAnalyzer):
    @property
    def language_name(self) -> str:
        return "Python"

    @property
    def file_extensions(self) -> list[str]:
        return [".py"]

    _IMPORT_RE = re.compile(r"^\s*import\s+([\w.]+(?:\s*,\s*[\w.]+)*)")
    _FROM_IMPORT_RE = re.compile(r"^\s*from\s+([\w.]+)\s+import\s+(.+)")
    _FUNC_CALL_RE = re.compile(r"\b([a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*)*)\s*\(")
    _DECORATOR_RE = re.compile(r"^\s*@([a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*)*)")

    def extract_tokens(self, file_path: str) -> list[tuple[str, int, str]]:
        """
        Extract tokens using AST parsing (preferred) with regex fallback.
        AST provides more accurate results for complex code structures.
        """
        lines = self._read_file(file_path)
        source = "".join(lines)
        
        # 尝试使用AST解析（更精确）
        try:
            tokens = self._extract_tokens_ast(source, lines)
            if tokens:
                logger.debug("Used AST parser for %s", file_path)
                return tokens
        except SyntaxError as e:
            logger.debug("AST parse failed for %s: %s, falling back to regex", file_path, e)
        except Exception as e:
            logger.debug("AST parse error for %s: %s, falling back to regex", file_path, e)
        
        # 回退到正则表达式解析
        return self._extract_tokens_regex(lines)

    def _extract_tokens_ast(self, source: str, lines: list[str]) -> list[tuple[str, int, str]]:
        """使用AST解析提取tokens（更精确，能处理跨行调用和嵌套结构）"""
        tree = ast.parse(source)
        tokens = []
        
        for node in ast.walk(tree):
            # 处理import语句
            if isinstance(node, ast.Import):
                for alias in node.names:
                    line_no = node.lineno
                    context = lines[line_no - 1].strip() if line_no <= len(lines) else ""
                    tokens.append((alias.name, line_no, context))
                    # 拆分模块路径
                    for part in alias.name.split("."):
                        if len(part) >= 3:
                            tokens.append((part, line_no, context))
            
            # 处理from ... import语句
            elif isinstance(node, ast.ImportFrom):
                line_no = node.lineno
                context = lines[line_no - 1].strip() if line_no <= len(lines) else ""
                if node.module:
                    tokens.append((node.module, line_no, context))
                    for part in node.module.split("."):
                        if len(part) >= 3:
                            tokens.append((part, line_no, context))
                for alias in node.names:
                    if alias.name != "*":
                        tokens.append((alias.name, line_no, context))
            
            # 处理函数调用
            elif isinstance(node, ast.Call):
                line_no = node.lineno
                context = lines[line_no - 1].strip() if line_no <= len(lines) else ""
                call_name = self._get_call_name(node.func)
                if call_name and call_name not in _PY_KEYWORDS and len(call_name) >= 3:
                    tokens.append((call_name, line_no, context))
                    # 拆分调用链
                    for part in call_name.split("."):
                        if len(part) >= 3 and part not in _PY_KEYWORDS:
                            tokens.append((part, line_no, context))
            
            # 处理装饰器
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for decorator in node.decorator_list:
                    line_no = decorator.lineno
                    context = lines[line_no - 1].strip() if line_no <= len(lines) else ""
                    dec_name = self._get_decorator_name(decorator)
                    if dec_name and len(dec_name) >= 3:
                        tokens.append((dec_name, line_no, context))
            
            # 处理属性访问（可能是密码学库的常量或类）
            elif isinstance(node, ast.Attribute):
                line_no = node.lineno
                context = lines[line_no - 1].strip() if line_no <= len(lines) else ""
                attr_chain = self._get_attribute_chain(node)
                if attr_chain and len(attr_chain) >= 3:
                    tokens.append((attr_chain, line_no, context))
        
        return tokens

    def _get_call_name(self, node) -> str:
        """从AST节点获取函数调用名称"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_attribute_chain(node)
        return ""

    def _get_attribute_chain(self, node) -> str:
        """获取属性访问链（如 crypto.cipher.AES）"""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        parts.reverse()
        return ".".join(parts)

    def _get_decorator_name(self, node) -> str:
        """获取装饰器名称"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_attribute_chain(node)
        elif isinstance(node, ast.Call):
            return self._get_call_name(node.func)
        return ""

    def _extract_tokens_regex(self, lines: list[str]) -> list[tuple[str, int, str]]:
        """使用正则表达式提取tokens（回退方案）"""
        tokens = []

        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            m = self._IMPORT_RE.match(stripped)
            if m:
                modules = m.group(1).split(",")
                for mod in modules:
                    mod = mod.strip()
                    tokens.append((mod, line_no, stripped))
                    parts = mod.split(".")
                    if len(parts) > 1:
                        for part in parts:
                            if len(part) >= 3:
                                tokens.append((part, line_no, stripped))
                continue

            m = self._FROM_IMPORT_RE.match(stripped)
            if m:
                module = m.group(1).strip()
                imports = m.group(2).strip()
                tokens.append((module, line_no, stripped))
                for imp in re.split(r"[,\s]+", imports):
                    imp = imp.strip().rstrip(")")
                    if imp and imp != "(" and not imp.startswith("#"):
                        tokens.append((imp, line_no, stripped))
                continue

            m = self._DECORATOR_RE.match(stripped)
            if m:
                tokens.append((m.group(1), line_no, stripped))

            for m in self._FUNC_CALL_RE.finditer(stripped):
                call = m.group(1)
                if call not in _PY_KEYWORDS and len(call) >= 3:
                    tokens.append((call, line_no, stripped))
                    parts = call.split(".")
                    if len(parts) > 1:
                        for part in parts:
                            if len(part) >= 3 and part not in _PY_KEYWORDS:
                                tokens.append((part, line_no, stripped))

        return tokens


_PY_KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await",
    "break", "class", "continue", "def", "del", "elif", "else", "except",
    "finally", "for", "from", "global", "if", "import", "in", "is",
    "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
    "while", "with", "yield", "print", "len", "range", "str", "int",
    "float", "list", "dict", "set", "tuple", "type", "isinstance",
    "super", "self", "cls",
}
