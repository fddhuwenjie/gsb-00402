#!/usr/bin/env python3
"""
CBOM Analyzer CLI - command-line entry point for cryptographic code analysis.

Usage:
    python cli.py --yara <yara_file> --code <code_path> --lang <language> [--output <output_file>]

Examples:
    python cli.py --yara signatures/crypto.yar --code ./src --lang python
    python cli.py -y rules.yar -c ./project -l c -o report.json
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.yara_parser import YaraParser
from app.core.fuzzy_matcher import FuzzyMatcher
from app.core.cbom_generator import CBOMGenerator
from app.analyzers import get_analyzer

logger = logging.getLogger("cbom_cli")


def parse_args():
    parser = argparse.ArgumentParser(
        description="CBOM Analyzer - Cryptographic Bill of Materials analysis tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --yara crypto.yar --code ./src --lang python
  %(prog)s -y rules.yar -c ./project -l c -o report.json
  %(prog)s --yara sigs/ --code ./app --lang java --threshold 0.7

Supported languages: c, cpp, python, java, csharp, rust, perl
        """
    )

    parser.add_argument(
        "-y", "--yara", required=True, nargs="+",
        help="YARA signature file path(s), supports multiple files or directories",
    )
    parser.add_argument("-c", "--code", required=True, help="Source code path (file or directory)")
    parser.add_argument(
        "-l", "--lang", required=True,
        choices=["c", "cpp", "c++", "python", "java", "csharp", "c#", "rust", "perl"],
        help="Code language type",
    )
    parser.add_argument("-o", "--output", default=None, help="Output report file path (default: stdout)")
    parser.add_argument("-t", "--threshold", type=float, default=0.6, help="Fuzzy match threshold 0-1 (default: 0.6)")
    parser.add_argument("--json", action="store_true", default=True, help="JSON output (default)")
    parser.add_argument("--summary", action="store_true", help="Print summary only")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--version", action="version", version="CBOM Analyzer v1.0.0")

    return parser.parse_args()


def collect_yara_files(yara_paths: list[str]) -> list[str]:
    all_files = []
    for yara_path in yara_paths:
        path = Path(yara_path)
        if path.is_file():
            all_files.append(str(path))
        elif path.is_dir():
            files = list(path.glob("**/*.yar")) + list(path.glob("**/*.yara"))
            all_files.extend([str(f) for f in files])
        else:
            raise FileNotFoundError(f"YARA path not found: {yara_path}")
    return all_files


def run_analysis(args) -> dict:
    start_time = time.time()

    lang_aliases = {"c++": "cpp", "c#": "csharp"}
    lang = lang_aliases.get(args.lang, args.lang)

    yara_files = collect_yara_files(args.yara)
    if not yara_files:
        raise ValueError(f"No YARA files found: {args.yara}")

    logger.info("Found %d YARA file(s)", len(yara_files))

    parser = YaraParser()
    all_patterns = []
    sig_file_names = []

    for yara_file in yara_files:
        rules = parser.parse_file(yara_file)
        sig_file_names.append(Path(yara_file).name)
        for rule in rules:
            for sig in rule.signatures:
                if sig.pattern and not sig.pattern.startswith("hex:"):
                    all_patterns.append(sig.pattern)

    if not all_patterns:
        raise ValueError("No valid function signatures found in YARA files")

    logger.info("Extracted %d function signatures", len(all_patterns))

    code_path = Path(args.code)
    if not code_path.exists():
        raise FileNotFoundError(f"Code path not found: {args.code}")

    analyzer = get_analyzer(lang)
    logger.info("Scanning with %s analyzer...", analyzer.language_name)

    file_tokens = analyzer.scan_directory(str(code_path))
    logger.info("Scanned %d file(s)", len(file_tokens))

    matcher = FuzzyMatcher(threshold=args.threshold)
    all_matches = []

    for file_path, tokens in file_tokens:
        try:
            rel_path = str(Path(file_path).relative_to(code_path))
        except ValueError:
            rel_path = file_path
        matches = matcher.match_tokens_in_file(tokens, all_patterns, rel_path)
        all_matches.extend(matches)

    logger.info("Found %d match(es)", len(all_matches))

    scan_duration = time.time() - start_time
    cbom_gen = CBOMGenerator()

    return cbom_gen.generate(
        matches=all_matches,
        target_path=str(code_path),
        language=lang,
        signature_files=sig_file_names,
        total_files_scanned=len(file_tokens),
        scan_duration=scan_duration,
    )


def print_summary(report: dict):
    summary = report.get("summary", {})

    print("=" * 50)
    print("CBOM Analysis Report Summary")
    print("=" * 50)
    print(f"扫描文件数: {summary.get('total_files_scanned', 0)}")
    print(f"匹配总数: {summary.get('total_matches', 0)}")
    print(f"密码组件数: {summary.get('total_crypto_components', 0)}")
    print(f"风险等级: {summary.get('risk_level', 'unknown')}")
    print(f"扫描耗时: {summary.get('scan_duration_seconds', 0):.2f}秒")
    print("=" * 50)

    components = report.get("components", [])
    if components:
        print("\n检测到的密码组件:")
        for comp in components[:10]:
            print(f"  - {comp.get('name', 'unknown')} ({comp.get('total_occurrences', 0)} occurrences)")
        if len(components) > 10:
            print(f"  ... and {len(components) - 10} more")


def main():
    args = parse_args()

    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="[%(levelname)s] %(message)s",
        stream=sys.stderr,
    )

    try:
        report = run_analysis(args)

        if args.summary:
            print_summary(report)
        else:
            output = json.dumps(report, ensure_ascii=False, indent=2)
            if args.output:
                Path(args.output).write_text(output, encoding="utf-8")
                logger.info("Report saved to: %s", args.output)
            else:
                print(output)

        risk = report.get("summary", {}).get("risk_level", "low")
        sys.exit(1 if risk == "high" else 0)

    except FileNotFoundError as e:
        logger.error("File not found: %s", e)
        sys.exit(2)
    except ValueError as e:
        logger.error("Argument error: %s", e)
        sys.exit(2)
    except Exception as e:
        logger.error("Analysis failed: %s", e)
        if args.verbose:
            import traceback
            traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
