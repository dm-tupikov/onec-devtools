"""Capability catalogs for 1C Configurator and ibcmd batch modes.

The catalogs are documentation-first allowlists. They do not invoke a shell and
separate read-only operations from operations that can mutate an infobase.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Capability:
    name: str
    executable: str
    command: str
    mutates_infobase: bool
    needs_exclusive_access: bool
    description: str
    source: str

    def to_dict(self) -> dict:
        return asdict(self)


DESIGNER_CAPABILITIES = (
    Capability("dump_ib", "1cv8", "/DumpIB", False, True, "Выгрузить информационную базу в DT.", "1C batch mode"),
    Capability("restore_ib", "1cv8", "/RestoreIB", True, True, "Восстановить информационную базу из DT.", "1C batch mode"),
    Capability("dump_cfg", "1cv8", "/DumpCfg", False, False, "Выгрузить основную конфигурацию или расширение в CF/CFE.", "1C batch mode"),
    Capability("load_cfg", "1cv8", "/LoadCfg", True, True, "Загрузить основную конфигурацию или расширение из CF/CFE.", "1C batch mode"),
    Capability("dump_db_cfg", "1cv8", "/DumpDBCfg", False, False, "Выгрузить конфигурацию базы данных в CF.", "1C batch mode"),
    Capability("rollback_cfg", "1cv8", "/RollbackCfg", True, True, "Вернуть основную конфигурацию к конфигурации базы данных.", "1C batch mode"),
    Capability("dump_xml", "1cv8", "/DumpConfigToFiles", False, False, "Выгрузить конфигурацию или расширения в XML-файлы.", "1C 8.3 administrator guide"),
    Capability("load_xml", "1cv8", "/LoadConfigFromFiles", True, True, "Загрузить конфигурацию или расширения из XML-файлов.", "1C 8.3 administrator guide"),
    Capability("update_db", "1cv8", "/UpdateDBCfg", True, True, "Обновить конфигурацию базы данных.", "1C batch mode"),
    Capability("check_modules", "1cv8", "/CheckModules", False, False, "Выполнить синтаксический контроль модулей.", "1C batch mode"),
    Capability("check_config", "1cv8", "/CheckConfig", False, False, "Выполнить проверку конфигурации с выбранными видами контроля.", "1C batch mode"),
    Capability("check_and_repair", "1cv8", "/IBCheckAndRepair", True, True, "Протестировать или исправить информационную базу.", "1C batch mode"),
    Capability("update_supported_cfg", "1cv8", "/UpdateCfg", True, True, "Обновить конфигурацию, находящуюся на поддержке.", "1C batch mode"),
    Capability("reduce_event_log", "1cv8", "/ReduceEventLogSize", True, True, "Сократить журнал регистрации до указанной даты.", "1C batch mode"),
    Capability("dump_config_files", "1cv8", "/DumpConfigFiles", False, False, "Выгрузить модули, формы или справку в текстовые файлы.", "1C batch mode"),
    Capability("load_config_files", "1cv8", "/LoadConfigFiles", True, True, "Загрузить модули, формы или справку из текстовых файлов.", "1C batch mode"),
    Capability("create_distribution", "1cv8", "/CreateDistributionFiles", False, False, "Создать файлы поставки CF/CFU.", "1C batch mode"),
    Capability("repository_dump", "1cv8", "/ConfigurationRepositoryDumpCfg", False, False, "Выгрузить версию конфигурации из хранилища.", "1C batch mode"),
    Capability("repository_update", "1cv8", "/ConfigurationRepositoryUpdateCfg", True, True, "Обновить конфигурацию из хранилища.", "1C batch mode"),
    Capability("build_external", "1cv8", "/LoadExternalDataProcessorOrReportFromFiles", False, False, "Собрать EPF/ERF из XML-файлов.", "1C 8.3 administrator guide"),
    Capability("dump_external", "1cv8", "/DumpExternalDataProcessorOrReportToFiles", False, False, "Разобрать EPF/ERF в XML-файлы.", "1C 8.3 administrator guide"),
)


IBCMD_CAPABILITIES = (
    Capability("infobase.create", "ibcmd", "infobase create", True, True, "Создать ИБ; можно загрузить DT, CF или XML и применить конфигурацию.", "ibcmd 8.3.21 --help"),
    Capability("infobase.dump", "ibcmd", "infobase dump", False, True, "Выгрузить данные ИБ.", "ibcmd 8.3.21 --help"),
    Capability("infobase.restore", "ibcmd", "infobase restore", True, True, "Восстановить данные ИБ с опциональным завершением сеансов.", "ibcmd 8.3.21 --help"),
    Capability("infobase.clear", "ibcmd", "infobase clear", True, True, "Очистить ИБ.", "ibcmd 8.3.21 --help"),
    Capability("config.load", "ibcmd", "infobase config load", True, True, "Загрузить CF/CFE.", "ibcmd 8.3.21 --help"),
    Capability("config.save", "ibcmd", "infobase config save", False, False, "Сохранить CF/CFE, включая конфигурацию БД.", "ibcmd 8.3.21 --help"),
    Capability("config.check", "ibcmd", "infobase config check", False, False, "Проверить конфигурацию или расширение.", "ibcmd 8.3.21 --help"),
    Capability("config.apply", "ibcmd", "infobase config apply", True, True, "Применить конфигурацию с политикой динамического обновления и завершения сеансов.", "ibcmd 8.3.21 --help"),
    Capability("config.reset", "ibcmd", "infobase config reset", True, True, "Вернуть конфигурацию к конфигурации БД.", "ibcmd 8.3.21 --help"),
    Capability("config.repair", "ibcmd", "infobase config repair", True, True, "Завершить, отменить или восстановить незавершённую операцию.", "ibcmd 8.3.21 --help"),
    Capability("config.export", "ibcmd", "infobase config export", False, False, "Экспортировать XML, ConfigDumpInfo, изменения или выбранные объекты.", "ibcmd 8.3.21 --help"),
    Capability("config.import", "ibcmd", "infobase config import", True, True, "Импортировать весь XML, выбранные файлы или все расширения.", "ibcmd 8.3.21 --help"),
    Capability("config.support.disable", "ibcmd", "infobase config support disable", True, True, "Снять конфигурацию с поддержки.", "ibcmd 8.3.21 --help"),
    Capability("config.data_separation.list", "ibcmd", "infobase config data-separation list", False, False, "Получить список разделителей ИБ.", "ibcmd 8.3.21 --help"),
    Capability("config.extension", "ibcmd", "infobase config extension", True, False, "Создать, просмотреть, изменить или удалить расширения.", "ibcmd 8.3.21 --help"),
    Capability("config.generation_id", "ibcmd", "infobase config generation-id", False, False, "Получить идентификатор поколения конфигурации.", "ibcmd 8.3.21 --help"),
    Capability("server.config.init", "ibcmd", "server config init", False, False, "Создать конфигурационный файл автономного сервера.", "ibcmd 8.3.21 --help"),
    Capability("server.config.import", "ibcmd", "server config import", False, False, "Импортировать настройки автономного сервера из реестра кластера.", "ibcmd 8.3.21 --help"),
)


def designer_capabilities() -> list[dict]:
    return [item.to_dict() for item in DESIGNER_CAPABILITIES]


def ibcmd_capabilities() -> list[dict]:
    return [item.to_dict() for item in IBCMD_CAPABILITIES]
