#!/usr/bin/env python3
"""
Web Signup Script Builder Agent

Usage:
  python agent.py "https://example.com/signup/" --recon-only
  python agent.py "https://example.com/signup/" --name mysite --out ../mysite_signup
  python agent.py --from-analysis analysis.json --out ../mysite_signup

Set LLM in .env: BUILDER_LLM=deepseek|anthropic|openai|openrouter|ollama|gemini|antigravity
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from llm_router import analyze_with_llm, get_provider_config  # noqa: E402
from recon import analyze_url, report_to_markdown, save_report  # noqa: E402
from scaffold import scaffold_project  # noqa: E402


def load_env() -> None:
    for p in (ROOT / ".env", ROOT.parent / ".env"):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    load_env()
    ap = argparse.ArgumentParser(description="Build Matrix signup scripts from any URL")
    ap.add_argument("url", nargs="?", help="Signup page URL")
    ap.add_argument("--name", help="Project slug (default: from domain)")
    ap.add_argument("--out", type=Path, help="Output directory")
    ap.add_argument("--recon-only", action="store_true", help="Only run recon, no LLM/scaffold")
    ap.add_argument("--from-analysis", type=Path, help="Skip LLM; use existing analysis.json")
    ap.add_argument("--notes", default="", help="Extra hints for LLM")
    ap.add_argument("--no-scripts", action="store_true", help="Skip fetching external JS files")
    args = ap.parse_args()

    if args.from_analysis:
        spec = json.loads(args.from_analysis.read_text(encoding="utf-8"))
        out = args.out or ROOT.parent / f"{spec.get('project_name', 'signup')}_signup"
        scaffold_project(spec, out)
        print(f"Scaffolded from {args.from_analysis} -> {out}")
        return 0

    if not args.url:
        ap.print_help()
        return 1

    print(f"Recon: {args.url}")
    report = analyze_url(args.url, fetch_scripts=not args.no_scripts)
    recon_path = ROOT / "recon_report.json"
    save_report(report, str(recon_path))
    md_path = ROOT / "recon_report.md"
    md_path.write_text(report_to_markdown(report), encoding="utf-8")
    print(f"Saved {recon_path} and {md_path}")

    if args.recon_only:
        print(report_to_markdown(report))
        return 0

    try:
        provider, _, model, _ = get_provider_config()
        print(f"LLM: {provider} / {model}")
    except (RuntimeError, ValueError) as e:
        print(f"LLM config error: {e}")
        print("Tip: set BUILDER_LLM and API key in .env, or use --recon-only + manual analysis.json")
        return 1

    recon_dict = report.to_dict()
    if report.consent_snippets:
        recon_dict["consent_snippets"] = report.consent_snippets

    print("Analyzing with LLM...")
    spec = analyze_with_llm(recon_dict, user_notes=args.notes)

    if args.name:
        spec["project_name"] = args.name

    if not spec.get("project_name"):
        from urllib.parse import urlparse
        spec["project_name"] = urlparse(args.url).netloc.split(".")[0]

    analysis_path = ROOT / "analysis.json"
    analysis_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(f"Saved {analysis_path}")

    out = args.out or ROOT.parent / f"{spec['project_name']}_signup"
    scaffold_project(spec, out)
    print(f"Generated project: {out}")
    print("\nNext steps:")
    print(f"  cd {out}")
    print("  cp .env.example .env   # add MATRIX_USER, MATRIX_PASS")
    print("  pip install -r requirements.txt")
    print("  bash run.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
