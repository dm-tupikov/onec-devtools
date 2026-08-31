"""Names exposed by the MCP server."""

AVAILABLE_TOOLS = [
    "meta.tree", "meta.structure", "meta.search", "meta.dependencies", "meta.find_orphans", "meta.compare", "meta.find_undefined_refs", "meta.subsystem_map", "meta.field_usage", "meta.cross_ref",
    "audit.e1_e9", "audit.query_antipatterns", "audit.code_antipatterns", "audit.security", "audit.deprecated_api", "audit.pi_data", "audit.rls_roles", "audit.duplicate_code", "audit.dead_code", "audit.module_complexity", "audit.tms_integration", "audit.exchange_safety", "audit.version_check", "audit.rnd_flag", "audit.transaction_boundary",
    "query.validate", "query.optimize", "query.explain", "query.find_sinks", "query.generate", "query.check_fields", "query.check_dimensions", "query.convert_to_async",
    "epf.validate", "epf.roundtrip_check", "epf.generate", "epf.extract_info", "epf.check_modules", "epf.compare", "epf.validate_rules", "epf.list_commands",
    "form.structure", "form.find_orphans", "form.command_audit", "skd.structure", "skd.check_fields", "skd.compare", "mxl.audit", "form.to_async",
    "exchange.analyze", "xdto.validate", "kshd.contract_check", "integration.retry_policy", "integration.cascade_check", "integration.loop_prevention",
    "test.generate", "test.coverage", "quality.metrics", "quality.bulk_analyze", "quality.gate", "quality.trend",
    "bsl.syntax.help", "bsl.generate_query", "bsl.generate_print_form", "bsl.generate_report", "bsl.convert_modal_async", "bsl.find_synonyms", "bsl.version_check", "config.template_apply",
    "config.diff", "config.validate_build", "config.added_objects", "config.checklist", "config.generate_report",
    "designer.capabilities", "designer.apply_xml_and_build_cf", "ibcmd.capabilities", "ibcmd.run",
]
