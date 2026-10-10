"""MCP smoke test: the server starts and answers the stdio handshake.

No real config dump needed: the server must boot, complete initialize,
and list its tools. Run from the repository root:

    python scripts/mcp_smoke.py

Exit code 0 = smoke passed.
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_MIN_TOOLS = 80


async def run_smoke() -> int:
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "mcp_devtools",
        cwd=str(ROOT),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    async def send(msg: dict) -> None:
        proc.stdin.write((json.dumps(msg) + "\n").encode())
        await proc.stdin.drain()

    async def recv() -> dict:
        while True:
            line = await proc.stdout.readline()
            if not line:
                raise RuntimeError("server closed stdout before answering")
            line = line.strip()
            if line.startswith(b"{"):
                return json.loads(line)

    try:
        await send({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-smoke", "version": "0"},
            },
        })
        init = await recv()
        name = init["result"]["serverInfo"]["name"]
        print(f"initialize OK: {name}")

        await send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        await send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = await recv()
        tool_names = [t["name"] for t in tools["result"]["tools"]]
        print(f"tools/list OK: {len(tool_names)} tools")

        missing = [t for t in ("graph.stats", "std.search", "meta.tree") if t not in tool_names]
        if missing:
            print(f"FAIL: expected tools missing: {missing}")
            return 1
        if len(tool_names) < EXPECTED_MIN_TOOLS:
            print(f"FAIL: expected >= {EXPECTED_MIN_TOOLS} tools, got {len(tool_names)}")
            return 1

        print("smoke PASSED")
        return 0
    finally:
        try:
            proc.kill()
        except ProcessLookupError:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_smoke()))
