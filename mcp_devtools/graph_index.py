"""Graph index over a 1C configuration XML dump.

Builds a call/reference graph from the same XML dump the existing
OneCConfigParser consumes: metadata objects are vertices, calls and
code/query references are edges. Powers graph.calls / graph.impact /
graph.search MCP tools.

Design notes:
- No external dependencies: stdlib re + the existing parser.
- Module discovery reuses OneCConfigParser._parse_modules so both plain
  dumps (CommonModules/<Name>/Ext/Module.bsl) and object-module layouts
  are covered the same way meta.* tools already see them.
- BSL call extraction is heuristic-by-line (the same evidence level as
  find_object_refs), but every edge carries its evidence: file, line,
  matched text. Nothing is invented.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .parser_1c_xml import OneCConfigParser

# Standard dump layout: plural directory name -> metadata type
# used for module owner resolution from module paths.
DUMP_DIR_TO_TYPE = {
    "Catalogs": "Catalog",
    "Documents": "Document",
    "DocumentJournals": "DocumentJournal",
    "InformationRegisters": "InformationRegister",
    "AccumulationRegisters": "AccumulationRegister",
    "AccountingRegisters": "AccountingRegister",
    "CalculationRegisters": "CalculationRegister",
    "ChartsOfAccounts": "ChartOfAccounts",
    "ChartsOfCharacteristicTypes": "ChartOfCharacteristicType",
    "ChartsOfCalculationTypes": "ChartOfCalculationType",
    "Constants": "Constant",
    "Reports": "Report",
    "DataProcessors": "DataProcessor",
    "BusinessProcesses": "BusinessProcess",
    "Tasks": "Task",
    "Enums": "Enum",
    "ExchangePlans": "ExchangePlan",
    "ScheduledJobs": "ScheduledJob",
    "Sequences": "Sequence",
    "SettingsStorages": "SettingsStorage",
    "CommonModules": "CommonModule",
    "CommonForms": "CommonForm",
    "CommonCommands": "CommonCommand",
    "CommonAttributes": "CommonAttribute",
    "CommonTemplates": "CommonTemplate",
    "CommonPictures": "CommonPicture",
    "DefinedTypes": "DefinedType",
    "EventSubscriptions": "EventSubscription",
    "FilterCriteria": "FilterCriterion",
    "FunctionalOptions": "FunctionalOption",
    "FunctionalOptionsParameters": "FunctionalOptionParameter",
    "Roles": "Role",
    "Subsystems": "Subsystem",
    "WSReferences": "WSReference",
    "XDTOPackages": "XDTOPackage",
}

# Procedure/function definition: ИмяПроцедуры(/*
Procedure_RE = re.compile(r"^\s*(?:процедура|функция|proc|func)\s+([A-Za-zА-Яа-яЁё0-9_]+)", re.IGNORECASE)

# A call: Имя( — excludes keywords that only look like calls
_CALL_KEYWORDS = {
    "если", "иначе", "иначеесли", "конецесли", "тогда", "цикл", "конеццикла",
    "попытка", "исключение", "конецпопытки", "вызватьисключение", "прервать",
    "продолжить", "возврат", "новый", "перейти", "выполнить",
}
Call_RE = re.compile(r"([A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)\s*\(")

# Context access patterns: Модуль.Функция(...) / ОбъектМодуль.Метод(...)
Dotted_RE = re.compile(r"([A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)\.([A-Za-zА-Яа-яЁё0-9_]*)")

# Platform collection access: РегистрыНакопления.ИмяРегистра.Метод(...)
CollectionAccess_RE = re.compile(
    r"\b(РегистрыНакопления|РегистрыСведений|РегистрыБухгалтерии|РегистрыРасчета|Справочники|Документы|"
    r"Отчеты|Обработки|Перечисления|ПланыСчетов|ПланыВидовХарактеристик|ПланыОбмена|ПланыВидовРасчета|"
    r"БизнесПроцессы|Задачи|Константы)\.([A-Za-zА-Яа-яЁё0-9_]+)",
    re.IGNORECASE,
)
CollectionPrefixByType = {
    "РегистрыНакопления": "AccumulationRegister",
    "РегистрыСведений": "InformationRegister",
    "РегистрыБухгалтерии": "AccountingRegister",
    "РегистрыРасчета": "CalculationRegister",
    "Справочники": "Catalog",
    "Документы": "Document",
    "Отчеты": "Report",
    "Обработки": "DataProcessor",
    "Перечисления": "Enum",
    "ПланыСчетов": "ChartOfAccounts",
    "ПланыВидовХарактеристик": "ChartOfCharacteristicType",
    "ПланыОбмена": "ExchangePlan",
    "ПланыВидовРасчета": "ChartOfCalculationType",
    "БизнесПроцессы": "BusinessProcess",
    "Задачи": "Task",
    "Константы": "Constant",
}

# Document posting: Движения.ИмяРегистраНакопления.Метод (record sets from document modules)
Movements_RE = re.compile(r"\bДвижения\.([A-Za-zА-Яа-яЁё0-9_]+)", re.IGNORECASE)

# Query source tables: ИЗ Справочник.Контрагенты / .ТабличнаяЧасть.Х
QuerySource_RE = re.compile(
    r"\b(?:из|from|соединение|join)\s+"
    r"((?:справочник|документ|регистрсведений|регистрнакопления|регистрбухгалтерии|регистррасчета|"
    r"перечисление|плансчетов|планвидовхарактеристик|планобмена|планвидоврасчета|бизнеспроцесс|задача|"
    r"пакет|константа)\.[A-Za-zА-Яа-яЁё0-9_]+(?:\.[A-Za-zА-Яа-яЁё0-9_]+)*)",
    re.IGNORECASE,
)


def _norm(name: str) -> str:
    return name.strip().lower()


class GraphIndex:
    """Call/reference graph over a parsed 1C configuration dump."""

    def __init__(self, parser: OneCConfigParser):
        self.parser = parser
        self.vertices: Dict[str, Dict[str, Any]] = {}      # key: type:Name (normed)
        self.by_name: Dict[str, List[str]] = defaultdict(list)  # normed name -> vertex keys
        self.module_owner: Dict[str, str] = {}             # module path -> vertex key
        self.procedures: Dict[str, Dict[str, Any]] = {}    # proc fq name -> info
        self.proc_by_module: Dict[str, List[str]] = defaultdict(list)
        self.call_edges: List[Dict[str, Any]] = []         # code calls
        self.ref_edges: List[Dict[str, Any]] = []          # metadata refs from code
        self.query_edges: List[Dict[str, Any]] = []        # tables used in queries
        self._built = False

    # ---------- building ----------

    def build(self) -> "GraphIndex":
        if self._built:
            return self
        p = self.parser
        p.parse()

        # vertices from metadata objects
        for obj in p._all_objects:
            key = f"{obj.type}:{obj.name}"
            if key in self.vertices:  # same type:name seen twice — keep first
                continue
            v = {
                "key": key,
                "type": obj.type,
                "name": obj.name,
                "description": obj.description,
                "modules": [],
                "procedures": [],
            }
            self.vertices[key] = v
            self.by_name[_norm(obj.name)].append(key)
            for m in getattr(obj, "module_files", ()) or ():
                self.module_owner[str(m)] = key
                v["modules"].append(str(m))

        # owner resolution by dump path prefix: <TypeDir>/<ObjName>/...
        # (the standard "Выгрузка конфигурации в файлы" layout)
        dir_to_type = getattr(p, "DUMP_DIR_TO_TYPE", None)
        if not dir_to_type:
            dir_to_type = DUMP_DIR_TO_TYPE
        type_dir_names = set(dir_to_type.keys())

        for path in p._modules:
            path = str(path)
            owner = self.module_owner.get(path)
            if owner:
                continue
            parts = Path(path).parts
            # find the metadata type directory in the path and take the next segment as owner
            for i, seg in enumerate(parts):
                if seg in type_dir_names and i + 1 < len(parts):
                    objname = parts[i + 1]
                    # resolve by name -> vertex keys; prefer exact type match
                    keys = self.by_name.get(_norm(objname), [])
                    want = dir_to_type.get(seg, "")
                    key = None
                    for k in keys:
                        vt = self.vertices[k]["type"]
                        if vt == want or vt == seg or vt + "s" == seg:
                            key = k
                            break
                    if key is None and len(keys) == 1:
                        key = keys[0]
                    if key is None:
                        # module without a metadata object (e.g. Configuration session module)
                        key = f"Module:{objname}"
                        self.vertices.setdefault(
                            key,
                            {"key": key, "type": "Module", "name": objname, "description": "", "modules": [], "procedures": []},
                        )
                        self.by_name[_norm(objname)].append(key)
                    self.module_owner[path] = key
                    self.vertices[key]["modules"].append(path)
                    break
            else:
                # no type dir in path: top-level module (session/external connection)
                key = f"Module:{Path(path).stem or path}"
                if key not in self.vertices:
                    self.vertices[key] = {"key": key, "type": "Module", "name": Path(path).stem, "description": "", "modules": [path], "procedures": []}
                    self.by_name[_norm(Path(path).stem)].append(key)
                self.module_owner[path] = key

        # procedures and calls per module
        for path, content in p._modules.items():
            path = str(path)
            owner = self.module_owner.get(path, "")
            self._scan_module(path, owner, content)

        self._built = True
        return self

    def _scan_module(self, path: str, owner: str, content: str) -> None:
        lines = content.splitlines()
        current_proc = None

        for lineno, raw in enumerate(lines, 1):
            line = raw.strip()

            # procedure boundaries
            m = Procedure_RE.match(line)
            if m:
                pname = m.group(1)
                fq = f"{owner}#{pname}" if owner else f"{path}#{pname}"
                current_proc = fq
                info = self.procedures.setdefault(
                    fq,
                    {"name": pname, "module": path, "owner": owner, "line": lineno, "calls": 0},
                )
                if owner and owner in self.vertices:
                    self.vertices[owner]["procedures"].append(fq)
                self.proc_by_module[path].append(fq)
                continue
            if re.match(r"^\s*(?:конецпроцедуры|конецфункции|endprocedure|endfunction)\s*;?", line, re.IGNORECASE):
                current_proc = None
                continue

            # calls on this line
            for cm in Call_RE.finditer(raw):
                callee = cm.group(1)
                if _norm(callee) in _CALL_KEYWORDS:
                    continue
                self.call_edges.append(
                    {
                        "from_proc": current_proc or f"{path}#(module)",
                        "from_module": path,
                        "from_owner": owner,
                        "callee": callee,
                        "line": lineno,
                        "text": raw.strip()[:200],
                    }
                )

            # metadata references: ObjectName mentioned with context
            for dm in Dotted_RE.finditer(raw):
                head = dm.group(1)
                for vkey in self.by_name.get(_norm(head), ()):
                    if vkey == owner:
                        continue
                    self.ref_edges.append(
                        {"from_module": path, "from_owner": owner, "from_proc": current_proc, "target": vkey, "line": lineno, "text": raw.strip()[:200]}
                    )

            # platform collection access: РегистрыНакопления.ИмяРегистра.Метод()
            for cm_ in CollectionAccess_RE.finditer(raw):
                coll, objname = cm_.group(1), cm_.group(2)
                want_type = None
                for word, prefix in CollectionPrefixByType.items():
                    if word.lower() == coll.lower():
                        want_type = prefix
                        break
                if want_type is None:
                    continue
                target_key = f"{want_type}:{objname}"
                if target_key in self.vertices and target_key != owner:
                    self.ref_edges.append(
                        {
                            "from_module": path,
                            "from_owner": owner,
                            "from_proc": current_proc,
                            "target": target_key,
                            "kind": "collection",
                            "line": lineno,
                            "text": raw.strip()[:200],
                        }
                    )

            # document movements: Движения.ИмяРегистра.Метод()
            for mm in Movements_RE.finditer(raw):
                target_key = f"AccumulationRegister:{mm.group(1)}"
                if target_key in self.vertices and target_key != owner:
                    self.ref_edges.append(
                        {
                            "from_module": path,
                            "from_owner": owner,
                            "from_proc": current_proc,
                            "target": target_key,
                            "kind": "movement",
                            "line": lineno,
                            "text": raw.strip()[:200],
                        }
                    )

            # query tables
            for qm in QuerySource_RE.finditer(raw):
                table = qm.group(1)
                parts = table.split(".")
                if len(parts) >= 2:
                    for vkey in self.by_name.get(_norm(parts[1]), ()):
                        self.ref_edges.append(
                            {
                                "from_module": path,
                                "from_owner": owner,
                                "from_proc": current_proc,
                                "target": vkey,
                                "kind": "query",
                                "line": lineno,
                                "text": raw.strip()[:200],
                            }
                        )
                        break

    # ---------- queries ----------

    def resolve(self, name: str, obj_type: str = "") -> List[str]:
        """Resolve a name (case-insensitive) to vertex keys."""
        keys = self.by_name.get(_norm(name), [])
        if obj_type:
            keys = [k for k in keys if self.vertices[k]["type"].lower() == obj_type.lower()]
        return keys

    def _resolve_one(self, name: str, obj_type: str = "") -> Optional[str]:
        keys = self.resolve(name, obj_type)
        return keys[0] if len(keys) == 1 else None

    def calls(self, name: str, direction: str = "out", obj_type: str = "", limit: int = 50) -> Dict[str, Any]:
        """Direct calls of/to procedures whose owner object matches name."""
        vkey = self._resolve_one(name, obj_type)
        if not vkey:
            return {"error": f"object not found or ambiguous: {name}"}
        out: List[Dict] = []
        if direction in ("out", "both"):
            for fq, info in self.procedures.items():
                if info["owner"] != vkey:
                    continue
                for e in self.call_edges:
                    if e["from_proc"] == fq:
                        out.append(
                            {
                                "proc": info["name"],
                                "callee": e["callee"],
                                "resolved": self._resolve_callee(e["callee"], fq),
                                "line": e["line"],
                                "module": e["from_module"],
                                "text": e["text"],
                            }
                        )
        inc: List[Dict] = []
        if direction in ("in", "both"):
            # callers that call any procedure defined in this object's modules
            owner_procs = {fq for fq, info in self.procedures.items() if info["owner"] == vkey}
            owner_proc_names = {self.procedures[fq]["name"].lower() for fq in owner_procs}
            seen: Set[Tuple[str, str, int]] = set()
            for e in self.call_edges:
                if e["callee"].lower() in owner_proc_names:
                    t = (e["from_module"], e["callee"], e["line"])
                    if t in seen:
                        continue
                    seen.add(t)
                    inc.append(
                        {
                            "callee": e["callee"],
                            "caller_module": e["from_module"],
                            "caller_owner": e["from_owner"],
                            "caller_proc": e["from_proc"],
                            "line": e["line"],
                            "text": e["text"],
                        }
                    )
        out = out[:limit]
        inc = inc[:limit]
        return {"object": vkey, "outgoing": out, "incoming": inc}

    def _resolve_callee(self, callee: str, from_fq: str) -> Optional[str]:
        """Best-effort callee resolution: local module first, then common modules."""
        cl = callee.lower()
        from_module = self.procedures.get(from_fq, {}).get("module", "")
        # same module
        for fq, info in self.procedures.items():
            if info["module"] == from_module and info["name"].lower() == cl:
                return fq
        # common modules (BSL: ОбщийМодуль.ИмяПроцедуры)
        for fq, info in self.procedures.items():
            if info["name"].lower() == cl and info["owner"].startswith("CommonModule:"):
                return fq
        return None

    def impact(self, name: str, obj_type: str = "", depth: int = 2, limit: int = 100) -> Dict[str, Any]:
        """BFS over reverse edges: what is affected if this object changes."""
        start = self._resolve_one(name, obj_type)
        if not start:
            return {"error": f"object not found or ambiguous: {name}"}

        # reverse adjacency from ref edges + incoming calls
        preds: Dict[str, Set[str]] = defaultdict(set)
        for e in self.ref_edges:
            if e["target"] == e["from_owner"]:
                continue
            if e["target"] in self.vertices and e["from_owner"] in self.vertices:
                preds[e["target"]].add(e["from_owner"])

        visited: Dict[str, int] = {start: 0}
        frontier = [start]
        found: List[Dict] = []
        d = 0
        while frontier and d < depth:
            d += 1
            nxt: List[str] = []
            for node in frontier:
                for pred in preds.get(node, ()):
                    if pred in visited:
                        continue
                    visited[pred] = d
                    v = self.vertices.get(pred, {})
                    found.append(
                        {
                            "key": pred,
                            "type": v.get("type", ""),
                            "name": v.get("name", pred),
                            "depth": d,
                            "reason": f"ссылается на {node}",
                        }
                    )
                    nxt.append(pred)
            frontier = nxt
            if len(found) >= limit:
                break
        return {
            "object": start,
            "affected": found[:limit],
            "truncated": len(found) >= limit,
            "stats": {"vertices": len(self.vertices), "call_edges": len(self.call_edges), "ref_edges": len(self.ref_edges)},
        }

    def search(self, query: str, obj_type: str = "", limit: int = 20) -> Dict[str, Any]:
        """Search vertices by name/description substring."""
        q = _norm(query)
        hits: List[Dict] = []
        for v in self.vertices.values():
            if obj_type and v["type"].lower() != obj_type.lower():
                continue
            if q in _norm(v["name"]) or (v.get("description") and q in _norm(v["description"])):
                hits.append(
                    {
                        "key": v["key"],
                        "type": v["type"],
                        "name": v["name"],
                        "description": (v.get("description") or "")[:120],
                        "modules": len(v["modules"]),
                        "procedures": len(v["procedures"]),
                    }
                )
                if len(hits) >= limit:
                    break
        return {"query": query, "hits": hits}

    def stats(self) -> Dict[str, Any]:
        return {
            "vertices": len(self.vertices),
            "procedures": len(self.procedures),
            "call_edges": len(self.call_edges),
            "ref_edges": len(self.ref_edges),
            "modules": len(self.module_owner),
        }
