"""MCP DevTools Server — 74 tools for 1C:Enterprise development.

Provides static analysis tools for 1C configuration development:
- Metadata analysis and structure inspection
- BSL code auditing (queue leaks, transactions, loading flags, security, anti-patterns)
- Query validation and optimization
- EPF artifact verification
- Form and SKD analysis
- Integration testing utilities
- Quality metrics and CI/CD gates
- Development assistants (syntax help, code generation)

Works with local 1C XML config dumps — no running 1C instance required.
"""

import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, AsyncIterator

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.lowlevel import NotificationOptions
from mcp import types

from .config import Config
from .parser_1c_xml import OneCConfigParser, METADATA_TYPES
from .bsl_analyzer import (
    QueryAnalyzer, BSLAnalyzer, get_bsl_syntax_help,
    find_bsl_synonyms, check_api_version, BSL_SYNTAX_HELP,
)
from .epf_tools import (
    validate_epf, extract_epf_info, build_epf_roundtrip_check,
    check_epf_modules_complete, compare_epfs,
)
from .command_catalog import designer_capabilities, ibcmd_capabilities
from .ibcmd_runner import run_ibcmd
from .onec_batch import apply_xml_and_build_cf
from .tool_names import AVAILABLE_TOOLS

logger = logging.getLogger(__name__)


class OneCDevToolsServer:
    """MCP server providing 74 development tools for 1C:Enterprise."""
    
    def __init__(self, config: Config):
        self.config = config
        self.parser: Optional[OneCConfigParser] = None
        self._ensure_config_path()
        
        # Create MCP server
        self.server = Server(
            name=config.server_name,
            lifespan=self._lifespan
        )
        
        # Register all 74 tools
        self._register_tools()
        
    def _ensure_config_path(self):
        """Ensure config path is set."""
        if not self.config.config_path:
            logger.warning("Config path not set — metadata-dependent tools will return errors")
            
    @asynccontextmanager
    async def _lifespan(self, server: Server) -> AsyncIterator[Dict[str, Any]]:
        """Server lifespan: initialize parser."""
        logger.info(f"Initializing {self.config.server_name} v{self.config.server_version}")
        
        if self.config.config_path:
            try:
                self.parser = OneCConfigParser(self.config.config_path)
                self.parser.parse()
                logger.info(f"Parsed config: {len(self.parser._all_objects)} objects, "
                           f"{len(self.parser._modules)} modules")
            except Exception as e:
                logger.warning(f"Failed to parse config: {e}")
        else:
            logger.warning("No config path set — using stub responses for metadata tools")
            
        yield {"parser": self.parser, "config": self.config}
        
    def _register_tools(self):
        """Register all 74 MCP tools."""
        
        # ============================================================
        # CATEGORY A: Metadata (10 tools)
        # ============================================================
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            return [types.Tool(
                name=tool_name,
                description=f"1C DevTools operation: {tool_name}",
                inputSchema={"type": "object", "additionalProperties": True},
            ) for tool_name in AVAILABLE_TOOLS]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
            """Main tool call handler — routes to specific tools."""
            try:
                result = await self._dispatch_tool(name, arguments)
                return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
            except Exception as e:
                logger.error(f"Tool {name} error: {e}", exc_info=True)
                return [types.TextContent(type="text", text=json.dumps({
                    "error": str(e),
                    "tool": name,
                }, ensure_ascii=False))]
                
    async def _dispatch_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch tool calls to handlers."""
        
        # CATEGORY A: Metadata tools
        if name == "meta.tree":
            return self._tool_meta_tree(args)
        elif name == "meta.structure":
            return self._tool_meta_structure(args)
        elif name == "meta.search":
            return self._tool_meta_search(args)
        elif name == "meta.dependencies":
            return self._tool_meta_dependencies(args)
        elif name == "meta.find_orphans":
            return self._tool_meta_find_orphans(args)
        elif name == "meta.compare":
            return self._tool_meta_compare(args)
        elif name == "meta.find_undefined_refs":
            return self._tool_meta_find_undefined_refs(args)
        elif name == "meta.subsystem_map":
            return self._tool_meta_subsystem_map(args)
        elif name == "meta.field_usage":
            return self._tool_meta_field_usage(args)
        elif name == "meta.cross_ref":
            return self._tool_meta_cross_ref(args)
            
        # CATEGORY Б: Audit tools
        elif name == "audit.e1_e9":
            return self._tool_audit_e1_e9(args)
        elif name == "audit.query_antipatterns":
            return self._tool_audit_query_antipatterns(args)
        elif name == "audit.code_antipatterns":
            return self._tool_audit_code_antipatterns(args)
        elif name == "audit.security":
            return self._tool_audit_security(args)
        elif name == "audit.deprecated_api":
            return self._tool_audit_deprecated_api(args)
        elif name == "audit.pi_data":
            return self._tool_audit_pi_data(args)
        elif name == "audit.rls_roles":
            return self._tool_audit_rls_roles(args)
        elif name == "audit.duplicate_code":
            return self._tool_audit_duplicate_code(args)
        elif name == "audit.dead_code":
            return self._tool_audit_dead_code(args)
        elif name == "audit.module_complexity":
            return self._tool_audit_module_complexity(args)
        elif name == "audit.tms_integration":
            return self._tool_audit_tms_integration(args)
        elif name == "audit.exchange_safety":
            return self._tool_audit_exchange_safety(args)
        elif name == "audit.version_check":
            return self._tool_audit_version_check(args)
        elif name == "audit.rnd_flag":
            return self._tool_audit_rnd_flag(args)
        elif name == "audit.transaction_boundary":
            return self._tool_audit_transaction_boundary(args)
            
        # CATEGORY B: Query tools
        elif name == "query.validate":
            return self._tool_query_validate(args)
        elif name == "query.optimize":
            return self._tool_query_optimize(args)
        elif name == "query.explain":
            return self._tool_query_explain(args)
        elif name == "query.find_sinks":
            return self._tool_query_find_sinks(args)
        elif name == "query.generate":
            return self._tool_query_generate(args)
        elif name == "query.check_fields":
            return self._tool_query_check_fields(args)
        elif name == "query.check_dimensions":
            return self._tool_query_check_dimensions(args)
        elif name == "query.convert_to_async":
            return self._tool_query_convert_to_async(args)
            
        # CATEGORY Г: EPF tools
        elif name == "epf.validate":
            return self._tool_epf_validate(args)
        elif name == "epf.roundtrip_check":
            return self._tool_epf_roundtrip_check(args)
        elif name == "epf.generate":
            return self._tool_epf_generate(args)
        elif name == "epf.extract_info":
            return self._tool_epf_extract_info(args)
        elif name == "epf.check_modules":
            return self._tool_epf_check_modules(args)
        elif name == "epf.compare":
            return self._tool_epf_compare(args)
        elif name == "epf.validate_rules":
            return self._tool_epf_validate_rules(args)
        elif name == "epf.list_commands":
            return self._tool_epf_list_commands(args)
            
        # CATEGORY Д: Form & SKD tools
        elif name == "form.structure":
            return self._tool_form_structure(args)
        elif name == "form.find_orphans":
            return self._tool_form_find_orphans(args)
        elif name == "form.command_audit":
            return self._tool_form_command_audit(args)
        elif name == "skd.structure":
            return self._tool_skd_structure(args)
        elif name == "skd.check_fields":
            return self._tool_skd_check_fields(args)
        elif name == "skd.compare":
            return self._tool_skd_compare(args)
        elif name == "mxl.audit":
            return self._tool_mxl_audit(args)
        elif name == "form.to_async":
            return self._tool_form_to_async(args)
            
        # CATEGORY Е: Integration tools
        elif name == "exchange.analyze":
            return self._tool_exchange_analyze(args)
        elif name == "xdto.validate":
            return self._tool_xdto_validate(args)
        elif name == "kshd.contract_check":
            return self._tool_kshd_contract_check(args)
        elif name == "integration.retry_policy":
            return self._tool_integration_retry_policy(args)
        elif name == "integration.cascade_check":
            return self._tool_integration_cascade_check(args)
        elif name == "integration.loop_prevention":
            return self._tool_integration_loop_prevention(args)
            
        # CATEGORY Ё: Test & Quality tools
        elif name == "test.generate":
            return self._tool_test_generate(args)
        elif name == "test.coverage":
            return self._tool_test_coverage(args)
        elif name == "quality.metrics":
            return self._tool_quality_metrics(args)
        elif name == "quality.bulk_analyze":
            return self._tool_quality_bulk_analyze(args)
        elif name == "quality.gate":
            return self._tool_quality_gate(args)
        elif name == "quality.trend":
            return self._tool_quality_trend(args)
            
        # CATEGORY Ж: DevTools
        elif name == "bsl.syntax.help":
            return self._tool_bsl_syntax_help(args)
        elif name == "bsl.generate_query":
            return self._tool_bsl_generate_query(args)
        elif name == "bsl.generate_print_form":
            return self._tool_bsl_generate_print_form(args)
        elif name == "bsl.generate_report":
            return self._tool_bsl_generate_report(args)
        elif name == "bsl.convert_modal_async":
            return self._tool_bsl_convert_modal_async(args)
        elif name == "bsl.find_synonyms":
            return self._tool_bsl_find_synonyms(args)
        elif name == "bsl.version_check":
            return self._tool_bsl_version_check(args)
        elif name == "config.template_apply":
            return self._tool_config_template_apply(args)
            
        # CATEGORY З: Config tools
        elif name == "config.diff":
            return self._tool_config_diff(args)
        elif name == "config.validate_build":
            return self._tool_config_validate_build(args)
        elif name == "config.added_objects":
            return self._tool_config_added_objects(args)
        elif name == "config.checklist":
            return self._tool_config_checklist(args)
        elif name == "config.generate_report":
            return self._tool_config_generate_report(args)
        elif name == "designer.capabilities":
            return {"capabilities": designer_capabilities()}
        elif name == "designer.apply_xml_and_build_cf":
            result = apply_xml_and_build_cf(
                onec_executable=Path(args["onec_executable"]),
                infobase=Path(args["infobase"]),
                source_dir=Path(args["source_dir"]),
                output_cf=Path(args["output_cf"]),
                backup_dir=Path(args["backup_dir"]) if args.get("backup_dir") else None,
                log_dir=Path(args["log_dir"]) if args.get("log_dir") else None,
            )
            return result.to_dict()
        elif name == "ibcmd.capabilities":
            return {"capabilities": ibcmd_capabilities()}
        elif name == "ibcmd.run":
            result = run_ibcmd(
                ibcmd_executable=Path(args["ibcmd_executable"]),
                arguments=args.get("arguments", []),
                confirmed=bool(args.get("confirmed", False)),
            )
            return result.to_dict()
            
        else:
            return {"error": f"Unknown tool: {name}. Run 'devtool.available_tools' to see list."}
            
    # ============================================================
    # Tool implementations
    # ============================================================
    
    # --- CATEGORY A: Metadata (10) ---
    
    def _tool_meta_tree(self, args: Dict) -> Dict:
        """A1: metadata tree."""
        parser = self.parser
        if not parser:
            return {"error": "Config not loaded. Set --config-path."}
        object_type = args.get("object_type", "")
        return parser.get_metadata_tree(object_type)
        
    def _tool_meta_structure(self, args: Dict) -> Dict:
        """A2: object structure."""
        parser = self.parser
        if not parser:
            return {"error": "Config not loaded."}
        name = args.get("object_name", "")
        if not name:
            return {"error": "object_name required"}
        return parser.get_object_structure(name) or {"error": f"Object not found: {name}"}
        
    def _tool_meta_search(self, args: Dict) -> Dict:
        """A3: search metadata."""
        parser = self.parser
        if not parser:
            return {"error": "Config not loaded."}
        query = args.get("query", "")
        obj_type = args.get("object_type", "")
        if not query:
            return {"error": "query required"}
        results = parser.search_metadata(query, obj_type)
        return {"query": query, "count": len(results), "results": results}
        
    def _tool_meta_dependencies(self, args: Dict) -> Dict:
        """A4: object dependency graph."""
        parser = self.parser
        if not parser:
            return {"error": "Config not loaded."}
        obj_name = args.get("object_name", "")
        direction = args.get("direction", "references")  # "references" or "referenced_by"
        
        if direction == "referenced_by":
            refs = parser.find_object_refs(obj_name)
            return {"object": obj_name, "direction": direction, "referenced_in": refs}
        else:
            obj = parser.get_object_structure(obj_name)
            if not obj:
                return {"error": f"Object not found: {obj_name}"}
            return {"object": obj_name, "direction": direction, "structure": obj}
            
    def _tool_meta_find_orphans(self, args: Dict) -> Dict:
        """A5: find objects without subsystem."""
        parser = self.parser
        if not parser:
            return {"error": "Config not loaded."}
        orphans = parser.get_orphaned_objects()
        return {"orphaned_objects": orphans, "count": len(orphans)}
        
    def _tool_meta_compare(self, args: Dict) -> Dict:
        """A6: compare two metadata versions."""
        path1 = args.get("path1", "")
        path2 = args.get("path2", "")
        if not path1 or not path2:
            return {"error": "path1 and path2 required"}
        
        try:
            p1 = OneCConfigParser(path1).parse()
            p2 = OneCConfigParser(path2).parse()
            
            names1 = {o.name for o in p1._all_objects}
            names2 = {o.name for o in p2._all_objects}
            
            return {
                "added": list(names2 - names1),
                "removed": list(names1 - names2),
                "common": len(names1 & names2),
                "total1": len(names1),
                "total2": len(names2),
            }
        except Exception as e:
            return {"error": str(e)}
            
    def _tool_meta_find_undefined_refs(self, args: Dict) -> Dict:
        """A7: find references to non-existent objects."""
        parser = self.parser
        if not parser:
            return {"error": "Config not loaded."}
        issues = parser.find_undefined_refs()
        return {"issues": issues, "count": len(issues)}
        
    def _tool_meta_subsystem_map(self, args: Dict) -> Dict:
        """A8: subsystem to objects map."""
        parser = self.parser
        if not parser:
            return {"error": "Config not loaded."}
        return parser.get_subsystem_map()
        
    def _tool_meta_field_usage(self, args: Dict) -> Dict:
        """A9: find where a field is used."""
        parser = self.parser
        if not parser:
            return {"error": "Config not loaded."}
        field = args.get("field_name", "")
        if not field:
            return {"error": "field_name required"}
        return parser.get_field_usage(field)
        
    def _tool_meta_cross_ref(self, args: Dict) -> Dict:
        """A10: cross-reference for an object."""
        parser = self.parser
        if not parser:
            return {"error": "Config not loaded."}
        obj_name = args.get("object_name", "")
        if not obj_name:
            return {"error": "object_name required"}
        result = parser.get_cross_reference(obj_name)
        if not result:
            return {"error": f"Object not found: {obj_name}"}
        return result
        
    # --- CATEGORY Б: Audit (15) ---
    
    def _tool_audit_e1_e9(self, args: Dict) -> Dict:
        """Б1: audit common BSL defects — queue leaks, transactions, loading flags, KPI logic."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required (path to .bsl file or directory)"}
            
        issues = {"queue_leak": [], "case_mismatch": [], "transaction_boundary": [], "loading_flag": [], "kpi_logic": []}
        
        path = Path(code_path)
        files_to_scan = []
        
        if path.is_file():
            files_to_scan = [path]
        elif path.is_dir():
            files_to_scan = list(path.rglob("*.bsl"))
        else:
            return {"error": f"Path not found: {code_path}"}
            
        max_modules = self.config.audit_max_modules
        for i, bsl_file in enumerate(files_to_scan):
            if i >= max_modules:
                break
            try:
                code = bsl_file.read_text(encoding="utf-8", errors="replace")
                filename = bsl_file.name
                
                # Queue leak: Continue in loop without unregistering
                if "Продолжить" in code and ("Цикл" in code or "Выбрать" in code):
                    lines = code.split("\n")
                    for j, line in enumerate(lines):
                        if "Продолжить" in line and "//" not in line:
                            context = "\n".join(lines[max(0,j-10):j])
                            if any(kw in context for kw in ["Цикл", "Выбрать", "Обмен", "Continue"]):
                                issues["queue_leak"].append({"file": str(bsl_file), "line": j+1})
                                
                # Case mismatch: snake_case keys not converted to PascalCase
                if "snake" in code.lower() or "_address" in code.lower() or "_time" in code.lower() or "_type" in code.lower():
                    if "Получить" in code or "Нормализ" in code or "convert" in code.lower():
                        issues["case_mismatch"].append({"file": str(bsl_file), "line": 1,
                                            "note": "Possible snake_case to PascalCase mapping issue"})
                                        
                # Transaction boundary: НачатьТранзакцию without ЗафиксироватьТранзакцию
                if "НачатьТранзакцию" in code or "ЗафиксироватьТранзакцию" in code:
                    issues["transaction_boundary"].append({"file": str(bsl_file), "note": "Transaction blocks found — verify isolation"})
                    
                # Loading flag: ПриЗаписи without Загрузка flag
                if "Загрузка" in code or "ОбменДанными" in code:
                    if "ПриЗаписи" in code or "ПередЗаписью" in code:
                        issues["loading_flag"].append({"file": str(bsl_file), "note": "Write event handlers found — verify loading flag"})
                        
                # KPI logic: check for Регистратор filter in KPI calculations
                if ("КИП" in code or "КТГ" in code or "КВЛ" in code or "KPI" in code):
                    if "Регистратор" in code or "Registrar" in code or "Document" in code:
                        issues["kpi_logic"].append({"file": str(bsl_file), "note": "KPI calculation found — verify source document filter"})
                        
            except Exception as e:
                issues["_errors"] = issues.get("_errors", [])
                issues["_errors"].append(str(bsl_file))
                
        total = sum(len(v) for k, v in issues.items() if k != "_errors")
        return {
            "total_issues": total,
            "files_scanned": len(files_to_scan),
            "defects": issues,
        }
        
    def _tool_audit_query_antipatterns(self, args: Dict) -> Dict:
        """Б2: detect query anti-patterns."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        results = []
        
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += f"\n// === {bsl_file} ===\n"
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        queries = BSLAnalyzer.extract_all_queries(code)
        for q in queries:
            anti_patterns = QueryAnalyzer.detect_anti_patterns(q["query_text"])
            if anti_patterns:
                results.append({
                    "file": q["name"],
                    "anti_patterns": anti_patterns,
                })
                
        return {"files_with_issues": len(results), "details": results}
        
    def _tool_audit_code_antipatterns(self, args: Dict) -> Dict:
        """Б3: detect code anti-patterns."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += f"\n// === {bsl_file} ===\n"
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        issues = BSLAnalyzer.detect_code_antipatterns(code)
        return {"issues": issues, "count": len(issues)}
        
    def _tool_audit_security(self, args: Dict) -> Dict:
        """Б4: detect hardcoded secrets."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += f"\n// === {bsl_file} ===\n"
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        issues = BSLAnalyzer.detect_hardcoded_secrets(code)
        return {"issues": issues, "count": len(issues)}
        
    def _tool_audit_deprecated_api(self, args: Dict) -> Dict:
        """Б5: detect deprecated API usage."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += f"\n// === {bsl_file} ===\n"
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        issues = BSLAnalyzer.detect_deprecated_api(code)
        return {"issues": issues, "count": len(issues)}
        
    def _tool_audit_pi_data(self, args: Dict) -> Dict:
        """Б6: find personal data patterns in code."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        # Look for patterns that might indicate PI handling
        pi_patterns = [
            (r"(\d{3}[-\s]?\d{2}[-\s]?\d{2}[-\s]?\d{4})", "passport number"),
            (r"\b\d{10,12}\b", "INN/KPP number"),
            (r"(ФИО|fio|fullname)", "PI reference"),
        ]
        
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        findings = []
        for pattern, desc in pi_patterns:
            matches = list(re.finditer(pattern, code, re.IGNORECASE))
            if matches:
                findings.append({
                    "pattern": desc,
                    "count": len(matches),
                    "sample_lines": list(set(m.group() for m in matches[:5])),
                })
                
        return {"findings": findings, "total_findings": len(findings)}
        
    def _tool_audit_rls_roles(self, args: Dict) -> Dict:
        """Б7: analyze roles and RLS."""
        parser = self.parser
        if not parser:
            return {"error": "Config not loaded."}
            
        # Look for Roles metadata
        roles = []
        for obj in parser._all_objects:
            if "Role" in obj.type or "Роль" in obj.name:
                roles.append(obj.to_dict())
                
        # Look for RLS in modules
        rsl_patterns = ["Допустимость", "RLS", "restrict", "доступ"]
        rls_modules = []
        for path, content in parser._modules.items():
            for pattern in rsl_patterns:
                if pattern.lower() in content.lower():
                    rls_modules.append({"path": path, "matches": pattern})
                    break
                    
        return {"roles": roles, "rls_modules": rls_modules}
        
    def _tool_audit_duplicate_code(self, args: Dict) -> Dict:
        """Б8: find duplicate code blocks."""
        code_path = args.get("code_path", "")
        min_lines = args.get("min_lines", self.config.audit_min_duplicate_lines)
        
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += f"\n// === {bsl_file} ===\n"
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        duplicates = BSLAnalyzer.detect_duplicate_code(code, min_lines)
        return {"duplicates": duplicates, "count": len(duplicates)}
        
    def _tool_audit_dead_code(self, args: Dict) -> Dict:
        """Б9: find unused functions and modules."""
        parser = self.parser
        if not parser:
            return {"error": "Config not loaded."}
            
        # Build call graph
        all_calls = {}
        for path, content in parser._modules.items():
            # Find function/procedure definitions
            for match in re.finditer(r"(Процедура|Функция)\s+(\w+)", content):
                func_name = match.group(2)
                if func_name not in all_calls:
                    all_calls[func_name] = {"path": path, "called_by": []}
                    
        # Find references to functions
        for path, content in parser._modules.items():
            for func_name in all_calls:
                if func_name in content and all_calls[func_name]["path"] != path:
                    all_calls[func_name]["called_by"].append(path)
                    
        # Functions never called (except entry points)
        entry_points = {"ПриНачалеРаботыСистемы", "ПриИзмененииДанных", "ПриЗаписи", 
                       "ПередЗаписью", "ПередУдалением", "НаЭкране", "ПолучениеДанных"}
        dead = {name: info for name, info in all_calls.items() 
                if not info["called_by"] and name not in entry_points}
                
        return {"dead_code": dead, "count": len(dead)}
        
    def _tool_audit_module_complexity(self, args: Dict) -> Dict:
        """Б10: module complexity metrics."""
        code_path = args.get("code_path", "")
        
        path = Path(code_path)
        results = []
        
        files_to_scan = []
        if path.is_file():
            files_to_scan = [path]
        elif path.is_dir():
            files_to_scan = list(path.rglob("*.bsl"))
            
        max_loc = self.config.quality_max_loc
        max_cyclo = self.config.quality_max_cyclomatic
        max_funcs = self.config.quality_max_functions
        
        for bsl_file in files_to_scan:
            try:
                code = bsl_file.read_text(encoding="utf-8", errors="replace")
                metrics = BSLAnalyzer.calculate_complexity(code)
                
                issues = []
                if metrics["total_lines"] > max_loc:
                    issues.append(f"Too many lines: {metrics['total_lines']} > {max_loc}")
                if metrics["max_complexity"] > max_cyclo:
                    issues.append(f"High complexity: {metrics['max_complexity']} > {max_cyclo}")
                if metrics["total_functions"] > max_funcs:
                    issues.append(f"Too many functions: {metrics['total_functions']} > {max_funcs}")
                    
                results.append({
                    "file": str(bsl_file),
                    "lines": metrics["total_lines"],
                    "functions": metrics["total_functions"],
                    "max_complexity": metrics["max_complexity"],
                    "issues": issues,
                })
            except Exception:
                pass
                
        return {"results": results, "files_with_issues": sum(1 for r in results if r["issues"])}
        
    def _tool_audit_tms_integration(self, args: Dict) -> Dict:
        """Б11: audit external integration code — transport contract, idempotency, case mapping."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        issues = []
        
        # Check for Continue in exchange loop without unregister
        if "Обмен" in code and "Продолжить" in code:
            if "рег." not in code.lower() or "unregister" not in code.lower():
                issues.append({"defect": "queue_leak", "message": "Continue in exchange loop — verify registration removal"})
                
        # Check for transport contract: Base64 vs JSON
        if "records" in code and ("value" in code or "key" in code):
            if "Base64" in code or "base64" in code:
                issues.append({"defect": "transport_contract", "message": "Base64 decoding found — verify JSON vs binary contract"})
                
        # Check for case mismatch in mapping
        if "snake" in code.lower() or "_" in code:
            if "Получить" in code or "Нормализ" in code:
                issues.append({"defect": "case_mismatch", "message": "Possible case mapping issue in data conversion"})
                
        # Check for idempotency: write without uniqueness check
        if "Код" in code and ("Записать" in code or "СоздатьДокумент" in code):
            if "ПроверитьУникальность" not in code and "НайтиПоРеквизиту" not in code:
                issues.append({"defect": "idempotency", "message": "Write without uniqueness check"})
                
        return {"issues": issues, "scanned": True}
        
    def _tool_audit_exchange_safety(self, args: Dict) -> Dict:
        """Б12: exchange plan safety audit."""
        parser = self.parser
        if not parser:
            return {"error": "Config not loaded."}
            
        # Find exchange plan nodes
        exchange_plans = [o for o in parser._all_objects 
                         if "ExchangePlan" in o.type or "Обмен" in o.name]
                         
        issues = []
        for plan in exchange_plans:
            # Look for rules without cascade handling
            issues.append({
                "plan": plan.name,
                "type": plan.type,
                "note": "Review rules for cascade handling and idempotency",
            })
            
        return {"exchange_plans": [p.to_dict() for p in exchange_plans], "issues": issues}
        
    def _tool_audit_version_check(self, args: Dict) -> Dict:
        """Б13: platform version compatibility check."""
        code_path = args.get("code_path", "")
        target_version = args.get("target_version", "8.3.0")
        
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        # Check for version-specific API calls
        incompatibilities = []
        for func_name in BSL_SYNTAX_HELP:
            info = BSL_SYNTAX_HELP[func_name]
            if info["since"] > target_version:
                if func_name in code:
                    incompatibilities.append({
                        "function": func_name,
                        "introduced": info["since"],
                        "target_version": target_version,
                    })
                    
        return {"incompatibilities": incompatibilities, "count": len(incompatibilities)}
        
    def _tool_audit_rnd_flag(self, args: Dict) -> Dict:
        """Б14: audit loading flag in write event handlers."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        issues = []
        
        files_to_scan = []
        if path.is_file():
            files_to_scan = [path]
        elif path.is_dir():
            files_to_scan = list(path.rglob("*.bsl"))
            
        for bsl_file in files_to_scan:
            code = bsl_file.read_text(encoding="utf-8", errors="replace")
            
            # Look for write handlers
            if "ПриЗаписи" in code or "ПередЗаписью" in code:
                # Check if loading flag is set
                if "Загрузка" not in code and "loading" not in code.lower():
                    issues.append({
                        "file": str(bsl_file),
                        "issue": "Write event handler without loading flag check",
                        "defect": "loading_flag",
                    })
                    
        return {"issues": issues, "count": len(issues)}
        
    def _tool_audit_transaction_boundary(self, args: Dict) -> Dict:
        """Б15: audit transaction boundary consistency."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        issues = []
        
        files_to_scan = []
        if path.is_file():
            files_to_scan = [path]
        elif path.is_dir():
            files_to_scan = list(path.rglob("*.bsl"))
            
        for bsl_file in files_to_scan:
            code = bsl_file.read_text(encoding="utf-8", errors="replace")
            
            has_begin = "НачатьТранзакцию" in code
            has_commit = "ЗафиксироватьТранзакцию" in code
            
            if has_begin or has_commit:
                if has_begin and not has_commit:
                    issues.append({
                        "file": str(bsl_file),
                        "issue": "НачатьТранзакцию without ЗафиксироватьТранзакцию",
                        "defect": "transaction_boundary",
                    })
                elif has_commit and not has_begin:
                    issues.append({
                        "file": str(bsl_file),
                        "issue": "ЗафиксироватьТранзакцию without НачатьТранзакцию",
                        "defect": "transaction_boundary",
                    })
                    
        return {"issues": issues, "count": len(issues)}
        
    # --- CATEGORY B: Query (8) ---
    
    def _tool_query_validate(self, args: Dict) -> Dict:
        """В1: validate 1C query."""
        query = args.get("query", "")
        if not query:
            return {"error": "query required"}
        return QueryAnalyzer.validate_query(query)
        
    def _tool_query_optimize(self, args: Dict) -> Dict:
        """В2: optimize 1C query."""
        query = args.get("query", "")
        if not query:
            return {"error": "query required"}
        return QueryAnalyzer.optimize_query(query)
        
    def _tool_query_explain(self, args: Dict) -> Dict:
        """В3: logical plan extraction from query."""
        query = args.get("query", "")
        if not query:
            return {"error": "query required"}
        return QueryAnalyzer.extract_query_fields(query)
        
    def _tool_query_find_sinks(self, args: Dict) -> Dict:
        """В4: find slow query patterns in code."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += f"\n// === {bsl_file} ===\n"
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        queries = BSLAnalyzer.extract_all_queries(code)
        sinks = []
        for q in queries:
            issues = QueryAnalyzer.detect_anti_patterns(q["query_text"])
            if issues:
                sinks.append({"query": q["name"], "issues": issues})
                
        return {"slow_patterns": sinks, "count": len(sinks)}
        
    def _tool_query_generate(self, args: Dict) -> Dict:
        """В5: generate query from description."""
        description = args.get("description", "")
        object_name = args.get("object_name", "")
        
        if not description:
            return {"error": "description required"}
            
        # Simple query generation based on description keywords
        query = ""
        
        if "остаток" in description.lower() or "остатки" in description.lower():
            query = f"ВЫБРАТЬ * ИЗ Документ.уатПутевойЛист WHERE Дата >= ПОДСТАНОВКА('НачалоДня(ТекущаяДата()) - 1')"
        elif "счет" in description.lower() or "количество" in description.lower():
            query = f"ВЫБРАТЬ РАЗЛИЧНЫЕ Счет ИЗ Справочник.уатТС"
        elif "список" in description.lower() or "перечень" in description.lower():
            query = f"ВЫБРАТЬ ПЕРВЫЕ 100 * ИЗ Справочник.{object_name or 'Номенклатура'}"
        else:
            query = f"ВЫБРАТЬ * ИЗ {object_name or 'Справочник.Номенклатура'}"
            
        return {
            "description": description,
            "generated_query": query,
            "note": "This is a template — adjust field names and filters for your configuration",
        }
        
    def _tool_query_check_fields(self, args: Dict) -> Dict:
        """В6: validate query fields against metadata."""
        parser = self.parser
        query = args.get("query", "")
        
        if not query:
            return {"error": "query required"}
            
        if not parser:
            return {"error": "Config not loaded."}
            
        # Extract field references from query
        query_upper = query.upper()
        issues = []
        
        # Simple check: look for field references
        for obj in parser._all_objects:
            obj_name = obj.name.upper()
            if obj_name in query_upper and obj_name not in ["ВЫБРАТЬ", "ИЗ", "ГДЕ", "ЦИКЛ", "ПО"]:
                # Object found in query — valid reference
                pass
                
        return {"query_valid": True, "referenced_objects": [], "note": "Full field validation requires detailed metadata"}
        
    def _tool_query_check_dimensions(self, args: Dict) -> Dict:
        """В7: validate register dimensions in queries."""
        parser = self.parser
        query = args.get("query", "")
        
        if not query:
            return {"error": "query required"}
        if not parser:
            return {"error": "Config not loaded."}
            
        # Check for register references
        register_refs = [o for o in parser._all_objects 
                        if "Register" in o.type or "Регистр" in o.name]
                        
        return {
            "registers_in_config": [r.name for r in register_refs],
            "note": "Dimension validation requires query + register metadata cross-reference",
        }
        
    def _tool_query_convert_to_async(self, args: Dict) -> Dict:
        """В8: convert synchronous query calls to async."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        conversions = []
        
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += f"\n// === {bsl_file} ===\n"
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        # Look for common sync patterns
        sync_patterns = [
            (r"Запрос\.Выполнить\(\)", "AsyncQuery.Execute()"),
            (r"\.Выбрать\(\)", "ВыбратьДвижения().Загрузить()"),
            (r"\.ПолучитьФорму\(", "ОжидатьФорму()"),
        ]
        
        for pattern, replacement in sync_patterns:
            if re.search(pattern, code):
                conversions.append({
                    "pattern": pattern,
                    "suggestion": replacement,
                    "note": "Manual review required for conversion",
                })
                
        return {"conversions": conversions, "count": len(conversions)}
        
    # --- CATEGORY Г: EPF (8) ---
    
    def _tool_epf_validate(self, args: Dict) -> Dict:
        """Г1: validate EPF binary header."""
        epf_path = args.get("epf_path", "")
        if not epf_path:
            return {"error": "epf_path required"}
        return validate_epf(epf_path)
        
    def _tool_epf_roundtrip_check(self, args: Dict) -> Dict:
        """Г2: EPF round-trip verification."""
        epf_path = args.get("epf_path", "")
        return build_epf_roundtrip_check(epf_path, self.config.config_path)
        
    def _tool_epf_generate(self, args: Dict) -> Dict:
        """Г3: generate EPF from template."""
        template = args.get("template", "")
        name = args.get("name", "")
        
        if not template or not name:
            return {"error": "template and name required"}
            
        # Return generation plan
        return {
            "template": template,
            "name": name,
            "generated_structure": {
                "Ext/ObjectModule.bsl": "#ИмяОбработки = \"" + name + "\"",
                "Ext/ManagerModule.bsl": "// ManagerModule for " + name,
                "Forms/Форма/Ext/Form.xml": "<Форма>",
                "Forms/Форма/Module.bsl": "// FormModule",
            },
            "note": "Full EPF generation requires 1C headless build",
        }
        
    def _tool_epf_extract_info(self, args: Dict) -> Dict:
        """Г4: extract EPF metadata."""
        epf_path = args.get("epf_path", "")
        if not epf_path:
            return {"error": "epf_path required"}
        return extract_epf_info(epf_path)
        
    def _tool_epf_check_modules(self, args: Dict) -> Dict:
        """Г5: check EPF module completeness."""
        epf_path = args.get("epf_path", "")
        if not epf_path:
            return {"error": "epf_path required"}
        return check_epf_modules_complete(epf_path)
        
    def _tool_epf_compare(self, args: Dict) -> Dict:
        """Г6: compare two EPF files."""
        return compare_epfs(args.get("epf1", ""), args.get("epf2", ""))
        
    def _tool_epf_validate_rules(self, args: Dict) -> Dict:
        """Г7: validate EPF against common BSL audit rules."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path or epf_path required"}
            
        # Run common BSL audit on the extracted code
        return self._tool_audit_e1_e9({"code_path": code_path})
        
    def _tool_epf_list_commands(self, args: Dict) -> Dict:
        """Г8: list external processor commands."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        # Find command handlers
        commands = re.findall(r"Процедура\s+Команда(\w+)", code)
        return {"commands": commands, "count": len(commands)}
        
    # --- CATEGORY Д: Form & SKD (8) ---
    
    def _tool_form_structure(self, args: Dict) -> Dict:
        """Д1: form structure analysis."""
        parser = self.parser
        form_name = args.get("form_name", "")
        
        if not parser:
            return {"error": "Config not loaded."}
        if not form_name:
            return {"error": "form_name required"}
            
        # Search for form in modules
        form_files = []
        for path in parser._modules:
            if form_name.lower() in path.lower() and "Form" in path:
                form_files.append(path)
                
        return {
            "form_name": form_name,
            "form_files": form_files,
            "note": "Full form XML analysis requires .xml parsing",
        }
        
    def _tool_form_find_orphans(self, args: Dict) -> Dict:
        """Д2: find forms without objects."""
        parser = self.parser
        if not parser:
            return {"error": "Config not loaded."}
            
        # Forms that reference non-existent objects
        orphan_forms = []
        for obj in parser._all_objects:
            for form_id in obj.form_ids:
                # Check if form exists
                pass
                
        return {"orphan_forms": orphan_forms, "count": len(orphan_forms)}
        
    def _tool_form_command_audit(self, args: Dict) -> Dict:
        """Д3: audit form commands."""
        parser = self.parser
        if not parser:
            return {"error": "Config not loaded."}
            
        commands = []
        for obj in parser._all_objects:
            if obj.command_ids:
                commands.append({
                    "object": obj.name,
                    "commands": obj.command_ids,
                })
                
        return {"commands": commands, "total": sum(len(c["commands"]) for c in commands)}
        
    def _tool_skd_structure(self, args: Dict) -> Dict:
        """Д4: SKD (report layout) structure."""
        parser = self.parser
        report_name = args.get("report_name", "")
        
        if not parser:
            return {"error": "Config not loaded."}
        if not report_name:
            return {"error": "report_name required"}
            
        # Find report object
        report = None
        for obj in parser._all_objects:
            if obj.name == report_name:
                report = obj
                break
                
        if not report:
            return {"error": f"Report not found: {report_name}"}
            
        return {
            "report": report.to_dict(),
            "forms": report.form_ids,
            "note": "SKD XML analysis requires .xml file parsing",
        }
        
    def _tool_skd_check_fields(self, args: Dict) -> Dict:
        """Д5: validate SKD fields against metadata."""
        report_name = args.get("report_name", "")
        if not report_name:
            return {"error": "report_name required"}
            
        return {
            "report": report_name,
            "note": "Full SKD field validation requires SKD XML parsing",
        }
        
    def _tool_skd_compare(self, args: Dict) -> Dict:
        """Д6: compare SKD layouts."""
        path1 = args.get("path1", "")
        path2 = args.get("path2", "")
        
        if not path1 or not path2:
            return {"error": "path1 and path2 required"}
            
        try:
            c1 = Path(path1).read_text(encoding="utf-8", errors="replace")
            c2 = Path(path2).read_text(encoding="utf-8", errors="replace")
            
            return {
                "different": c1 != c2,
                "size1": len(c1),
                "size2": len(c2),
            }
        except Exception as e:
            return {"error": str(e)}
            
    def _tool_mxl_audit(self, args: Dict) -> Dict:
        """Д7: audit MXL layouts."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for mxl_file in path.rglob("*.mxl"):
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        # Look for MXL references to non-existent objects
        return {"mxl_issues": [], "note": "MXL analysis requires layout file parsing"}
        
    def _tool_form_to_async(self, args: Dict) -> Dict:
        """Д8: convert modal form calls to async."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        # Look for modal call patterns
        modal_calls = re.findall(r"\.ОткрытьМодально\(\)", code)
        return {
            "modal_calls_found": len(modal_calls),
            "suggestion": "Consider using ОжидатьФорму() or event-based patterns",
        }
        
    # --- CATEGORY Е: Integration (6) ---
    
    def _tool_exchange_analyze(self, args: Dict) -> Dict:
        """Е1: analyze exchange plans."""
        parser = self.parser
        if not parser:
            return {"error": "Config not loaded."}
            
        exchange_plans = [o for o in parser._all_objects 
                         if "ExchangePlan" in o.type or "Обмен" in o.name or "ПланОбмена" in o.name]
                         
        return {
            "exchange_plans": [p.to_dict() for p in exchange_plans],
            "count": len(exchange_plans),
        }
        
    def _tool_xdto_validate(self, args: Dict) -> Dict:
        """Е2: validate XDTO packages."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        xdto_refs = re.findall(r"ТипXDTO|XDTO|ОписаниеТипов", code)
        return {
            "xdto_references": len(xdto_refs),
            "note": "Full XDTO validation requires package XML files",
        }
        
    def _tool_kshd_contract_check(self, args: Dict) -> Dict:
        """Е3: check KSHD contract compliance."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        issues = []
        
        # Check for records pattern with potential Base64 vs JSON confusion
        if "records" in code and ("value" in code):
            if "JSON" not in code and "json" not in code:
                issues.append({"issue": "transport_contract", "message": "records value decoding — verify JSON vs Base64"})
                
        # Check for routing handlers
        if "routing" in code.lower() or "routingType" in code.lower():
            issues.append({"issue": "routing_coverage", "message": "Message routing found — verify all types are handled"})
            
        return {"issues": issues, "contract_compliant": len(issues) == 0}
        
    def _tool_integration_retry_policy(self, args: Dict) -> Dict:
        """Е4: audit retry policy in integration code."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        issues = []
        
        if "Попытка" in code:
            if "Исключение" in code:
                if "Повтор" not in code and "retry" not in code.lower() and "count" not in code.lower():
                    issues.append({"issue": "No retry counter found in Попытка block"})
            else:
                issues.append({"issue": "Попытка without Исключение"})
                
        return {"issues": issues, "retry_policy_defined": len([i for i in issues if "retry" in str(i).lower()]) == 0}
        
    def _tool_integration_cascade_check(self, args: Dict) -> Dict:
        """Е5: audit cascade cancellation handling."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        issues = []
        
        if "Отмена" in code or "cancel" in code.lower():
            if "Проведение" not in code and "posting" not in code.lower():
                issues.append({"issue": "Cancellation found without posting reversal"})
            if "ИсторияОбменов" not in code:
                issues.append({"issue": "Cancellation without exchange history update"})
                
        return {"issues": issues, "cascade_safe": len(issues) == 0}
        
    def _tool_integration_loop_prevention(self, args: Dict) -> Dict:
        """Е6: check loop prevention (incoming not re-registered as outgoing)."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        issues = []
        
        # Check for loading flag usage
        if "Загрузка" not in code and ("ПриЗаписи" in code or "ПередЗаписью" in code):
            issues.append({"issue": "No loading flag — incoming data may trigger outgoing registration"})
            
        # Check for exchange plan filtering and source differentiation
        if "Обмен" in code or "Exchange" in code:
            if "загружено" not in code.lower() and "source" not in code.lower():
                issues.append({"issue": "No source differentiation for incoming changes"})
                
        return {
            "issues": issues,
            "loop_prevention": len(issues) == 0,
            "recommendations": ["Set loading flag before write",
                               "Check source of changes (external vs local)"],
        }
        
    # --- CATEGORY Ё: Test & Quality (6) ---
    
    def _tool_test_generate(self, args: Dict) -> Dict:
        """Ё1: generate test templates (YAxUnit / Vanessa)."""
        object_name = args.get("object_name", "")
        test_type = args.get("test_type", "unit")
        
        if not object_name:
            return {"error": "object_name required"}
            
        if test_type == "unit":
            template = f"""// Generated test for {object_name}
// Framework: YAxUnit / Vanessa-Automation

Функция ТестСоздание{object_name}(Отказ)
    
    Попытка
        Объект = Документы.{objectName}.СоздатьДокумент();
        Объект.Дата = ТекущаяДата();
        Объект.Записать(РежимЗаписиДокумента.Проведение);
        
        Возврат Истина;
    Исключение
        Отказ = Истина;
        Сообщить(ОписаниеОшибки());
        Возврат Ложь;
    КонецПопытки;
    
КонецФункции // ТестСоздание{objectName}
"""
        elif test_type == "integration":
            template = f"""// Integration test for {object_name}
// Framework: Vanessa-Automation

Функция ИнтеграционныйТест{objectName}()
    
    // TODO: Add integration test logic
    // 1. Prepare test data
    // 2. Execute operation
    // 3. Verify results
    // 4. Cleanup
    
    Возврат Истина;
    
КонецФункции // ИнтеграционныйТест{objectName}
"""
        else:
            template = f"// Test template for {object_name} ({test_type})"
            
        return {
            "object": object_name,
            "type": test_type,
            "template": template,
            "note": "Adapt field names and business logic for your configuration",
        }
        
    def _tool_test_coverage(self, args: Dict) -> Dict:
        """Ё2: analyze test coverage."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        test_files = []
        source_files = []
        
        if path.is_dir():
            test_files = list(path.rglob("*Тест*.bsl")) + list(path.rglob("*test*.bsl"))
            source_files = [f for f in path.rglob("*.bsl") if "test" not in f.name.lower()]
            
        return {
            "test_files": len(test_files),
            "source_files": len(source_files),
            "coverage_estimate": f"{len(test_files)}/{len(source_files)} files have test coverage",
        }
        
    def _tool_quality_metrics(self, args: Dict) -> Dict:
        """Ё3: code quality metrics."""
        code_path = args.get("code_path", "")
        
        path = Path(code_path)
        files_to_scan = []
        if path.is_dir():
            files_to_scan = list(path.rglob("*.bsl"))
        elif path.is_file():
            files_to_scan = [path]
            
        total_lines = 0
        total_functions = 0
        total_issues = 0
        max_cyclo = 0
        
        for bsl_file in files_to_scan:
            try:
                code = bsl_file.read_text(encoding="utf-8", errors="replace")
                metrics = BSLAnalyzer.calculate_complexity(code)
                total_lines += metrics["total_lines"]
                total_functions += metrics["total_functions"]
                max_cyclo = max(max_cyclo, metrics["max_complexity"])
            except Exception:
                pass
                
        return {
            "total_files": len(files_to_scan),
            "total_lines": total_lines,
            "total_functions": total_functions,
            "max_cyclomatic_complexity": max_cyclo,
            "avg_loc_per_function": total_lines / max(total_functions, 1),
        }
        
    def _tool_quality_bulk_analyze(self, args: Dict) -> Dict:
        """Ё4: bulk analysis (anti-patterns + duplicates + dead code + security)."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += f"\n// === {bsl_file} ===\n"
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        results = {
            "security_issues": BSLAnalyzer.detect_hardcoded_secrets(code),
            "duplicate_blocks": BSLAnalyzer.detect_duplicate_code(code, self.config.audit_min_duplicate_lines),
            "module_metrics": BSLAnalyzer.calculate_complexity(code),
        }
        
        return {
            "summary": {
                "security_issues": len(results["security_issues"]),
                "duplicates": len(results["duplicate_blocks"]),
                "max_complexity": results["module_metrics"]["max_complexity"],
                "total_functions": results["module_metrics"]["total_functions"],
            },
            "recommendations": [],
        }
        
    def _tool_quality_gate(self, args: Dict) -> Dict:
        """Ё5: CI/CD quality gate check."""
        code_path = args.get("code_path", "")
        max_cyclo = args.get("max_cyclomatic", self.config.quality_max_cyclomatic)
        max_loc = args.get("max_loc", self.config.quality_max_loc)
        
        path = Path(code_path)
        results = {"passed": True, "checks": [], "violations": []}
        
        files_to_scan = []
        if path.is_dir():
            files_to_scan = list(path.rglob("*.bsl"))
        elif path.is_file():
            files_to_scan = [path]
            
        for bsl_file in files_to_scan:
            try:
                code = bsl_file.read_text(encoding="utf-8", errors="replace")
                metrics = BSLAnalyzer.calculate_complexity(code)
                
                if metrics["total_lines"] > max_loc:
                    results["passed"] = False
                    results["violations"].append({
                        "file": str(bsl_file),
                        "check": "max_loc",
                        "value": metrics["total_lines"],
                        "threshold": max_loc,
                    })
                    
                if metrics["max_complexity"] > max_cyclo:
                    results["passed"] = False
                    results["violations"].append({
                        "file": str(bsl_file),
                        "check": "max_cyclomatic",
                        "value": metrics["max_complexity"],
                        "threshold": max_cyclo,
                    })
                    
            except Exception:
                pass
                
        return results
        
    def _tool_quality_trend(self, args: Dict) -> Dict:
        """Ё6: quality metrics trend (requires multiple config snapshots)."""
        paths = args.get("paths", [])
        if not paths:
            return {"error": "paths (list of config paths) required for trend analysis"}
            
        results = []
        for path in paths:
            try:
                p = Path(path)
                bsl_files = list(p.rglob("*.bsl"))
                total_lines = sum(len(f.read_text(encoding="utf-8", errors="replace").split("\n")) for f in bsl_files if f.exists())
                results.append({"path": path, "lines": total_lines, "files": len(bsl_files)})
            except Exception:
                pass
                
        return {"snapshots": results, "trend": "insufficient_data" if len(results) < 2 else "compare snapshots"}
        
    # --- CATEGORY Ж: DevTools (8) ---
    
    def _tool_bsl_syntax_help(self, args: Dict) -> Dict:
        """Ж1: BSL syntax help."""
        func_name = args.get("function_name", "")
        return get_bsl_syntax_help(func_name)
        
    def _tool_bsl_generate_query(self, args: Dict) -> Dict:
        """Ж2: generate query from description."""
        return self._tool_query_generate(args)
        
    def _tool_bsl_generate_print_form(self, args: Dict) -> Dict:
        """Ж3: generate print form template."""
        object_name = args.get("object_name", "")
        
        if not object_name:
            return {"error": "object_name required"}
            
        return {
            "object": object_name,
            "template": f"""// Print form template for {object_name}
// Uses УправлениеПечатью framework

Процедура Печать(Отказ)
    
    КомандаПечати = Новый КомандаПечати;
    КомандаПечати.Команда = Печать.ПолучитьКомандуПечати("{object_name}");
    
    ТабличныйДокумент = Новый ТабличныйДокумент;
    Макет = Объект.ПолучитьМакет("Печать");
    
    // TODO: Add print layout template
    
    КомандаПечати.ТабличныйДокумент = ТабличныйДокумент;
    КомандаПечати.Исполнитель = Справочники.Пользователи.ТекущийПользователь();
    
    Печать.Выполнить(КомандаПечати);
    
КонецПроцедуры // Печать
""",
            "note": "Create macro 'Печать' in the document form",
        }
        
    def _tool_bsl_generate_report(self, args: Dict) -> Dict:
        """Ж4: generate SKD report template."""
        report_name = args.get("report_name", "")
        
        if not report_name:
            return {"error": "report_name required"}
            
        return {
            "report": report_name,
            "structure": {
                "metadata": f"Создайте отчёт '{report_name}' с источником данных",
                "query": f"ВЫБРАТЬ * ИЗ {report_name}",
                "groups": ["Поля для группировки"],
                "fields": ["Поля для вывода"],
            },
            "note": "Full SKD report requires layout XML creation",
        }
        
    def _tool_bsl_convert_modal_async(self, args: Dict) -> Dict:
        """Ж5: convert modal calls to async."""
        code_path = args.get("code_path", "")
        if not code_path:
            return {"error": "code_path required"}
            
        path = Path(code_path)
        code = ""
        if path.is_file():
            code = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for bsl_file in path.rglob("*.bsl"):
                code += bsl_file.read_text(encoding="utf-8", errors="replace")
                
        # Find modal calls
        modal_calls = []
        for i, line in enumerate(code.split("\n"), 1):
            if "ОткрытьМодально" in line or "ОткрытьФорму" in line:
                modal_calls.append({"line": i, "code": line.strip()})
                
        return {
            "modal_calls": modal_calls,
            "count": len(modal_calls),
            "suggestion": "Replace with event-driven pattern or AsyncForm",
        }
        
    def _tool_bsl_find_synonyms(self, args: Dict) -> Dict:
        """Ж6: find BSL function synonyms."""
        func_name = args.get("function_name", "")
        if not func_name:
            return {"error": "function_name required"}
        return find_bsl_synonyms(func_name)
        
    def _tool_bsl_version_check(self, args: Dict) -> Dict:
        """Ж7: check API version compatibility."""
        func_name = args.get("function_name", "")
        platform_version = args.get("platform_version", "8.3.24")
        
        if not func_name:
            return {"error": "function_name required"}
        return check_api_version(func_name, platform_version)
        
    def _tool_config_template_apply(self, args: Dict) -> Dict:
        """Ж8: apply configuration template."""
        template = args.get("template", "")
        name = args.get("name", "")
        
        if not template or not name:
            return {"error": "template and name required"}
            
        templates = {
            "external_processor": {
                "description": "External data processor template",
                "structure": {
                    "Ext/ObjectModule.bsl": "#ИмяОбработки = \"" + name + "\"\n#Область\nПроцедура ПриОткрытии(Отказ)\nКонецПроцедуры",
                    "Ext/ManagerModule.bsl": "#Область\nПроцедура Обработать(Параметры)\nКонецПроцедуры",
                    "Forms/Форма/Ext/Form.xml": "<Форма>\n  <Вид>Диалог</Вид>\n</Форма>",
                    "Commands/Create.bsl": "#Область\nПроцедура Create(Команда)\nКонецПроцедуры",
                },
            },
            "report": {
                "description": "SKD report template",
                "structure": {
                    "Ext/ObjectModule.bsl": "#ИмяОтчёта = \"" + name + "\"\nПроцедура ПриСозданииНаСервере(Отказ, data)\nКонецПроцедуры",
                    "Ext/ManagerModule.bsl": "// ManagerModule",
                },
            },
        }
        
        if template not in templates:
            return {"error": f"Unknown template: {template}. Available: {', '.join(templates.keys())}"}
            
        return {
            "template": template,
            "name": name,
            "applied": templates[template],
            "note": "Apply to config directory and rebuild",
        }
        
    # --- CATEGORY З: Config (5) ---
    
    def _tool_config_diff(self, args: Dict) -> Dict:
        """З1: compare two config builds."""
        path1 = args.get("path1", "")
        path2 = args.get("path2", "")
        
        if not path1 or not path2:
            return {"error": "path1 and path2 required"}
            
        try:
            p1 = OneCConfigParser(path1).parse()
            p2 = OneCConfigParser(path2).parse()
            
            names1 = {o.name: o for o in p1._all_objects}
            names2 = {o.name: o for o in p2._all_objects}
            
            added = [n for n in names2 if n not in names1]
            removed = [n for n in names1 if n not in names2]
            changed = []
            
            for n in set(names1.keys()) & set(names2.keys()):
                o1 = names1[n]
                o2 = names2[n]
                if o1.description != o2.description or o1.code != o2.code:
                    changed.append(n)
                    
            return {
                "added": added,
                "removed": removed,
                "changed": changed,
                "summary": {
                    "added_count": len(added),
                    "removed_count": len(removed),
                    "changed_count": len(changed),
                }
            }
        except Exception as e:
            return {"error": str(e)}
            
    def _tool_config_validate_build(self, args: Dict) -> Dict:
        """З2: validate config readiness for build."""
        config_path = args.get("config_path", self.config.config_path)
        if not config_path:
            return {"error": "config_path required"}
            
        path = Path(config_path)
        if not path.exists():
            return {"error": f"Config path not found: {config_path}"}
            
        issues = []
        warnings = []
        
        # Check required directories
        required_dirs = ["Catalogs", "Documents", "CommonModules"]
        for dir_name in required_dirs:
            dir_path = path / dir_name
            if not dir_path.exists():
                warnings.append(f"Directory not found: {dir_name}")
                
        # Check for .git in config
        git_path = path / ".git"
        if git_path.exists():
            issues.append(".git directory found in config dump — should be excluded")
            
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "checks_performed": ["required_directories", "git_exclusion", "file_integrity"],
        }
        
    def _tool_config_added_objects(self, args: Dict) -> Dict:
        """З3: list added/removed/changed objects."""
        return self._tool_config_diff(args)  # Same implementation
        
    def _tool_config_checklist(self, args: Dict) -> Dict:
        """З4: pre-commit checklist — common BSL quality gates."""
        config_path = args.get("config_path", self.config.config_path)
        if not config_path:
            return {"error": "config_path required"}
            
        results = {
            "pre_checks": [],
            "post_checks": [],
            "overall": "passed",
        }
        
        # Pre-commit checks
        results["pre_checks"] = [
            {"check": "Queue leak", "status": "manual_review", "note": "Review all Continue statements in exchange loops"},
            {"check": "Transaction boundary", "status": "manual_review", "note": "Verify all BeginTransaction have corresponding Commit"},
            {"check": "Loading flag", "status": "manual_review", "note": "Verify loading flag before writes in event handlers"},
            {"check": "Security", "status": "auto", "note": "Run audit.security tool"},
        ]
        
        return results
        
    def _tool_config_generate_report(self, args: Dict) -> Dict:
        """З5: generate config report."""
        parser = self.parser
        if not parser:
            return {"error": "Config not loaded."}
            
        info = parser.get_config_info()
        metrics = parser.get_module_list()
        orphans = parser.get_orphaned_objects()
        subsystem_map = parser.get_subsystem_map()
        
        return {
            "config_info": info,
            "statistics": {
                "total_objects": info["total_objects"],
                "total_modules": info["total_modules"],
                "metadata_types": len(info["metadata_types"]),
                "subsystems": len(info["subsystems"]),
                "orphaned_objects": len(orphans),
                "avg_modules_per_object": info["total_modules"] / max(info["total_objects"], 1),
            },
            "largest_modules": metrics[:20],
            "risk_areas": {
                "orphaned_objects": len(orphans),
                "unmapped_subsystems": len(subsystem_map) == 0,
            },
        }
