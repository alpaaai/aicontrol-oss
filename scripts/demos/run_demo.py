#!/usr/bin/env python3
"""
AIControl Demo Runner — select scenario by name
Usage: python scripts/demos/run_demo.py --scenario lending --token $TOKEN --mode walkthrough
"""
import argparse
import os
import sys

_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from scripts.demos.scenarios import SCENARIOS
from scripts.demos.engine import dispatch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AIControl Demo Runner")
    parser.add_argument("--scenario", required=True, choices=sorted(SCENARIOS.keys()),
                        help=f"Scenario to run: {', '.join(sorted(SCENARIOS.keys()))}")
    parser.add_argument("--token", required=True, help="Agent or admin JWT token")
    parser.add_argument("--mode", choices=["fast", "walkthrough"], default="walkthrough",
                        help="fast = no pauses, walkthrough = press ENTER between calls")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    dispatch(args.scenario, args.token, args.mode)


if __name__ == "__main__":
    main()
