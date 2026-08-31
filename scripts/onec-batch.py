#!/usr/bin/env python3
"""CLI for verified 1C DESIGNER/ibcmd batch operations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow direct execution from the repository root: python scripts/onec-batch.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_devtools.command_catalog import designer_capabilities, ibcmd_capabilities
from mcp_devtools.ibcmd_runner import discover_ibcmd, run_ibcmd
from mcp_devtools.onec_batch import apply_xml_and_build_cf


def main() -> int:
    parser = argparse.ArgumentParser(description="Verified 1C batch operations")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("designer-capabilities")
    sub.add_parser("ibcmd-capabilities")

    build = sub.add_parser("apply-and-build-cf")
    build.add_argument("--onec", required=True, type=Path)
    build.add_argument("--infobase", required=True, type=Path)
    build.add_argument("--source", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--backup-dir", type=Path)
    build.add_argument("--log-dir", type=Path)

    ibhelp = sub.add_parser("ibcmd-help")
    ibhelp.add_argument("--ibcmd", required=True, type=Path)
    ibhelp.add_argument("--mode", default="infobase", choices=["infobase", "server", "session", "lock"])

    args = parser.parse_args()
    if args.command == "designer-capabilities":
        print(json.dumps(designer_capabilities(), ensure_ascii=False, indent=2))
    elif args.command == "ibcmd-capabilities":
        print(json.dumps(ibcmd_capabilities(), ensure_ascii=False, indent=2))
    elif args.command == "apply-and-build-cf":
        result = apply_xml_and_build_cf(
            onec_executable=args.onec,
            infobase=args.infobase,
            source_dir=args.source,
            output_cf=args.output,
            backup_dir=args.backup_dir,
            log_dir=args.log_dir,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    elif args.command == "ibcmd-help":
        result = discover_ibcmd(args.ibcmd, args.mode)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
