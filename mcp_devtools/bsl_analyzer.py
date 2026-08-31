"""BSL/1C query analyzer for static analysis.

Provides query parsing, anti-pattern detection, and code analysis
for 1C Enterprise (BSL - Business Languages) code.
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """Analyzes 1C query syntax and detects anti-patterns."""
    
    # Common query anti-patterns
    ANTI_PATTERNS = {
        "no_first": {
            "pattern": r"ВЫБРАТЬ\s+(?!РАЗЛИЧНЫЕ)(?!ПЕРВЫЕ)[\w\s,.*]+?\s+ИЗ",
            "message": "Отсутствует ПЕРВЫЕ N — выборка всех записей",
            "severity": "warning",
        },
        "select_all": {
            "pattern": r"ВЫБРАТЬ\s+(?!РАЗЛИЧНЫЕ)[\w\s,]*\.\*",
            "message": "Используется SELECT * — рекомендуется явное перечисление полей",
            "severity": "info",
        },
        "no_where": {
            "pattern": r"ВЫБРАТЬ[\s\S]{0,200}?ИЗ\s+[\w\s,]+?\s+(?!ГДЕ)(?!ПЕРВЫЕ)(?!ORDER)",
            "message": "Отсутствует фильтр ГДЕ — полная выборка таблицы",
            "severity": "warning",
        },
        "duplicate_left_join": {
            "pattern": r"ЛЕВОЕ\tСОЕДИНЕНИЕ\s+([\w.]+)\s+\(([\w.]+)\s+ЛЕВОЕ\s+СОЕДИНЕНИЕ",
            "message": "Возможна дублирующая левая связь — проверьте ключи",
            "severity": "info",
        },
        "subquery_in_select": {
            "pattern": r"ВЫБРАТЬ\s+\(ВЫБРАТЬ",
            "message": "Подзапрос в секции ВЫБРАТЬ — может быть медленным",
            "severity": "warning",
        },
        "string_compare": {
            "pattern": r"(=|!=|<>)\s*['\"]",
            "message": "Строковое сравнение в фильтре — используйте параметры",
            "severity": "info",
        },
        "like_concat": {
            "pattern": r"([\w.]+)\s+(НЕ\s+)?ПОДОБНО\s+['\"]",
            "message": "Использование ПОДОБНО с константой — проверьте производительность",
            "severity": "info",
        },
        "not_in_subquery": {
            "pattern": r"НЕ\s+В\s+\(ВЫБРАТЬ",
            "message": "Использование НЕ В (ВЫБРАТЬ) — рассмотрите КАК НЕЛЬЗЯ или ЛЕВОЕ СОЕДИНЕНИЕ",
            "severity": "warning",
        },
        "order_by_non_indexed": {
            "pattern": r"ORDER\s+BY\s+([\w.]+)",
            "message": "ORDER BY — убедитесь, что поле проиндексировано",
            "severity": "info",
        },
        "no_group_having": {
            "pattern": r"СГРУППИРОВАТЬ\s+ПО\s+([\w.]+)[\s\S]*?(?!HAVING)",
            "message": "Группировка без HAVING — возможно, нужна дополнительная фильтрация",
            "severity": "info",
        },
        "cast_in_where": {
            "pattern": r"ГДЕ\s+([\w.]+)\s+(НЕ\s+)?(ЗАМЕНИТЬ|ПРЕДСТАВИТЬИНТ|ПРЕДСТАВИТЬНОМЕР)\(",
            "message": "Функция в ГДЕ по полю — индекс не будет использоваться",
            "severity": "warning",
        },
        "empty_period": {
            "pattern": r"([\w.]+)\s+(МЕЖДУ|>=|<=)\s+ПЕРВОЙДАТЫ\(ПЕРИОДА\)",
            "message": "Проверьте обработку пустого периода",
            "severity": "info",
        },
        "fetch_top_without_period": {
            "pattern": r"ПЕРВЫЕ\s+\d+\s*.*?ИЗ\s+[\w.]+\s+(?!ПЕРИОДА)",
            "message": "ПЕРВЫЕ без ПЕРИОДА — может вернуть разные результаты при повторном запуске",
            "severity": "warning",
        },
        "max_rows_missing": {
            "pattern": r"ВЫБРАТЬ\s+(?!РАЗЛИЧНЫЕ)(?!ПЕРВЫЕ)[\w\s,]+?\s+ИЗ\s+[\w.]+\s+ГДЕ\s+([\w.]+)\s+=",
            "message": "Рекомендуется ограничить выборку ПЕРВЫЕ для больших таблиц",
            "severity": "info",
        },
        "sync_call_pattern": {
            "pattern": r"([\w.]+)\.([\w.]+)\s*=\s*([\w.]+)\.(.*)Запрос",
            "message": "Возможна синхронная обработка — рассмотрите пакетную",
            "severity": "info",
        },
    }
    
    @classmethod
    def detect_anti_patterns(cls, query_text: str) -> List[Dict[str, Any]]:
        """Detect anti-patterns in a 1C query."""
        issues = []
        normalized = re.sub(r"\s+", " ", query_text).upper()
        
        for pattern_id, info in cls.ANTI_PATTERNS.items():
            if re.search(info["pattern"], query_text, re.IGNORECASE | re.MULTILINE):
                issues.append({
                    "pattern_id": pattern_id,
                    "message": info["message"],
                    "severity": info["severity"],
                    "query": query_text[:500],
                })
                
        return issues
        
    @classmethod
    def validate_query(cls, query_text: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Validate a 1C query against metadata (if provided)."""
        result = {
            "valid": True,
            "issues": [],
            "warnings": [],
        }
        
        if not query_text.strip():
            return {
                "valid": False,
                "issues": [{"message": "Пустой запрос"}],
                "warnings": [],
            }
            
        # Check basic query structure
        query_upper = query_text.upper().strip()
        
        if not any(query_upper.startswith(kw) for kw in ["ВЫБРАТЬ", "ВЫБРАТЬ РАЗЛИЧНЫЕ"]):
            result["valid"] = False
            result["issues"].append({"message": "Запрос должен начинаться с ВЫБРАТЬ или ВЫБРАТЬ РАЗЛИЧНЫЕ"})
            
        if "ИЗ" not in query_upper:
            result["valid"] = False
            result["issues"].append({"message": "В запросе отсутствует секция ИЗ"})
            
        # Detect anti-patterns
        anti_patterns = cls.detect_anti_patterns(query_text)
        for ap in anti_patterns:
            if ap["severity"] == "warning":
                result["warnings"].append(ap)
            else:
                result["issues"].append(ap)
                
        # Validate against metadata if provided
        if metadata:
            result["metadata_validated"] = True
            # Field validation would go here
        else:
            result["metadata_validated"] = False
            
        return result
        
    @classmethod
    def optimize_query(cls, query_text: str) -> Dict[str, Any]:
        """Suggest optimizations for a 1C query."""
        suggestions = []
        
        # Detect anti-patterns and suggest fixes
        anti_patterns = cls.detect_anti_patterns(query_text)
        
        for ap in anti_patterns:
            suggestion = {
                "pattern_id": ap["pattern_id"],
                "current": ap["message"],
                "suggestion": "",
            }
            
            if ap["pattern_id"] == "no_first":
                suggestion["suggestion"] = "Добавьте ПЕРВЫЕ 1000 (или нужное число)"
            elif ap["pattern_id"] == "select_all":
                suggestion["suggestion"] = "Замените * на явный список полей"
            elif ap["pattern_id"] == "not_in_subquery":
                suggestion["suggestion"] = "Используйте КАК НЕЛЬЗЯ вместо НЕ В (ВЫБРАТЬ)"
            elif ap["pattern_id"] == "cast_in_where":
                suggestion["suggestion"] = "Перенесите функцию из ГДЕ в вычисляемое поле"
            elif ap["pattern_id"] == "subquery_in_select":
                suggestion["suggestion"] = "Рассмотрите СОЕДИНЕНИЕ вместо подзапроса"
            else:
                suggestion["suggestion"] = "Проверьте паттерн вручную"
                
            suggestions.append(suggestion)
            
        return {
            "original_query": query_text[:500],
            "suggestions": suggestions,
            "count": len(suggestions),
        }
        
    @classmethod
    def extract_query_fields(cls, query_text: str) -> Dict[str, Any]:
        """Extract SELECT fields, FROM table, and WHERE conditions from a query."""
        result = {
            "fields": [],
            "tables": [],
            "conditions": [],
            "joins": [],
            "group_by": [],
            "order_by": [],
            "having": [],
            "first_n": None,
        }
        
        lines = query_text.split("\n")
        in_select = False
        in_where = False
        in_join = False
        in_group = False
        in_order = False
        
        for line in lines:
            stripped = line.strip().upper()
            
            if "ВЫБРАТЬ" in stripped or "ВЫБРАТЬ РАЗЛИЧНЫЕ" in stripped:
                in_select = True
                in_where = False
                in_join = False
                in_group = False
                in_order = False
                # Extract PЕРВЫЕ
                match = re.search(r"ПЕРВЫЕ\s+(\d+)", stripped)
                if match:
                    result["first_n"] = int(match.group(1))
                continue
                
            if "ИЗ" in stripped:
                in_select = False
                in_where = True
                # Extract table
                continue
                
            if stripped.startswith("ГДЕ"):
                in_where = True
                in_join = False
                in_group = False
                in_order = False
                continue
                
            if stripped.startswith("СОЕДИНЕНИЕ"):
                in_join = True
                in_where = False
                continue
                
            if stripped.startswith("СГРУППИРОВАТЬ"):
                in_group = True
                in_where = False
                in_join = False
                continue
                
            if stripped.startswith("ИМЕЮЩИЕ"):
                in_where = False
                in_join = False
                in_group = False
                result["having"].append(line.strip())
                continue
                
            if stripped.startswith("ORDER"):
                in_order = True
                in_where = False
                in_join = False
                in_group = False
                continue
                
            if stripped.startswith("//") or stripped.startswith("="):
                continue
                
            # Parse current line based on context
            if in_select and stripped and not any(stripped.startswith(kw) for kw in 
                                                    ["ИЗ", "ГДЕ", "СГРУППИРОВАТЬ", "ORDER", "ПЕРВЫЕ", "СОЕДИНЕНИЕ"]):
                result["fields"].append(line.strip())
            elif in_where and stripped and not stripped.startswith("ИЛИ") and not stripped.startswith("И "):
                if stripped.startswith("ГДЕ"):
                    result["conditions"].append(line.strip()[3:].strip())
                else:
                    result["conditions"].append(line.strip())
            elif in_join and stripped:
                result["joins"].append(line.strip())
            elif in_group and stripped:
                result["group_by"].append(line.strip())
            elif in_order and stripped:
                result["order_by"].append(line.strip())
                
        return result


class BSLAnalyzer:
    """Analyzes 1C BSL code for various issues and patterns."""
    
    # Patterns for deprecated API detection
    DEPRECATED_PATTERNS = {
        "getformbyid": r"\.ПолучитьФорму\s*\(\s*\"?([\w]+)\"?\s*\)",
        "stringtrim": r"\.СтрДлина\s*\(",
        "strreplace_old": r"\.СтрЗаменить\s*\(",
        "strfind_old": r"\.СтрНайти\s*\(",
        "strleft": r"\.СтрЛев\s*\(",
        "strright": r"\.СтрПрав\s*\(",
        "strmid": r"\.СтрПолучитьСтроку\s*\(",
        "datepart": r"\.GetYear\s*\(",
        "maxvalue_old": r"\.МаксЗнач\s*\(",
        "minvalue_old": r"\.МинЗнач\s*\(",
    }
    
    @classmethod
    def detect_deprecated_api(cls, code: str) -> List[Dict[str, Any]]:
        """Detect usage of deprecated 1C API functions."""
        issues = []
        lines = code.split("\n")
        
        for line_num, line in enumerate(lines, 1):
            for pattern_name, pattern in cls.DEPRECATED_PATTERNS.items():
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        "line": line_num,
                        "text": line.strip(),
                        "deprecated_api": pattern_name,
                        "message": f"Обнаружен устаревший метод: {pattern_name}",
                    })
                    
        return issues
        
    @classmethod
    def detect_hardcoded_secrets(cls, code: str) -> List[Dict[str, Any]]:
        """Detect hardcoded passwords, tokens, and URLs."""
        issues = []
        lines = code.split("\n")
        
        # Password patterns
        password_patterns = [
            r"(?:Пароль|Password|PWD)\s*=\s*['\"]([^'\"$]+)['\"]",
            r"['\"](?:password|passwd|pwd)\s*[:=]\s*['\"]([^'\"$]+)['\"]",
            r"(?:пароль|passwd)\s*:\s*['\"]([^'\"$]+)['\"]",
        ]
        
        # Token patterns
        token_patterns = [
            r"(?:Token|TOKEN|token)\s*=\s*['\"]([a-zA-Z0-9_\-]{16,})['\"]",
            r"(?:API[_\s]?KEY|APIKEY|api_key)\s*[:=]\s*['\"]([^'\"$]+)['\"]",
        ]
        
        for line_num, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith("//"):
                continue
                
            for pattern in password_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    # Skip empty or obviously non-secret values
                    if value and len(value) > 3 and not value.startswith("$"):
                        issues.append({
                            "line": line_num,
                            "text": line.strip(),
                            "type": "hardcoded_password",
                            "message": "Обнаружен хардкод пароля",
                        })
                        
            for pattern in token_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    issues.append({
                        "line": line_num,
                        "text": line.strip(),
                        "type": "hardcoded_token",
                        "message": "Обнаружен хардкод токена/ключа API",
                    })
                    
        return issues
        
    @classmethod
    def detect_duplicate_code(cls, code: str, min_lines: int = 10) -> List[Dict[str, Any]]:
        """Detect duplicate code blocks."""
        lines = code.split("\n")
        normalized_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Skip empty lines and comments for comparison
            if not stripped or stripped.startswith("//"):
                continue
            # Normalize whitespace
            normalized = " ".join(stripped.split())
            normalized_lines.append(normalized)
            
        duplicates = []
        block_size = min_lines
        
        for i in range(len(normalized_lines) - block_size + 1):
            block = normalized_lines[i:i + block_size]
            block_hash = hash(tuple(block))
            
            for j in range(i + block_size, len(normalized_lines) - block_size + 1):
                other_block = normalized_lines[j:j + block_size]
                if tuple(block) == tuple(other_block):
                    duplicates.append({
                        "first_start": i + 1,
                        "first_end": i + block_size,
                        "second_start": j + 1,
                        "second_end": j + block_size,
                        "lines": block_size,
                        "block_preview": block[0][:80] + "..." if len(block) > 1 else block[0][:80],
                    })
                    break  # Skip overlapping matches
                    
        return duplicates
        
    @classmethod
    def detect_code_antipatterns(cls, code: str) -> List[Dict[str, Any]]:
        """Detect common BSL code anti-patterns."""
        issues = []
        lines = code.split("\n")
        
        # Detect loops over full selection
        for i, line in enumerate(lines):
            if "Выбрать()" in line or ".Выбрать()" in line:
                # Check if next lines have цикл and no ПЕРВЫЕ
                context = "\n".join(lines[max(0, i-5):i])
                if "ПЕРВЫЕ" not in context:
                    issues.append({
                        "line": i + 1,
                        "text": line.strip(),
                        "type": "loop_full_selection",
                        "message": "Цикл по полной выборке без ПЕРВЫЕ",
                    })
                    
        # Detect synchronous calls in loops
        in_loop = False
        loop_start = 0
        for i, line in enumerate(lines):
            if "Цикл" in line:
                in_loop = True
                loop_start = i
            elif "КонецЦикла" in line:
                in_loop = False
                
        # Very large functions
        functions = []
        current_func = None
        for i, line in enumerate(lines):
            match = re.match(r"\s*(Процедура|Функция)\s+(\w+)", line)
            if match:
                if current_func:
                    functions.append(current_func)
                current_func = {
                    "type": match.group(1),
                    "name": match.group(2),
                    "start": i + 1,
                }
            elif current_func and re.match(r"\s*КонецПроцедуры|КонецФункции", line):
                current_func["end"] = i + 1
                functions.append(current_func)
                current_func = None
                
        return issues
        
    @classmethod
    def calculate_complexity(cls, code: str) -> Dict[str, Any]:
        """Calculate cyclomatic complexity for functions in code."""
        lines = code.split("\n")
        functions = []
        current_func = None
        
        complexity_keywords = [
            "Если", "Цикл", "Для", "Пока", "Исключение",
            "When", "For", "While", "Try",
        ]
        
        for i, line in enumerate(lines):
            match = re.match(r"\s*(Процедура|Функция)\s+(\w+)", line)
            if match:
                if current_func:
                    functions.append(current_func)
                current_func = {
                    "type": match.group(1),
                    "name": match.group(2),
                    "start": i + 1,
                    "complexity": 1,  # Base complexity
                    "lines": 0,
                }
            elif current_func:
                current_func["lines"] += 1
                for kw in complexity_keywords:
                    if kw in line:
                        current_func["complexity"] += 1
                        
        if current_func:
            functions.append(current_func)
            
        return {
            "functions": functions,
            "max_complexity": max((f["complexity"] for f in functions), default=0),
            "total_functions": len(functions),
            "total_lines": len(lines),
        }
        
    @classmethod
    def extract_all_queries(cls, code: str) -> List[Dict[str, Any]]:
        """Extract all Query objects from BSL code."""
        queries = []
        lines = code.split("\n")
        
        in_query = False
        query_start = 0
        query_lines = []
        query_name = ""
        
        for i, line in enumerate(lines):
            # Look for Query creation
            if "Новый Запрос" in line or "Запрос" in line and "Новый" in line:
                in_query = True
                query_start = i + 1
                query_lines = []
                # Try to get query name from variable assignment
                match = re.match(r"\s*(\w+)\s*=\s*.*Новый\s+Запрос", line)
                if match:
                    query_name = match.group(1)
                    
            elif in_query:
                if "Текст" in line and ("=" in line or ".Добавить" in line):
                    # Extract query text
                    text_match = re.search(r"\.Текст\s*=\s*\"\"\"([\s\S]*?)\"\"\"", line)
                    if text_match:
                        query_text = text_match.group(1)
                        queries.append({
                            "name": query_name or f"query_at_line_{query_start}",
                            "start_line": query_start,
                            "query_text": query_text[:1000],
                            "is_multiline": True,
                        })
                        
                # Check for multi-line text with Добавление
                if "Добавить" in line and ("\"\"\"" in line or "Текст" in line):
                    text_match = re.search(r"\"\s*(\+?\s*)?\n([\s\S]*?)\".*?\.Текст", line)
                    if text_match:
                        pass  # Complex extraction
                        
                # End of query block
                if "КонецПопытки" in line or "КонецЕсли" in line:
                    # Check if we're still in a query context
                    pass
                    
        return queries


# BSL syntax help database (common functions)
BSL_SYNTAX_HELP = {
    "СтрНайти": {"sig": "СтрНайти(Строка, Подстрока [, Позиция])", "desc": "Возвращает позицию первого вхождения подстроки", "since": "8.0.0"},
    "СтрЗаменить": {"sig": "СтрЗаменить(Строка, Строка, Строка)", "desc": "Заменяет все вхождения подстроки", "since": "8.0.0"},
    "СтрДлина": {"sig": "СтрДлина(Строка)", "desc": "Возвращает длину строки в символах", "since": "8.0.0"},
    "СтрПолучитьСтроку": {"sig": "СтрПолучитьСтроку(Строка, Номер)", "desc": "Возвращает указанную строку из многострочной", "since": "8.0.0"},
    "СтрЧислоСтрок": {"sig": "СтрЧислоСтрок(Строка)", "desc": "Возвращает количество строк", "since": "8.0.0"},
    "СокрЛ": {"sig": "СокрЛ(Строка)", "desc": "Удаляет пробелы слева", "since": "8.0.0"},
    "СокрП": {"sig": "СокрП(Стokka)", "desc": "Удаляет пробелы справа", "since": "8.0.0"},
    "СокрЛП": {"sig": "СокрЛП(Строка)", "desc": "Удаляет пробелы слева и справа", "since": "8.0.0"},
    "Число": {"sig": "Число(Строка)", "desc": "Преобразует строку в число", "since": "8.0.0"},
    "Строка": {"sig": "Строка(Значение)", "desc": "Преобразует значение в строку", "since": "8.0.0"},
    "ДатаГод": {"sig": "ДатаГод(Дата)", "desc": "Возвращает год из даты", "since": "8.0.0"},
    "ДатаМесяц": {"sig": "ДатаМесяц(Дата)", "desc": "Возвращает месяц из даты", "since": "8.0.0"},
    "ДатаЧисло": {"sig": "ДатаЧисло(Дата)", "desc": "Возвращает день месяца из даты", "since": "8.0.0"},
    "ТекущаяДата": {"sig": "ТекущаяДата()", "desc": "Возвращает текущие дату и время", "since": "8.0.0"},
    "НачалоГода": {"sig": "НачалоГода(Дата)", "desc": "Начало года для указанной даты", "since": "8.0.0"},
    "КонецГода": {"sig": "КонецГода(Дата)", "desc": "Конец года для указанной даты", "since": "8.0.0"},
    "НачалоМесяца": {"sig": "НачалоМесяца(Дата)", "desc": "Начало месяца для указанной даты", "since": "8.0.0"},
    "КонецМесяца": {"sig": "КонецМесяца(Дата)", "desc": "Конец месяца для указанной даты", "since": "8.0.0"},
    "НачалоДня": {"sig": "НачалоДня(Дата)", "desc": "Начало дня для указанной даты", "since": "8.0.0"},
    "КонецДня": {"sig": "КонецДня(Дата)", "desc": "Конец дня для указанной даты", "since": "8.0.0"},
    "ДобавитьМесяц": {"sig": "ДобавитьМесяц(Дата, Число)", "desc": "Добавляет указанное число месяцев", "since": "8.0.0"},
    "НайтиПробел": {"sig": "НайтиПробел(Строка [, Направление])", "desc": "Находит пробел в строке", "since": "8.0.0"},
    "РегБ": {"sig": "РегБ(Строка)", "desc": "Верхний регистр", "since": "8.0.0"},
    "РегМ": {"sig": "РегМ(Строка)", "desc": "Нижний регистр", "since": "8.0.0"},
    "Формат": {"sig": "Формат(Значение, СтрокаФормата)", "desc": "Форматирует значение по шаблону", "since": "8.0.0"},
    "ЭтоНомер": {"sig": "ЭтоНомер(Значение)", "desc": "Истина, если значение — номер", "since": "8.0.0"},
    "ЭтоДата": {"sig": "ЭтоДата(Значение)", "desc": "Истина, если значение — дата", "since": "8.0.0"},
    "ЭтоЧисло": {"sig": "ЭтоЧисло(Значение)", "desc": "Истина, если значение — число", "since": "8.0.0"},
    "ЗаполнитьЗначенияСвойств": {"sig": "ЗаполнитьЗначенияСвойств(Объект, Источник)", "desc": "Копирует значения свойств объекта", "since": "8.0.0"},
    "Заполнить": {"sig": "Заполнить(Назначения, Источники [, МассивПолей])", "desc": "Заполняет реквизиты из источника", "since": "8.0.0"},
    "СоздатьОбъект": {"sig": "СоздатьОбъект(Имя)", "desc": "Создает COM-объект (устаревший)", "since": "8.0.0"},
}


def get_bsl_syntax_help(func_name: str = "") -> Dict[str, Any]:
    """Get BSL syntax help for a function."""
    if func_name:
        # Search for the function (case-insensitive)
        for name, info in BSL_SYNTAX_HELP.items():
            if name.lower() == func_name.lower():
                return {"function": name, **info}
        return {"error": f"Функция '{func_name}' не найдена в справочнике"}
        
    # Return all functions
    return {"count": len(BSL_SYNTAX_HELP), "functions": BSL_SYNTAX_HELP}


def find_bsl_synonyms(func_name: str) -> Dict[str, Any]:
    """Find BSL synonyms (Russian/English equivalents)."""
    synonyms = {
        "СтрНайти": ["StrFind", "StringFind"],
        "СтрЗаменить": ["StrReplace", "StringReplace"],
        "СтрДлина": ["StrLength", "StringLength"],
        "СтрПолучитьСтроку": ["StrGetLine", "StringGetLine"],
        "СокрЛ": ["TrimLeft", "StrTrimLeft"],
        "СокрП": ["TrimRight", "StrTrimRight"],
        "СокрЛП": ["Trim", "StrTrim"],
        "РегБ": ["ToUpper", "RegB"],
        "РегМ": ["ToLower", "RegM"],
        "ТекущаяДата": ["GetCurrentDate", "CurrentDate"],
        "НачалоГода": ["StartOfYear", "BeginningOfYear"],
        "КонецГода": ["EndOfYear"],
        "НачалоМесяца": ["StartOfMonth", "BeginningOfMonth"],
        "КонецМесяца": ["EndOfMonth"],
    }
    
    result = {}
    for ru_name, en_names in synonyms.items():
        if func_name.lower() in ru_name.lower() or func_name in en_names:
            result[ru_name] = en_names
            
    return result if result else {"error": f"Синонимы для '{func_name}' не найдены"}


def check_api_version(func_name: str, platform_version: str = "8.3.0") -> Dict[str, Any]:
    """Check if a BSL function is available in the specified platform version."""
    for name, info in BSL_SYNTAX_HELP.items():
        if name.lower() == func_name.lower():
            introduced = info.get("since", "8.0.0")
            # Simple version comparison
            if introduced <= platform_version:
                return {
                    "function": name,
                    "available": True,
                    "since": introduced,
                    "message": f"Функция доступна в версии {platform_version}+",
                }
            else:
                return {
                    "function": name,
                    "available": False,
                    "introduced_in": introduced,
                    "message": f"Функция добавлена в версии {introduced}, текущая: {platform_version}",
                }
    return {"error": "Функция не найдена в справочнике"}
