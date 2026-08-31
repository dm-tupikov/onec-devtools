"""Verified batch operations for the 1C:Enterprise Configurator.

Commands use the supported DESIGNER mode with /F for file infobases.
Arguments are passed as a list, so spaces and Cyrillic paths do not require
shell quoting or PowerShell/cmd wrappers.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence


@dataclass(frozen=True)
class CommandResult:
    """Evidence captured from one Configurator command."""

    label: str
    command: list[str]
    exit_code: int
    log_path: str
    log_text: str


@dataclass(frozen=True)
class BuildResult:
    """Artifacts and command evidence for an apply-and-build operation."""

    infobase: str
    source_dir: str
    backup_cf: str
    backup_size: int
    backup_sha256: str
    output_cf: str
    output_size: int
    output_sha256: str
    commands: list[CommandResult]

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "commands": [asdict(command) for command in self.commands],
        }


Runner = Callable[..., subprocess.CompletedProcess]


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_inputs(onec_executable: Path, infobase: Path, source_dir: Path) -> None:
    required = (
        onec_executable,
        infobase / "1Cv8.1CD",
        source_dir / "Configuration.xml",
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Required paths not found: " + ", ".join(missing))


def run_designer(
    *,
    onec_executable: Path,
    infobase: Path,
    arguments: Sequence[str],
    log_path: Path,
    label: str,
    timeout: int = 1800,
    runner: Runner = subprocess.run,
) -> CommandResult:
    """Run one Configurator batch command and return verifiable evidence."""

    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(onec_executable),
        "DESIGNER",
        "/F",
        str(infobase),
        *map(str, arguments),
        "/Out",
        str(log_path),
        "/DisableStartupDialogs",
    ]
    completed = runner(command, capture_output=True, timeout=timeout)
    log_text = (
        log_path.read_text(encoding="utf-8-sig", errors="replace")
        if log_path.exists()
        else ""
    )
    result = CommandResult(
        label=label,
        command=command,
        exit_code=completed.returncode,
        log_path=str(log_path),
        log_text=log_text,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{label}: Configurator returned {completed.returncode}; "
            f"log={log_path}; tail={log_text[-2000:]}"
        )
    return result


def apply_xml_and_build_cf(
    *,
    onec_executable: Path,
    infobase: Path,
    source_dir: Path,
    output_cf: Path,
    backup_dir: Path | None = None,
    log_dir: Path | None = None,
    timestamp: str | None = None,
    timeout: int = 1800,
    runner: Runner = subprocess.run,
) -> BuildResult:
    """Back up an infobase, load XML, update the DB, and build a CF.

    The operation is fail-fast: XML is never loaded when the fresh backup
    command fails or does not create a non-empty CF file.
    """

    onec_executable = Path(onec_executable)
    infobase = Path(infobase)
    source_dir = Path(source_dir)
    output_cf = Path(output_cf)
    backup_dir = Path(backup_dir) if backup_dir else output_cf.parent
    log_dir = Path(log_dir) if log_dir else output_cf.parent / "onec-batch-logs"
    timestamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")

    _validate_inputs(onec_executable, infobase, source_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    output_cf.parent.mkdir(parents=True, exist_ok=True)
    backup_cf = backup_dir / f"infobase-before-{timestamp}.cf"

    commands: list[CommandResult] = []
    commands.append(
        run_designer(
            onec_executable=onec_executable,
            infobase=infobase,
            arguments=["/DumpCfg", str(backup_cf)],
            log_path=log_dir / "01-backup.log",
            label="backup-current-cf",
            timeout=timeout,
            runner=runner,
        )
    )
    if not backup_cf.exists() or backup_cf.stat().st_size == 0:
        raise RuntimeError(f"Fresh backup CF was not created: {backup_cf}")

    commands.append(
        run_designer(
            onec_executable=onec_executable,
            infobase=infobase,
            arguments=[
                "/LoadConfigFromFiles",
                str(source_dir),
                "-Format",
                "Hierarchical",
                "/UpdateDBCfg",
            ],
            log_path=log_dir / "02-load-update.log",
            label="load-xml-and-update-db",
            timeout=timeout,
            runner=runner,
        )
    )
    commands.append(
        run_designer(
            onec_executable=onec_executable,
            infobase=infobase,
            arguments=["/DumpCfg", str(output_cf)],
            log_path=log_dir / "03-dump-final.log",
            label="dump-final-cf",
            timeout=timeout,
            runner=runner,
        )
    )
    if not output_cf.exists() or output_cf.stat().st_size == 0:
        raise RuntimeError(f"Final CF was not created: {output_cf}")

    return BuildResult(
        infobase=str(infobase),
        source_dir=str(source_dir),
        backup_cf=str(backup_cf),
        backup_size=backup_cf.stat().st_size,
        backup_sha256=file_sha256(backup_cf),
        output_cf=str(output_cf),
        output_size=output_cf.stat().st_size,
        output_sha256=file_sha256(output_cf),
        commands=commands,
    )
