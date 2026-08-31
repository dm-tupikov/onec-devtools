"""Generic allowlisted runner for 1C Configurator batch operations."""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

from .command_catalog import DESIGNER_CAPABILITIES


Runner = Callable[..., subprocess.CompletedProcess]


@dataclass(frozen=True)
class DesignerResult:
    command: list[str]
    exit_code: int
    log_path: str
    log_text: str

    def to_dict(self) -> dict:
        return asdict(self)


def _capability(arguments: Sequence[str]):
    if not arguments:
        return None
    first = str(arguments[0]).lower()
    return next(
        (item for item in DESIGNER_CAPABILITIES if item.command.lower() == first),
        None,
    )


def run_designer_batch(
    *,
    onec_executable: Path,
    connection_mode: str,
    connection: str,
    arguments: Sequence[str],
    log_path: Path,
    username: str = "",
    password: str = "",
    confirmed: bool = False,
    timeout: int = 1800,
    runner: Runner = subprocess.run,
) -> DesignerResult:
    """Run one allowlisted Configurator operation without a command shell."""

    executable = Path(onec_executable)
    if not executable.exists():
        raise FileNotFoundError(executable)
    if connection_mode not in {"file", "server", "name", "connection-string"}:
        raise ValueError("Unsupported connection_mode")
    capability = _capability(arguments)
    if capability is None:
        raise ValueError("Unsupported Configurator batch command")
    if capability.mutates_infobase and not confirmed:
        raise PermissionError("Mutating Configurator command requires confirmed=true")

    connection_switch = {
        "file": "/F",
        "server": "/S",
        "name": "/IBName",
        "connection-string": "/IBConnectionString",
    }[connection_mode]
    command = [str(executable), "DESIGNER", connection_switch, str(connection)]
    display_command = list(command)
    if username:
        command.extend(["/N", username])
        display_command.extend(["/N", username])
    if password:
        command.extend(["/P", password])
        display_command.extend(["/P", "[REDACTED]"])
    command.extend(map(str, arguments))
    display_command.extend(map(str, arguments))
    command.extend(["/Out", str(log_path), "/DisableStartupDialogs"])
    display_command.extend(["/Out", str(log_path), "/DisableStartupDialogs"])

    log_path.parent.mkdir(parents=True, exist_ok=True)
    completed = runner(command, capture_output=True, timeout=timeout)
    log_text = (
        log_path.read_text(encoding="utf-8-sig", errors="replace")
        if log_path.exists()
        else ""
    )
    result = DesignerResult(
        command=display_command,
        exit_code=completed.returncode,
        log_path=str(log_path),
        log_text=log_text,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Configurator returned {completed.returncode}; "
            f"log={log_path}; tail={log_text[-2000:]}"
        )
    return result
