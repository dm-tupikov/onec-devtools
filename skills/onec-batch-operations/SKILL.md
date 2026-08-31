---
name: onec-batch-operations
description: Use when automating 1C Configurator or ibcmd operations.
version: 0.1.0
author: Project contributors, Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [1C, DESIGNER, ibcmd, batch, CF, XML, DT]
    related_skills: []
---

# 1C Batch Operations

Используйте пакетный режим для воспроизводимых операций с ИБ и конфигурацией. В проекте поддержаны два исполнителя: `1cv8.exe DESIGNER` и `ibcmd.exe`; они вызываются списком аргументов без shell-интерполяции.

## When to Use

- загрузка/выгрузка CF, DT и XML;
- обновление конфигурации БД;
- синтаксический контроль и `CheckConfig`;
- тестирование/исправление ИБ;
- работа с расширениями и хранилищем;
- CI/CD и повторяемая сборка артефактов.

## How to Run

Через `terminal` из корня репозитория:

```bash
python scripts/onec-batch.py designer-capabilities
python scripts/onec-batch.py ibcmd-capabilities
python scripts/onec-batch.py ibcmd-help --ibcmd "C:\\Program Files\\1cv8\\8.3.21.1393\\bin\\ibcmd.exe"
python scripts/onec-batch.py apply-and-build-cf \
  --onec "C:\\Program Files\\1cv8\\8.3.21.1393\\bin\\1cv8.exe" \
  --infobase "C:\\Bases\\Test" --source "C:\\src\\cf" \
  --output "C:\\artifacts\\build.cf"
```

## Procedure

1. Проверить версию платформы и фактические возможности `ibcmd --help`.
2. Проверить, что ИБ не используется другими сеансами и существует `1Cv8.1CD`.
3. Перед изменяющей операцией выполнить `/DumpCfg` в отдельный backup-файл.
4. Для XML использовать `DESIGNER /F <ИБ> /LoadConfigFromFiles <каталог> -Format Hierarchical`.
5. Для применения структуры добавить `/UpdateDBCfg`; при необходимости — `-WarningsAsErrors` и явный режим dynamic.
6. Для результата выполнить `/DumpCfg <output.cf>` и проверить размер, SHA-256, exit code и журнал `/Out`.
7. Для частичной выгрузки/загрузки отдельно проверить формат `listFile`: для dump — имена объектов, для load — относительные пути файлов.
8. При ошибке не продолжать следующий шаг; восстановление выполняется из проверенного backup CF.

## DESIGNER catalog

Поддерживаемые операции: `/DumpIB`, `/RestoreIB`, `/DumpCfg`, `/LoadCfg`, `/DumpDBCfg`, `/RollbackCfg`, `/DumpConfigToFiles`, `/LoadConfigFromFiles`, `/UpdateDBCfg`, `/CheckModules`, `/CheckConfig`, `/IBCheckAndRepair`, `/UpdateCfg`, `/ReduceEventLogSize`, `/DumpConfigFiles`, `/LoadConfigFiles`, `/CreateDistributionFiles`, `/ConfigurationRepositoryDumpCfg`, `/ConfigurationRepositoryUpdateCfg`, сборка и разборка EPF/ERF.

Общие параметры: `DESIGNER`, `/F` или `/S`, `/N`, `/P`, `/WA+/-`, `/Out`, `/DisableStartupDialogs`, `/DisableStartupMessages`, `/DumpResult`.

## ibcmd catalog

Фактический каталог для установленной версии должен быть получен `ibcmd-help`. В версии 8.3.21 подтверждены: `infobase create/dump/restore/clear`, `config load/save/check/apply/reset/repair`, `config export/import`, support, data separation, extensions, generation id, а также server config init/import.

## Safety

`restore`, `clear`, `config load`, `config apply`, `config reset`, repair и операции с расширениями требуют явного подтверждения вызывающего кода. Пароли не должны попадать в журналы. Не использовать `shell=True` и не склеивать команду в строку.

## Verification

Успех подтверждается только одновременно: exit code 0, ожидаемый лог `/Out`, непустой артефакт и контрольная сумма. Отсутствие лога или артефакта — не успех.

Источники:

- официальный обзор 1С: `https://v8.1c.ru/platforma/zapusk-konfiguratora-v-paketnom-rezhime/`;
- 1С:ИТС, руководство администратора, приложение 7 — параметры командной строки;
- фактический вывод `ibcmd help infobase` установленной версии.
