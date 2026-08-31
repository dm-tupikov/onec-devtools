"""EPF (External Data Processor) tools for 1C configuration."""

import base64
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def validate_epf(epf_path: str) -> Dict[str, Any]:
    """Validate an EPF file's binary header.
    
    1C container files start with: \xff\xff\xff\x7f\x00\x02\x00\x00
    """
    result = {
        "valid": False,
        "path": epf_path,
        "size": 0,
        "header": "",
        "issues": [],
    }
    
    path = Path(epf_path)
    if not path.exists():
        result["issues"].append(f"Файл не найден: {epf_path}")
        return result
        
    result["size"] = path.stat().st_size
    
    try:
        with open(path, "rb") as f:
            header = f.read(8)
            result["header"] = header.hex()
            
            # Check for 1C container format
            known_headers = [
                b"\xff\xff\xff\x7f\x00\x02\x00\x00",  # 1C container
                b"\x1f\x8b",  # gzip (sometimes used)
                b"PK",  # ZIP (sometimes used for CF)
                b"\xd0\xcf\x11\xe0",  # OLE (sometimes used)
            ]
            
            is_valid = any(header.startswith(h) for h in known_headers)
            result["valid"] = is_valid
            
            if is_valid:
                result["issues"].append("Бинарный заголовок валиден")
            else:
                result["issues"].append("Бинарный заголовок не соответствует формату 1С")
                
    except Exception as e:
        result["issues"].append(f"Ошибка чтения файла: {e}")
        
    return result


def extract_epf_info(epf_path: str) -> Dict[str, Any]:
    """Extract metadata from an EPF file (requires headless 1C)."""
    result = {
        "path": epf_path,
        "modules": [],
        "forms": [],
        "commands": [],
        "version": "",
        "description": "",
    }
    
    # Try to read as XML dump first
    path = Path(epf_path)
    if path.suffix in (".xml", ""):
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            # Look for version info
            import re
            version_match = re.search(r'Вери(\w*?)сь\s*=\s*"([^"]+)"', content)
            if version_match:
                result["version"] = version_match.group(2)
        except Exception:
            pass
            
    return result


def build_epf_roundtrip_check(epf_path: str, config_path: str, 
                               headless_1c_path: str = "", 
                               test_base: str = "") -> Dict[str, Any]:
    """Perform round-trip check: build EPF -> dump -> compare.
    
    Gold standard for 1C artifact verification.
    """
    result = {
        "passed": False,
        "steps": [],
        "diff_lines": 0,
        "issues": [],
    }
    
    if not os.environ.get("ONEC_DEVTOOLS_TEST_BASE"):
        result["issues"].append("Для round-trip проверки требуется настройка тестовой базы: ONEC_DEVTOOLS_TEST_BASE")
        result["issues"].append("Например: Srvr=D021CUATAPP01D;Ref=UAT_Tupikov_TEST_01")
        return result
        
    # Step 1: Extract current EPF content
    epf_path = Path(epf_path)
    if not epf_path.exists():
        result["issues"].append(f"EPF файл не найден: {epf_path}")
        return result
        
    result["steps"].append({"step": "validate_epf", "status": "ok"})
    
    # Step 2: Build EPF against test base (headless)
    # This step requires 1C server access
    test_base = os.environ.get("ONEC_DEVTOOLS_TEST_BASE", test_base)
    if not test_base:
        result["issues"].append("Не указана тестовая база 1С")
        result["passed"] = False
        return result
        
    # The actual headless build would use:
    # 1cv8.exe DESIGNER /S <server>/<ref> /DumpExternalDataProcessorOrReportToFiles <temp_epf>
    
    result["steps"].append({"step": "build_epf", "status": "skipped", 
                            "note": "Requires 1C server access"})
    result["steps"].append({"step": "dump_epf", "status": "skipped",
                            "note": "Requires 1C server access"})
    result["steps"].append({"step": "compare", "status": "skipped",
                            "note": "Requires dump completion"})
                            
    result["passed"] = False
    return result


def check_epf_modules_complete(epf_path: str) -> Dict[str, Any]:
    """Check if all expected modules are present in an EPF.
    
    Standard structure:
    - Ext/ObjectModule.bsl
    - Ext/ManagerModule.bsl
    - Forms/Форма/Ext/Form.xml
    - Forms/Форма/Module.bsl
    """
    result = {
        "complete": True,
        "expected_modules": [],
        "found_modules": [],
        "missing_modules": [],
    }
    
    # Check if it's a directory structure
    path = Path(epf_path)
    if path.is_dir():
        # Check for standard module files
        expected = [
            "Ext/ObjectModule.bsl",
            "Ext/ManagerModule.bsl",
            "Ext/ExternalDataHandlers.bsl",
            "Forms/",
        ]
        found = []
        missing = []
        
        for exp in expected:
            if (path / exp).exists():
                found.append(exp)
            else:
                missing.append(exp)
                result["complete"] = False
                
        result["expected_modules"] = expected
        result["found_modules"] = found
        result["missing_modules"] = missing
        
    else:
        result["expected_modules"] = ["EPF must be extracted first"]
        result["issues"] = ["EPF файл не распакован. Используйте .xml-дамп."]
        
    return result


def compare_epfs(epf1_path: str, epf2_path: str) -> Dict[str, Any]:
    """Compare two EPF files (after extraction)."""
    result = {
        "different": False,
        "added_modules": [],
        "removed_modules": [],
        "modified_modules": [],
    }
    
    path1 = Path(epf1_path)
    path2 = Path(epf2_path)
    
    if not path1.is_dir() or not path2.is_dir():
        result["issues"] = ["Оба EPF должны быть распакованы в директории"]
        return result
        
    # Get all .bsl and .xml files
    files1 = set()
    files2 = set()
    
    for f in path1.rglob("*"):
        if f.suffix in (".bsl", ".xml", ".frm"):
            files1.add(f.relative_to(path1))
            
    for f in path2.rglob("*"):
        if f.suffix in (".bsl", ".xml", ".frm"):
            files2.add(f.relative_to(path2))
            
    added = files2 - files1
    removed = files1 - files2
    common = files1 & files2
    
    modified = []
    for f in common:
        f1 = path1 / f
        f2 = path2 / f
        try:
            c1 = f1.read_text(encoding="utf-8", errors="replace")
            c2 = f2.read_text(encoding="utf-8", errors="replace")
            if c1 != c2:
                modified.append(str(f))
        except Exception:
            pass
            
    result["different"] = bool(added or removed or modified)
    result["added_modules"] = [str(f) for f in added]
    result["removed_modules"] = [str(f) for f in removed]
    result["modified_modules"] = modified
    
    return result
