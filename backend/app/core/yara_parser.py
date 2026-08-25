"""
YARA signature file parser.
Extracts cryptographic function signatures from YARA rule files.
"""

import re
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class YaraSignature:
    identifier: str
    pattern: str
    prefix: str = ""

    def __post_init__(self):
        parts = self.pattern.rsplit("_", 1)
        if len(parts) > 1 and parts[0]:
            self.prefix = parts[0] + "_"
        else:
            self.prefix = self.pattern


@dataclass
class YaraRule:
    name: str
    description: str = ""
    extraction_method: str = ""
    generated: str = ""
    total_functions: int = 0
    signatures: list[YaraSignature] = field(default_factory=list)


class YaraParser:
    """Parses YARA rule files and extracts function signatures."""

    _META_PATTERN = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
    _META_INT_PATTERN = re.compile(r"(\w+)\s*=\s*(\d+)")
    _STRING_PATTERN = re.compile(r'\$(\w+)\s*=\s*"([^"]*)"')
    _RULE_START = re.compile(r"rule\s+(\w+)")
    _HEX_STRING_PATTERN = re.compile(r"\$(\w+)\s*=\s*\{([^}]*)\}")
    _REGEX_STRING_PATTERN = re.compile(r"\$(\w+)\s*=\s*/([^/]*)/" )

    def parse_file(self, file_path: str) -> list[YaraRule]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"YARA file not found: {file_path}")

        content = path.read_text(encoding="utf-8", errors="replace")
        return self.parse_content(content, source=str(path))

    def parse_content(self, content: str, source: str = "<string>") -> list[YaraRule]:
        rules: list[YaraRule] = []
        rule_blocks = self._split_rules(content)

        for rule_name, rule_body in rule_blocks:
            rule = YaraRule(name=rule_name)
            self._parse_meta(rule_body, rule)
            self._parse_strings(rule_body, rule)

            if rule.total_functions == 0:
                rule.total_functions = len(rule.signatures)

            logger.info("Parsed rule '%s' from %s: %d signatures", rule.name, source, len(rule.signatures))
            rules.append(rule)

        return rules

    def _split_rules(self, content: str) -> list[tuple[str, str]]:
        results = []
        matches = list(self._RULE_START.finditer(content))

        for i, m in enumerate(matches):
            name = m.group(1)
            start = m.end()
            brace_start = content.find("{", start)
            if brace_start == -1:
                continue

            depth = 1
            pos = brace_start + 1
            while pos < len(content) and depth > 0:
                if content[pos] == "{":
                    depth += 1
                elif content[pos] == "}":
                    depth -= 1
                pos += 1

            body = content[brace_start + 1 : pos - 1]
            results.append((name, body))

        return results

    def _parse_meta(self, body: str, rule: YaraRule):
        meta_match = re.search(r"meta\s*:", body)
        if not meta_match:
            return

        strings_match = re.search(r"strings\s*:", body)
        meta_end = strings_match.start() if strings_match else len(body)
        meta_section = body[meta_match.end() : meta_end]

        for m in self._META_PATTERN.finditer(meta_section):
            key, value = m.group(1), m.group(2)
            if key == "description":
                rule.description = value
            elif key == "extraction_method":
                rule.extraction_method = value
            elif key == "generated":
                rule.generated = value

        for m in self._META_INT_PATTERN.finditer(meta_section):
            key, value = m.group(1), int(m.group(2))
            if key == "total_functions":
                rule.total_functions = value

    def _parse_strings(self, body: str, rule: YaraRule):
        strings_match = re.search(r"strings\s*:", body)
        if not strings_match:
            return

        condition_match = re.search(r"condition\s*:", body)
        strings_end = condition_match.start() if condition_match else len(body)
        strings_section = body[strings_match.end() : strings_end]

        for m in self._STRING_PATTERN.finditer(strings_section):
            identifier, pattern = m.group(1), m.group(2)
            sig = YaraSignature(identifier=identifier, pattern=pattern)
            rule.signatures.append(sig)

        for m in self._HEX_STRING_PATTERN.finditer(strings_section):
            identifier = m.group(1)
            hex_content = m.group(2).strip()
            sig = YaraSignature(identifier=identifier, pattern=f"hex:{hex_content}")
            rule.signatures.append(sig)

    def parse_multiple_files(self, file_paths: list[str]) -> list[YaraRule]:
        all_rules: list[YaraRule] = []
        for fp in file_paths:
            try:
                rules = self.parse_file(fp)
                all_rules.extend(rules)
            except Exception as e:
                logger.error("Failed to parse YARA file %s: %s", fp, e)
        return all_rules
