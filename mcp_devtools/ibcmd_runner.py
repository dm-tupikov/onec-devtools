"""Safe subprocess runner for the 1C ibcmd utility."""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

from .command_catalog import IBCMD_CAPABILITIES


Runner = Callable[..., subprocess.CompletedProcess]
_SECRET_OPTIONS = {"--password", "--db-pwd", "--db-pwd-file"}


@dataclass(frozen=True)
class IbcmdResult:
    command: list[str]
    display_command: list[str]
    exit_code: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict:
        return asdict(self)


def _decode(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    for encoding in ("utf-8", "cp866", "cp1251"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


def _redact(arguments: Sequence[str]) -> list[str]:
    output: list[str] = []
    hide_next = False
    for argument in map(str, arguments):
        if hide_next:
            output.append("[REDACTED]")
            hide_next = False
            continue
        option, separator, _value = argument.partition("=")
        if option in _SECRET_OPTIONS:
            output.append(f"{option}=[REDACTED]" if separator else option)
            hide_next = not separator
        else:
            output.append(argument)
    return output


def _known_prefix(arguments: Sequence[str]) -> bool:
    normalized = " ".join(map(str, arguments))
    return any(
        normalized == capability.command
        or normalized.startswith(capability.command + " ")
        for capability in IBCMD_CAPABILITIES
    ) or normalized.startswith("help ")


def _is_mutating(arguments: Sequence[str]) -> bool:
    normalized = " ".join(map(str, arguments))
    return any(
        capability.mutates_infobase
        and (normalized == capability.command or normalized.startswith(capability.command + " "))
        for capability in IBCMD_CAPABILITIES
    )


def run_ibcmd(
    *,
    ibcmd_executable: Path,
    arguments: Sequence[str],
    confirmed: bool = False,
    timeout: int = 1800,
    runner: Runner = subprocess.run,
) -> IbcmdResult:
    """Run an allowlisted ibcmd command without shell interpolation.

    Mutating commands require ``confirmed=True``. Passwords are preserved in
    the real argv but redacted from returned evidence.
    """

    executable = Path(ibcmd_executable)
    if not executable.exists():
        raise FileNotFoundError(executable)
    if not arguments:
        raise ValueError("ibcmd arguments are required")
    if not _known_prefix(arguments):
        raise ValueError("Unsupported ibcmd command prefix")
    if _is_mutating(arguments) and not confirmed:
        raise PermissionError("Mutating ibcmd command requires confirmed=true")

    command = [str(executable), *map(str, arguments)]
    completed = runner(
        command,
        input=b"",
        capture_output=True,
        timeout=timeout,
    )
    result = IbcmdResult(
        command=_redact(command),
        display_command=_redact(command),
        exit_code=completed.returncode,
        stdout=_decode(completed.stdout),
        stderr=_decode(completed.stderr),
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"ibcmd returned {completed.returncode}: "
            f"{result.stderr[-2000:] or result.stdout[-2000:]}"
        )
    return result


def discover_ibcmd(
    ibcmd_executable: Path,
    mode: str = "infobase",
    *,
    timeout: int = 60,
    runner: Runner = subprocess.run,
) -> IbcmdResult:
    """Read capabilities from the installed executable's own help output."""

    if mode not in {"infobase", "server", "session", "lock"}:
        raise ValueError("mode must be infobase, server, session, or lock")
    return run_ibcmd(
        ibcmd_executable=ibcmd_executable,
        arguments=["help", mode],
        confirmed=False,
        timeout=timeout,
        runner=runner,
    )
