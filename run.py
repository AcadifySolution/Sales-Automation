#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  NEXUS MASTER RUNNER  |  One Command to Run the Entire Engine
  Run: python3 run.py
================================================================================

  EXECUTION ORDER:
  1. Scrape fresh US startup leads  (lead_scraper.py)
  2. Enrich + score + save leads.csv
  3. Run outreach pipeline           (pipeline.py)
  4. Publish today's social posts    (social_manager.py)

  OPTIONAL FLAGS:
  --scrape-only    Only run lead scraping
  --pipeline-only  Only run email pipeline (uses existing leads.csv)
  --social-only    Only run social media posting
  --generate       Generate 30-day content calendar (one-time setup)
  --clutch         Generate Clutch profile content (one-time setup)
  --dry-run        Preview without sending emails or posting
================================================================================
"""

import sys
import argparse
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List

ROOT = Path(__file__).parent


def get_python() -> str:
    """
    Prefer the project venv interpreter so all packages resolve correctly.
    Falls back to current sys.executable if venv doesn't exist.
    """
    venv_py = ROOT / "venv" / "bin" / "python3"
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def run_module(module_file: str, extra_args: Optional[List[str]] = None) -> bool:
    """Run a python module as subprocess, stream output."""
    cmd = [get_python(), str(ROOT / module_file)] + (extra_args or [])
    print(f"\n{'─' * 60}")
    print(f"  ▶  Running: {module_file}")
    print(f"{'─' * 60}\n")

    result = subprocess.run(cmd, cwd=str(ROOT))
    return result.returncode == 0


def print_banner():
    print("\n" + "═" * 62)
    print("  ⚡  NEXUS SALES ENGINE  ·  MASTER RUNNER")
    print(f"  📅  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  🌏  India Dev Company → US Startup Outreach")
    print("═" * 62)


def main():
    parser = argparse.ArgumentParser(description="NEXUS Master Runner")
    parser.add_argument("--scrape-only",    action="store_true")
    parser.add_argument("--pipeline-only",  action="store_true")
    parser.add_argument("--social-only",    action="store_true")
    parser.add_argument("--followup-only",  action="store_true")
    parser.add_argument("--generate",       action="store_true",
                        help="Generate 30-day content calendar (one-time)")
    parser.add_argument("--clutch",         action="store_true",
                        help="Generate Clutch profile content (one-time)")
    parser.add_argument("--dry-run",        action="store_true")
    parser.add_argument("--schedule",       action="store_true",
                        help="Start daily auto-scheduler for social posts")
    args = parser.parse_args()

    print_banner()

    # ── One-time setup commands ──
    if args.generate:
        social_args = ["--generate"]
        if args.dry_run:
            social_args.append("--dry-run")
        run_module("social_manager.py", social_args)
        print("\n✅  Content calendar generated. Review content_calendar.csv")
        return

    if args.clutch:
        run_module("social_manager.py", ["--clutch"])
        print("\n✅  Clutch content generated. Review content/ folder")
        return

    if args.schedule:
        social_args = ["--schedule"]
        if args.dry_run:
            social_args.append("--dry-run")
        run_module("social_manager.py", social_args)
        return

    if args.followup_only:
        run_module("engine/followup_engine.py", [])
        print("\n✅  Follow-up drips processed.")
        return

    # ── Full pipeline run ──
    steps = []

    if not args.pipeline_only and not args.social_only and not args.followup_only:
        steps.append(("🔭  Step 1/4: Lead Scraping",   "engine/lead_scraper.py",   []))
    if not args.scrape_only and not args.social_only and not args.followup_only:
        steps.append(("📧  Step 2/4: Outreach Pipeline", "engine/pipeline.py",       []))
    if not args.scrape_only and not args.pipeline_only and not args.followup_only:
        social_args = ["--publish-today"]
        if args.dry_run:
            social_args.append("--dry-run")
        steps.append(("📱  Step 3/4: Social Publishing",  "engine/social_manager.py", social_args))
    if not args.scrape_only and not args.pipeline_only and not args.social_only:
        steps.append(("🔁  Step 4/4: Follow-up Drips",    "engine/followup_engine.py", []))

    for label, module, extra in steps:
        print(f"\n  {label}")
        success = run_module(module, extra)
        if not success:
            print(f"\n  ⚠️   {module} exited with errors — continuing to next step")
        time.sleep(1)

    print("\n" + "═" * 62)
    print("  🏁  ALL STEPS COMPLETE")
    print("  📄  Check: data/leads.csv · data/pipeline_report.csv · data/followup_tracker.csv · logs/pipeline.log")
    print("═" * 62 + "\n")


if __name__ == "__main__":
    main()
