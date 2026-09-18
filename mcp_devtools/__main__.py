"""CLI entry point for MCP DevTools."""

import argparse
import logging
import sys

from .config import Config
from .server import OneCDevToolsServer
from mcp.server.models import InitializationOptions
from mcp.server.lowlevel import NotificationOptions


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="1C DevTools MCP Server — 78 tools for 1C:Enterprise development"
    )
    
    parser.add_argument(
        "--config-path", "-c",
        default="",
        help="Path to 1C config XML dump (e.g., src/cf/)"
    )
    parser.add_argument(
        "--server-name",
        default="1C-DevTools-MCP",
        help="MCP server display name"
    )
    parser.add_argument(
        "--log-level", "-l",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    parser.add_argument(
        "--syntax-help-path",
        default="",
        help="Path to BSL syntax help JSON (optional — built-in by default)"
    )
    parser.add_argument(
        "--test-base",
        default="",
        help="Test 1C base for EPF round-trip (Srvr=...; Ref=...)"
    )
    parser.add_argument(
        "--1c-path",
        default="",
        help="Path to 1cv8.exe for headless EPF operations"
    )
    parser.add_argument(
        "--available-tools", "-t",
        action="store_true",
        help="Print available tools and exit"
    )
    
    return parser


AVAILABLE_TOOLS = [
    # Category A: Metadata
    "meta.tree", "meta.structure", "meta.search", "meta.dependencies",
    "meta.find_orphans", "meta.compare", "meta.find_undefined_refs",
    "meta.subsystem_map", "meta.field_usage", "meta.cross_ref",
    # Category Б: Audit
    "audit.e1_e9", "audit.query_antipatterns", "audit.code_antipatterns",
    "audit.security", "audit.deprecated_api", "audit.pi_data",
    "audit.rls_roles", "audit.duplicate_code", "audit.dead_code",
    "audit.module_complexity", "audit.tms_integration", "audit.exchange_safety",
    "audit.version_check", "audit.rnd_flag", "audit.transaction_boundary",
    # Category B: Query
    "query.validate", "query.optimize", "query.explain", "query.find_sinks",
    "query.generate", "query.check_fields", "query.check_dimensions",
    "query.convert_to_async",
    # Category Г: EPF
    "epf.validate", "epf.roundtrip_check", "epf.generate", "epf.extract_info",
    "epf.check_modules", "epf.compare", "epf.validate_rules", "epf.list_commands",
    # Category Д: Form & SKD
    "form.structure", "form.find_orphans", "form.command_audit",
    "skd.structure", "skd.check_fields", "skd.compare", "mxl.audit",
    "form.to_async",
    # Category E: Integration
    "exchange.analyze", "xdto.validate", "kshd.contract_check",
    "integration.retry_policy", "integration.cascade_check",
    "integration.loop_prevention",
    # Category Ё: Test & Quality
    "test.generate", "test.coverage", "quality.metrics",
    "quality.bulk_analyze", "quality.gate", "quality.trend",
    # Category Ж: DevTools
    "bsl.syntax.help", "bsl.generate_query", "bsl.generate_print_form",
    "bsl.generate_report", "bsl.convert_modal_async", "bsl.find_synonyms",
    "bsl.version_check", "config.template_apply",
    # Category З: Config
    "config.diff", "config.validate_build", "config.added_objects",
    "config.checklist", "config.generate_report",
]


# Keep CLI listing in sync with MCP discovery.
from .tool_names import AVAILABLE_TOOLS as _MCP_AVAILABLE_TOOLS
AVAILABLE_TOOLS = _MCP_AVAILABLE_TOOLS

def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    setup_logging(args.log_level)
    
    # Print available tools and exit if requested
    if args.available_tools:
        print(f"Available tools ({len(AVAILABLE_TOOLS)}):")
        for i, tool in enumerate(AVAILABLE_TOOLS, 1):
            print(f"  {i:3d}. {tool}")
        sys.exit(0)
    
    # Create config from args + env
    config = Config.from_env()
    config.config_path = args.config_path or config.config_path
    config.server_name = args.server_name
    config.test_base_server = args.test_base or config.test_base_server
    config.headless_1c_path = getattr(args, "onec_path", None) or getattr(args, "1c_path", "") or config.headless_1c_path
    
    if not config.config_path:
        print("Warning: --config-path not set. Metadata-dependent tools will have limited functionality.", 
              file=sys.stderr)
        print("Set --config-path to a 1C config XML dump directory (e.g., src/cf/)", file=sys.stderr)
    
    # Start MCP server
    from mcp.server.stdio import stdio_server
    
    server = OneCDevToolsServer(config)
    
    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.server.run(
                read_stream, write_stream,
                InitializationOptions(
                    server_name=server.config.server_name,
                    server_version=server.config.server_version,
                    capabilities=server.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    
    try:
        asyncio_run(run())
    except KeyboardInterrupt:
        print("\nServer stopped.", file=sys.stderr)


def asyncio_run(coro):
    """Run async coroutine with compatibility."""
    try:
        import asyncio
        asyncio.run(coro)
    except ImportError:
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(coro)


if __name__ == "__main__":
    main()
