# MCP:1C-DevTools — сервер для разработки 1С

**74 инструмента для разработки в 1С:Предприятие** — статический анализ, аудит кода, проверка запросов, верификация EPF и многое другое.

Работает с локальными XML-выгрузками конфигурации 1С — **не требует запущенной базы 1С**.

## Быстрый старт

### Docker

```bash
# Клонируем и готовим данные
mkdir -p config-dump
# Копируем XML-выгрузку 1С в config-dump/

# Собираем и запускаем
docker build -t onec-devtools .
docker run --rm -it \
  -v $(pwd)/config-dump:/data/config:ro \
  -v $(pwd)/src/cf:/data/src:ro \
  onec-devtools

# Или через docker-compose
docker-compose up --build
```

### Локально

```bash
pip install -r requirements.txt
python -m mcp_devtools --config-path ./config-dump
```

## Доступные инструменты (74)

### А: Метаданные (10)
| Инструмент | Описание |
|-----------|----------|
| `meta.tree` | Дерево метаданных по типам |
| `meta.structure` | Полная структура объекта |
| `meta.search` | Поиск по имени/описанию |
| `meta.dependencies` | Граф зависимостей |
| `meta.find_orphans` | Объекты вне подсистем |
| `meta.compare` | Сравнение двух версий метаданных |
| `meta.find_undefined_refs` | Ссылки на несуществующие объекты |
| `meta.subsystem_map` | Карта подсистем → объекты |
| `meta.field_usage` | Где используется реквизит |
| `meta.cross_ref` | Перекрёстные ссылки: формы, модули, запросы |

### Б: Аудит (15)
| Инструмент | Описание |
|-----------|----------|
| `audit.e1_e9` | Аудит дефектов E1–E9 |
| `audit.query_antipatterns` | 15 антипаттернов запросов |
| `audit.code_antipatterns` | Антипаттерны BSL-кода |
| `audit.security` | Хардкод секретов |
| `audit.deprecated_api` | Устаревшие методы платформы |
| `audit.pi_data` | Шаблоны персональных данных |
| `audit.rls_roles` | Анализ ролей и RLS-прав |
| `audit.duplicate_code` | Дублирующийся код |
| `audit.dead_code` | Невостребованные функции |
| `audit.module_complexity` | Цикломатическая сложность |
| `audit.tms_integration` | Аудит интеграции TMS 2.0 |
| `audit.exchange_safety` | Безопасность планов обмена |
| `audit.version_check` | Совместимость с версией платформы |
| `audit.rnd_flag` | Проверка флага загрузки (E8) |
| `audit.transaction_boundary` | Границы транзакций (E4) |

### В: Запросы (8)
| Инструмент | Описание |
|-----------|----------|
| `query.validate` | Синтаксическая и семантическая валидация |
| `query.optimize` | Подсказки по оптимизации |
| `query.explain` | Извлечение логического плана |
| `query.find_sinks` | Медленные паттерны запросов |
| `query.generate` | Генерация по описанию |
| `query.check_fields` | Проверка полей по метаданным |
| `query.check_dimensions` | Проверка измерителей регистров |
| `query.convert_to_async` | Конвертация синхронных в асинхронные |

### Г: EPF-артефакты (8)
| Инструмент | Описание |
|-----------|----------|
| `epf.validate` | Проверка бинарного заголовка |
| `epf.roundtrip_check` | Сборка → выгрузка → diff |
| `epf.generate` | Генерация из шаблона |
| `epf.extract_info` | Извлечение метаданных из EPF |
| `epf.check_modules` | Проверка полноты модулей |
| `epf.compare` | Сравнение двух EPF |
| `epf.validate_rules` | Чеклист E1–E9 |
| `epf.list_commands` | Список команд внешн. обработки |

### Д: Формы и СКД (8)
| Инструмент | Описание |
|-----------|----------|
| `form.structure` | Анализ структуры формы |
| `form.find_orphans` | Формы без привязанных объектов |
| `form.command_audit` | Аудит команд |
| `skd.structure` | Структура компоновщика данных |
| `skd.check_fields` | Проверка полей СКД |
| `skd.compare` | Сравнение макетов СКД |
| `mxl.audit` | Аудит макетов MXL |
| `form.to_async` | Конвертация модальных вызовов |

### Е: Интеграции (6)
| Инструмент | Описание |
|-----------|----------|
| `exchange.analyze` | Анализ планов обмена |
| `xdto.validate` | Валидация XDTO-пакетов |
| `kshd.contract_check` | Проверка контракта КШД |
| `integration.retry_policy` | Аудит retry-политики |
| `integration.cascade_check` | Аудит каскадов отмены |
| `integration.loop_prevention` | Профилактика петель данных |

### Ё: Тесты и качество (6)
| Инструмент | Описание |
|-----------|----------|
| `test.generate` | Шаблоны тестов (YAxUnit/Vanessa) |
| `test.coverage` | Анализ покрытия тестами |
| `quality.metrics` | Метрики качества кода |
| `quality.bulk_analyze` | Полная проверка (антипаттерны + дубли + мёртвый код) |
| `quality.gate` | CI/CD quality gate |
| `quality.trend` | Тренды метрик по версиям |

### Ж: DevTools-ассистенты (8)
| Инструмент | Описание |
|-----------|----------|
| `bsl.syntax.help` | Справка по функциям платформы (30+) |
| `bsl.generate_query` | Генератор запросов |
| `bsl.generate_print_form` | Шаблон печатной формы |
| `bsl.generate_report` | Шаблон отчёта СКД |
| `bsl.convert_modal_async` | Модальные → асинхронные вызовы |
| `bsl.find_synonyms` | Синонимы функций (СтрНайти ↔ StrFind) |
| `bsl.version_check` | Доступность метода в версии платформы |
| `config.template_apply` | Шаблоны конфигурации |

### З: Конфигурация (5)
| Инструмент | Описание |
|-----------|----------|
| `config.diff` | Сравнение двух сборок XML |
| `config.validate_build` | Проверка готовности к сборке |
| `config.added_objects` | Добавленные/удалённые объекты |
| `config.checklist` | Чеклист перед коммитом |
| `config.generate_report` | Полный отчёт о конфигурации |

## Конфигурация

Задаётся через переменные окружения или аргументы CLI:

| Переменная | Описание | По умолчанию |
|-----------|----------|-------------|
| `ONEC_DEVTOOLS_CONFIG_PATH` | Путь к XML-выгрузке 1С | требуется для инструментов метаданных |
| `ONEC_DEVTOOLS_LOG_LEVEL` | Уровень логирования | INFO |
| `ONEC_DEVTOOLS_TEST_BASE` | Тестовая 1С-база для round-trip | опционально |
| `ONEC_DEVTOOLS_1C_PATH` | Путь к 1cv8.exe | опционально |

## Архитектура

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│  MCP-клиент  │────▶│  MCP-сервер      │────▶│  1С Config   │
│  (Kilo и др) │◀────│  (Python)        │◀────│  (локальный) │
└──────────────┘     └──────────────────┘     └──────────────┘
```

Работает исключительно с локальными XML-файлами — для статического анализа запущенная база 1С не нужна.

## Лицензия

MIT
