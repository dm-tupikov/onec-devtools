"""Configuration for MCP DevTools server."""

import os
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


class Config(BaseModel):
    """Configuration for MCP DevTools."""

    # Path to 1C config dump (XML files)
    config_path: str = Field(
        default="",
        description="Path to 1C configuration XML dump (e.g., src/cf/) or .cf file"
    )

    # Server settings
    server_name: str = Field(default="1C-DevTools-MCP", description="MCP server name")
    server_version: str = Field(default="0.1.0", description="MCP server version")
    
    # BSL syntax help database
    syntax_help_path: str = Field(
        default="",
        description="Path to BSL syntax help JSON database"
    )

    # EPF tools settings
    headless_1c_path: str = Field(
        default="",
        description="Path to 1cv8.exe for headless EPF build/dump (e.g., C:\\Program Files\\1cv8\\bin\\1cv8.exe)"
    )
    test_base_server: str = Field(
        default="",
        description="Test 1C base server for EPF build/dump (Srvr=...; Ref=...)"
    )

    # Query settings
    query_max_rows: int = Field(default=10000, description="Max rows for query validation")
    
    # Audit settings
    audit_max_modules: int = Field(default=10000, description="Max modules to scan in audit")
    audit_min_duplicate_lines: int = Field(default=10, description="Minimum lines for duplicate detection")
    
    # Quality gate thresholds
    quality_max_cyclomatic: int = Field(default=10, description="Max cyclomatic complexity per function")
    quality_max_loc: int = Field(default=500, description="Max lines of code per module")
    quality_max_functions: int = Field(default=50, description="Max functions per module")

    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables."""
        return cls(
            config_path=os.environ.get("ONEC_DEVTOOLS_CONFIG_PATH", ""),
            server_name=os.environ.get("ONEC_DEVTOOLS_SERVER_NAME", "1C-DevTools-MCP"),
            server_version=os.environ.get("ONEC_DEVTOOLS_SERVER_VERSION", "0.1.0"),
            syntax_help_path=os.environ.get("ONEC_DEVTOOLS_SYNTAX_HELP_PATH", ""),
            headless_1c_path=os.environ.get("ONEC_DEVTOOLS_1C_PATH", ""),
            test_base_server=os.environ.get("ONEC_DEVTOOLS_TEST_BASE", ""),
            query_max_rows=int(os.environ.get("ONEC_DEVTOOLS_QUERY_MAX_ROWS", "10000")),
            audit_max_modules=int(os.environ.get("ONEC_DEVTOOLS_AUDIT_MAX_MODULES", "10000")),
            audit_min_duplicate_lines=int(os.environ.get("ONEC_DEVTOOLS_AUDIT_MIN_DUP_LINES", "10")),
            quality_max_cyclomatic=int(os.environ.get("ONEC_DEVTOOLS_MAX_CYCLOMATIC", "10")),
            quality_max_loc=int(os.environ.get("ONEC_DEVTOOLS_MAX_LOC", "500")),
            quality_max_functions=int(os.environ.get("ONEC_DEVTOOLS_MAX_FUNCTIONS", "50")),
        )

    def ensure_config_path(self) -> Path:
        """Ensure config path is set and return as Path."""
        if not self.config_path:
            raise ValueError(
                "Config path not set. Set ONEC_DEVTOOLS_CONFIG_PATH env var "
                "or pass --config-path argument. "
                "Point to 1C config XML dump directory (e.g., src/cf/)."
            )
        return Path(self.config_path)
