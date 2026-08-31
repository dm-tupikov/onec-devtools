# 1C DevTools MCP Server

**74 tools for 1C:Enterprise development** — static analysis, code auditing, query validation, EPF verification, and more.

Works with local 1C XML config dumps — **no running 1C instance required**.

## Quick Start

### Docker

```bash
# Clone and setup
mkdir -p config-dump
# Copy your 1C config XML dump to config-dump/

# Build and run
docker build -t onec-devtools .
docker run --rm -it \
  -v $(pwd)/config-dump:/data/config:ro \
  -v $(pwd)/src/cf:/data/src:ro \
  onec-devtools

# Or with docker-compose
docker-compose up --build
```

### Local

```bash
pip install -r requirements.txt
python -m mcp_devtools --config-path ./config-dump
```

## Available Tools (74)

### A: Metadata (10)
| Tool | Description |
|------|-------------|
| `meta.tree` | Metadata tree by type |
| `meta.structure` | Full object structure |
| `meta.search` | Search by name/description |
| `meta.dependencies` | Dependency graph |
| `meta.find_orphans` | Objects without subsystem |
| `meta.compare` | Compare two metadata versions |
| `meta.find_undefined_refs` | References to non-existent objects |
| `meta.subsystem_map` | Subsystem → objects map |
| `meta.field_usage` | Where a field is used |
| `meta.cross_ref` | Cross-reference: forms, modules, queries |

### Б: Audit (15)
| Tool | Description |
|------|-------------|
| `audit.e1_e9` | Audit defects E1–E9 |
| `audit.query_antipatterns` | 15 query anti-patterns |
| `audit.code_antipatterns` | BSL code anti-patterns |
| `audit.security` | Hardcoded secrets |
| `audit.deprecated_api` | Deprecated API usage |
| `audit.pi_data` | Personal data patterns |
| `audit.rls_roles` | Roles and RLS analysis |
| `audit.duplicate_code` | Duplicate code blocks |
| `audit.dead_code` | Unused functions |
| `audit.module_complexity` | Cyclomatic complexity |
| `audit.tms_integration` | TMS 2.0 integration audit |
| `audit.exchange_safety` | Exchange plan safety |
| `audit.version_check` | Platform version compat |
| `audit.rnd_flag` | Loading flag (E8) check |
| `audit.transaction_boundary` | Transaction boundary (E4) |

### B: Query (8)
| Tool | Description |
|------|-------------|
| `query.validate` | Syntax + semantic validation |
| `query.optimize` | Optimization suggestions |
| `query.explain` | Logical plan extraction |
| `query.find_sinks` | Slow query patterns |
| `query.generate` | Generate from description |
| `query.check_fields` | Field validation |
| `query.check_dimensions` | Register dimension validation |
| `query.convert_to_async` | Sync to async conversion |

### Г: EPF (8)
| Tool | Description |
|------|-------------|
| `epf.validate` | Binary header validation |
| `epf.roundtrip_check` | Build → dump → diff |
| `epf.generate` | Generate from template |
| `epf.extract_info` | Metadata extraction |
| `epf.check_modules` | Module completeness |
| `epf.compare` | Compare two EPFs |
| `epf.validate_rules` | E1-E9 checklist |
| `epf.list_commands` | External processor commands |

### Д: Form & SKD (8)
| Tool | Description |
|------|-------------|
| `form.structure` | Form structure analysis |
| `form.find_orphans` | Forms without objects |
| `form.command_audit` | Command audit |
| `skd.structure` | Report layout structure |
| `skd.check_fields` | SKD field validation |
| `skd.compare` | Compare SKD layouts |
| `mxl.audit` | MXL layout audit |
| `form.to_async` | Modal to async conversion |

### Е: Integration (6)
| Tool | Description |
|------|-------------|
| `exchange.analyze` | Exchange plan analysis |
| `xdto.validate` | XDTO package validation |
| `kshd.contract_check` | KSHD contract compliance |
| `integration.retry_policy` | Retry policy audit |
| `integration.cascade_check` | Cascade cancellation |
| `integration.loop_prevention` | Loop prevention |

### Ё: Test & Quality (6)
| Tool | Description |
|------|-------------|
| `test.generate` | Test templates (YAxUnit/Vanessa) |
| `test.coverage` | Coverage analysis |
| `quality.metrics` | Quality metrics |
| `quality.bulk_analyze` | Full analysis (anti-patterns + dupes + dead code) |
| `quality.gate` | CI/CD quality gate |
| `quality.trend` | Quality trends |

### Ж: DevTools (8)
| Tool | Description |
|------|-------------|
| `bsl.syntax.help` | BSL function reference (30+) |
| `bsl.generate_query` | Query generator |
| `bsl.generate_print_form` | Print form template |
| `bsl.generate_report` | SKD report template |
| `bsl.convert_modal_async` | Modal call conversion |
| `bsl.find_synonyms` | Function synonyms |
| `bsl.version_check` | API version compatibility |
| `config.template_apply` | Config templates |

### З: Config (5)
| Tool | Description |
|------|-------------|
| `config.diff` | Compare two config builds |
| `config.validate_build` | Build readiness check |
| `config.added_objects` | Added/removed objects |
| `config.checklist` | Pre-commit checklist |
| `config.generate_report` | Full config report |

## Configuration

Set via environment variables or CLI args:

| Variable | Description | Default |
|----------|-------------|---------|
| `ONEC_DEVTOOLS_CONFIG_PATH` | Path to 1C config XML dump | required for metadata tools |
| `ONEC_DEVTOOLS_LOG_LEVEL` | Logging level | INFO |
| `ONEC_DEVTOOLS_TEST_BASE` | Test 1C base for EPF round-trip | optional |
| `ONEC_DEVTOOLS_1C_PATH` | Path to 1cv8.exe | optional |

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│  MCP Client  │────▶│  MCP-сервер      │────▶│  1C Config   │
│  (Kilo, etc) │◀────│  (Python)        │◀────│  (local XML) │
└──────────────┘     └──────────────────┘     └──────────────┘
```

Works entirely with local XML files — no running 1C instance needed for static analysis.

## License

MIT
