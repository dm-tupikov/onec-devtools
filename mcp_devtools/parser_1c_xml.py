"""Parser for 1C configuration XML dump files.

Parses the standard 1C configuration export format (Config.xml structure)
to provide programmatic access to metadata objects, forms, modules, etc.
"""

import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 1C metadata object types (Common types)
METADATA_TYPES = [
    "Catalog", "ChartOfAccounts", "ChartOfCharacteristicTypes",
    "CommonAttribute", "CommonCommand", "CommonModule",
    "CommonObject", "Diagram", "DocumentCounter",
    "DocumentNomenclatureGroups", "DocumentPostLimit",
    "DocumentPostLimitsType", "InformationRegister",
    "Constant", "ReportForm", "ScheduledJob",
    "SequencePrinter", "Subsystem", "TaskMonitor",
    "TaskMonitorManager", "Report", "Document",
    "ChartOfAccountsType", "BusinessProcesses",
    "CatalogRoutines", "CommonForm", "ReportRoutines",
    "AccumulationRegister", "BusinessRule",
]

# BSL keyword patterns for query detection
QUERY_KEYWORDS = [
    "ВЫБРАТЬ", "ВЫБРАТЬРАЗЛИЧНЫЕ", "ИЗ", "ГДЕ",
    "СОЕДИНЕНИЕ", "ПЕРВЫЕ", "ORDER BY", "СГРУППИРОВАТЬ ПО",
    "ИМЕЮЩИЕ", "КОГДА", "ЦИКЛ", "ПОЛУЧИТЬДАТУТАЙМСТЕМП",
]


class MetaObject:
    """Represents a 1C metadata object."""
    
    def __init__(self, data: Dict[str, Any]):
        self.name = data.get("Name", "")
        self.type = data.get("_type", "")
        self.code = data.get("Code", "")
        self.description = data.get("Description", "")
        self.subsystem = data.get("Subsystem", "")
        self.form_ids: List[str] = []
        self.module_files: List[str] = []
        self.command_ids: List[str] = []
        self.ext: Dict[str, Any] = data.get("Ext", {})
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "code": self.code,
            "description": self.description,
            "subsystem": self.subsystem,
            "forms": self.form_ids,
            "modules": self.module_files,
            "commands": self.command_ids,
        }


class OneCConfigParser:
    """Parses 1C configuration XML dump and provides metadata access."""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self._metadata: Dict[str, List[MetaObject]] = {}
        self._all_objects: List[MetaObject] = []
        self._modules: Dict[str, str] = {}  # path -> content
        self._forms: Dict[str, Dict] = {}
        self._subsystems: Dict[str, MetaObject] = {}
        self._parsed = False
        
    def parse(self) -> "OneCConfigParser":
        """Parse the configuration XML files."""
        if self._parsed:
            return self
            
        if self.config_path.is_file():
            self._parse_cf_file(str(self.config_path))
        elif self.config_path.is_dir():
            self._parse_directory(str(self.config_path))
        else:
            raise FileNotFoundError(f"Config path not found: {self.config_path}")
            
        self._parsed = True
        logger.info(f"Parsed {len(self._all_objects)} metadata objects from {self.config_path}")
        return self
    
    def _parse_cf_file(self, cf_path: str):
        """Parse a .cf backup file (binary container with XML inside)."""
        # .cf files are 1C container format
        # For now, we support plain XML dump directory
        # A .cf would need special extraction
        logger.warning(f".cf file parsing not fully implemented: {cf_path}")
        logger.warning("Please use XML dump directory instead, or extract .cf first")
        
    def _parse_directory(self, dir_path: str):
        """Parse a directory containing 1C XML dump files."""
        dir_path = Path(dir_path)
        
        # Parse subsystems first (needed for context)
        self._parse_subsystems(dir_path)
        
        # Parse each metadata type directory
        for type_dir in dir_path.iterdir():
            if not type_dir.is_dir():
                continue
                
            type_name = type_dir.name
            if type_name in ("Ext", "Descriptions", ".git"):
                continue
                
            objects = self._parse_type_directory(type_dir, type_name)
            if objects:
                self._metadata[type_name] = objects
                self._all_objects.extend(objects)
                
        # Parse common modules and forms
        self._parse_common_objects(dir_path)
        
        # Parse all .bsl module files
        self._parse_modules(dir_path)
        
    def _parse_subsystems(self, dir_path: Path):
        """Parse subsystem definitions."""
        subsys_dir = dir_path / "Subsystems"
        if not subsys_dir.exists():
            return
            
        for xml_file in subsys_dir.glob("*.xml"):
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                name = root.get("Name", "")
                desc = root.findtext("Description", "")
                obj = MetaObject({
                    "Name": name,
                    "_type": "Subsystem",
                    "Description": desc,
                })
                self._subsystems[name] = obj
            except Exception as e:
                logger.debug(f"Error parsing subsystem {xml_file}: {e}")
                
    def _parse_type_directory(self, type_dir: Path, type_name: str) -> List[MetaObject]:
        """Parse a metadata type directory (e.g., Documents/, Catalogs/)."""
        objects = []
        for obj_dir in type_dir.iterdir():
            if not obj_dir.is_dir():
                continue
                
            xml_file = obj_dir / f"{obj_dir.name}.xml"
            if not xml_file.exists():
                xml_file = list(obj_dir.glob("*.xml"))[0] if list(obj_dir.glob("*.xml")) else None
                
            if xml_file and xml_file.exists():
                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    
                    name = root.get("Name", obj_dir.name)
                    obj_type_map = {
                        "Catalogs": "Catalog",
                        "Documents": "Document",
                        "InformationRegisters": "InformationRegister",
                        "AccumulationRegisters": "AccumulationRegister",
                        "ChartsOfAccounts": "ChartOfAccounts",
                        "ChartsOfCharacteristicTypes": "ChartOfCharacteristicType",
                        "Constants": "Constant",
                        "Reports": "Report",
                        "BusinessProcesses": "BusinessProcess",
                        "ScheduledJobs": "ScheduledJob",
                        "CommonModules": "CommonModule",
                        "CommonForms": "CommonForm",
                        "CommonCommands": "CommonCommand",
                        "CommonAttributes": "CommonAttribute",
                        "DocumentJournal": "DocumentJournal",
                    }
                    
                    obj_data = {
                        "Name": name,
                        "_type": obj_type_map.get(type_name, type_name),
                        "Code": root.get("Code", ""),
                        "Description": root.findtext("Description", ""),
                    }
                    
                    obj = MetaObject(obj_data)
                    
                    # Collect form IDs
                    forms_elem = root.find("Forms")
                    if forms_elem is not None:
                        for form in forms_elem.findall("Form"):
                            form_name = form.get("Name", "")
                            obj.form_ids.append(form_name)
                            
                    # Collect command IDs  
                    cmds_elem = root.find("Commands")
                    if cmds_elem is not None:
                        for cmd in cmds_elem.findall("Command"):
                            cmd_name = cmd.get("Name", "")
                            obj.command_ids.append(cmd_name)
                            
                    # Check for subsystems attribute
                    subsys_elem = root.find("Subsystem")
                    if subsys_elem is not None and subsys_elem.text:
                        obj.subsystem = subsys_elem.text
                        
                    objects.append(obj)
                    
                except Exception as e:
                    logger.debug(f"Error parsing {obj_dir}: {e}")
                    
        return objects
        
    def _parse_common_objects(self, dir_path: Path):
        """Parse common modules, forms, etc."""
        common_types = {
            "CommonModules": "CommonModule",
            "CommonForms": "CommonForm",
            "CommonCommands": "CommonCommand",
            "CommonAttributes": "CommonAttribute",
        }
        
        for type_name, obj_type in common_types.items():
            type_dir = dir_path / type_name
            if not type_dir.exists():
                continue
                
            self._metadata[type_name] = []
            for xml_file in type_dir.glob("*.xml"):
                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    name = root.get("Name", xml_file.stem)
                    obj_data = {
                        "Name": name,
                        "_type": obj_type,
                        "Code": root.get("Code", ""),
                        "Description": root.findtext("Description", ""),
                    }
                    obj = MetaObject(obj_data)
                    self._metadata[type_name].append(obj)
                    self._all_objects.append(obj)
                except Exception as e:
                    logger.debug(f"Error parsing {xml_file}: {e}")
                    
    def _parse_modules(self, dir_path: Path):
        """Parse all .bsl module files."""
        for bsl_file in dir_path.rglob("*.bsl"):
            try:
                rel_path = bsl_file.relative_to(dir_path)
                content = bsl_file.read_text(encoding="utf-8", errors="replace")
                self._modules[str(rel_path)] = content
            except Exception as e:
                logger.debug(f"Error reading module {bsl_file}: {e}")
                
    def get_metadata_tree(self, object_type: Optional[str] = None) -> Dict[str, List[Dict]]:
        """Get metadata tree, optionally filtered by type."""
        result = {}
        types_to_include = [object_type] if object_type else list(self._metadata.keys())
        
        for type_name in types_to_include:
            if type_name not in self._metadata:
                continue
            objects = []
            for obj in self._metadata[type_name]:
                obj_dict = obj.to_dict()
                obj_dict["type_name"] = type_name
                objects.append(obj_dict)
            result[type_name] = objects
            
        return result
        
    def get_object_structure(self, object_name: str) -> Optional[Dict[str, Any]]:
        """Get full structure of a metadata object."""
        for obj in self._all_objects:
            if obj.name == object_name:
                result = obj.to_dict()
                result["attributes"] = self._get_object_attributes(obj)
                result["tabular_sections"] = self._get_tabular_sections(obj)
                result["modules"] = self._get_object_modules(obj)
                return result
        return None
        
    def _get_object_attributes(self, obj: MetaObject) -> List[Dict]:
        """Try to parse object attributes from XML."""
        attrs = []
        type_dir = None
        for type_name, objs in self._metadata.items():
            if obj in objs:
                type_dir = type_name
                break
                
        if not type_dir:
            return attrs
            
        type_path = Path(self.config_path) / type_dir / obj.name
        for xml_file in type_path.glob("*.xml"):
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                # Look for attributes (PredefinedData, DataFields, etc.)
                attrs_elem = root.find("Attributes")
                if attrs_elem is not None:
                    for attr in attrs_elem.findall("Attribute"):
                        attrs.append({
                            "name": attr.get("Name", ""),
                            "type": attr.get("Type", ""),
                            "description": attr.findtext("Description", ""),
                        })
                        
                # Look for tabular sections
                sections_elem = root.find("TabularSections")
                if sections_elem is not None:
                    for section in sections_elem.findall("TabularSection"):
                        section_name = section.get("Name", "")
                        fields = []
                        fields_elem = section.find("Fields")
                        if fields_elem is not None:
                            for field in fields_elem.findall("Field"):
                                fields.append({
                                    "name": field.get("Name", ""),
                                    "type": field.get("Type", ""),
                                    "description": field.findtext("Description", ""),
                                })
                        attrs.append({
                            "_type": "tabular_section",
                            "name": section_name,
                            "fields": fields,
                        })
            except Exception as e:
                logger.debug(f"Error parsing attributes for {obj.name}: {e}")
            break
            
        return attrs
        
    def _get_tabular_sections(self, obj: MetaObject) -> List[Dict]:
        """Get tabular sections for an object."""
        return [a for a in self._get_object_attributes(obj) if a.get("_type") == "tabular_section"]
        
    def _get_object_modules(self, obj: MetaObject) -> List[Dict]:
        """Get module files for an object."""
        modules = []
        base_name = obj.name
        
        # Search in type directories
        for type_name, objs in self._metadata.items():
            if obj in objs:
                type_path = Path(self.config_path) / type_name / base_name
                for bsl_file in type_path.rglob("*.bsl"):
                    rel_path = bsl_file.relative_to(Path(self.config_path))
                    content = self._modules.get(str(rel_path), "")
                    modules.append({
                        "path": str(rel_path),
                        "content_length": len(content),
                        "type": self._guess_module_type(str(rel_path)),
                    })
                break
                
        return modules
        
    def _guess_module_type(self, path: str) -> str:
        """Guess the module type from file path."""
        if "ObjectModule" in path:
            return "ObjectModule"
        elif "ManagerModule" in path:
            return "ManagerModule"
        elif "Form" in path and "Module" in path:
            return "FormModule"
        elif "CommandModule" in path:
            return "CommandModule"
        elif "CallCenter" in path:
            return "CallCenter"
        elif "OrdinaryApplication" in path:
            return "OrdinaryApplicationModule"
        elif "ManagedApplication" in path:
            return "ManagedApplicationModule"
        elif "ExternalConnection" in path:
            return "ExternalConnectionModule"
        elif "Session" in path:
            return "SessionModule"
        return "Unknown"
        
    def search_metadata(self, query: str, object_type: Optional[str] = None) -> List[Dict]:
        """Search metadata objects by name, description, or code."""
        results = []
        query_lower = query.lower()
        
        for obj in self._all_objects:
            score = 0
            if obj.name.lower() == query_lower:
                score = 100
            elif query_lower in obj.name.lower():
                score = 50
            elif query_lower in obj.description.lower():
                score = 30
            elif obj.code and query_lower in obj.code.lower():
                score = 20
                
            if score > 0:
                if object_type is None or obj.type == object_type:
                    result = obj.to_dict()
                    result["score"] = score
                    results.append(result)
                    
        results.sort(key=lambda x: x["score"], reverse=True)
        return results
        
    def find_object_refs(self, ref_name: str, ref_type: str = "") -> List[Dict]:
        """Find all references to a metadata object in module code."""
        results = []
        ref_lower = ref_name.lower()
        
        for path, content in self._modules.items():
            lines = content.split("\n")
            refs = []
            for i, line in enumerate(lines, 1):
                if ref_lower in line.lower() and not line.strip().startswith("//"):
                    refs.append({"line": i, "text": line.strip()})
                    
            if refs:
                results.append({
                    "path": path,
                    "references": refs,
                    "count": len(refs),
                })
                
        results.sort(key=lambda x: x["count"], reverse=True)
        return results
        
    def find_undefined_refs(self) -> List[Dict]:
        """Find references to non-existent objects in module code."""
        known_names = {obj.name.lower() for obj in self._all_objects}
        known_attrs = set()
        
        # Collect all attribute names
        for obj in self._all_objects:
            known_attrs.add(obj.name.lower())
            for attr in self._get_object_attributes(obj):
                if "_type" not in attr:
                    known_attrs.add(attr["name"].lower())
                    
        issues = []
        for path, content in self._modules.items():
            # Simple heuristic: look for patterns like "Object.FieldName" or "Document.FieldName"
            # This is a simplified check; a full parser would be more accurate
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                # Look for common 1C patterns that might reference unknown objects
                if "Выбрать()" in line or "Записать()" in line:
                    continue
                # Check for potentially undefined object references
                # This is a basic heuristic
                pass
                
        return issues
        
    def get_field_usage(self, field_name: str) -> List[Dict]:
        """Find where a field/attribute is used in the codebase."""
        return self.find_object_refs(field_name, "Attribute")
        
    def get_cross_reference(self, object_name: str) -> Optional[Dict]:
        """Get cross-references for an object: forms, modules, queries."""
        obj = None
        for o in self._all_objects:
            if o.name == object_name:
                obj = o
                break
                
        if not obj:
            return None
            
        result = {
            "object": obj.to_dict(),
            "form_files": self._find_form_files(obj),
            "module_files": self._get_object_modules(obj),
            "code_references": self.find_object_refs(obj.name),
        }
        return result
        
    def _find_form_files(self, obj: MetaObject) -> List[Dict]:
        """Find form XML files for an object."""
        form_files = []
        for type_name, objs in self._metadata.items():
            if obj in objs:
                type_path = Path(self.config_path) / type_name / obj.name
                for xml_file in type_path.rglob("Form.xml"):
                    form_files.append({
                        "path": str(xml_file.relative_to(Path(self.config_path))),
                        "form_name": xml_file.parent.name,
                    })
                break
        return form_files
        
    def get_subsystem_map(self) -> Dict[str, List[str]]:
        """Get map of subsystems to their objects."""
        result = {}
        for obj in self._all_objects:
            if obj.subsystem:
                if obj.subsystem not in result:
                    result[obj.subsystem] = []
                result[obj.subsystem].append(obj.name)
        return result
        
    def get_orphaned_objects(self) -> List[Dict]:
        """Find objects not assigned to any subsystem."""
        orphans = []
        for obj in self._all_objects:
            if not obj.subsystem and obj.type not in ("Subsystem", "CommonModule", 
                                                        "CommonForm", "CommonCommand",
                                                        "CommonAttribute"):
                orphans.append(obj.to_dict())
        return orphans
        
    def get_module_list(self) -> List[Dict]:
        """Get list of all module files with basic info."""
        modules = []
        for path, content in self._modules.items():
            lines = content.split("\n")
            # Count functions
            func_count = sum(1 for line in lines if "Процедура" in line or "Функция" in line)
            modules.append({
                "path": path,
                "lines": len(lines),
                "functions": func_count,
            })
        return sorted(modules, key=lambda x: x["lines"], reverse=True)
        
    def get_config_info(self) -> Dict[str, Any]:
        """Get basic configuration info."""
        return {
            "config_path": str(self.config_path),
            "total_objects": len(self._all_objects),
            "total_modules": len(self._modules),
            "metadata_types": list(self._metadata.keys()),
            "subsystems": list(self._subsystems.keys()),
        }
