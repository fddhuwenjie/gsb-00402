from app.analyzers.base_analyzer import BaseAnalyzer
from app.analyzers.c_analyzer import CAnalyzer
from app.analyzers.python_analyzer import PythonAnalyzer
from app.analyzers.java_analyzer import JavaAnalyzer
from app.analyzers.csharp_analyzer import CSharpAnalyzer
from app.analyzers.rust_analyzer import RustAnalyzer
from app.analyzers.perl_analyzer import PerlAnalyzer

ANALYZER_MAP: dict[str, type[BaseAnalyzer]] = {
    "c": CAnalyzer,
    "c++": CAnalyzer,
    "cpp": CAnalyzer,
    "python": PythonAnalyzer,
    "java": JavaAnalyzer,
    "c#": CSharpAnalyzer,
    "csharp": CSharpAnalyzer,
    "rust": RustAnalyzer,
    "perl": PerlAnalyzer,
}


def get_analyzer(language: str) -> BaseAnalyzer:
    lang = language.lower().strip()
    analyzer_cls = ANALYZER_MAP.get(lang)
    if analyzer_cls is None:
        raise ValueError(f"Unsupported language: {language}. Supported: {list(ANALYZER_MAP.keys())}")
    return analyzer_cls()


__all__ = [
    "BaseAnalyzer", "CAnalyzer", "PythonAnalyzer", "JavaAnalyzer",
    "CSharpAnalyzer", "RustAnalyzer", "PerlAnalyzer",
    "ANALYZER_MAP", "get_analyzer",
]
