"""MCP client: lets CivicPulse agents call tools on external Model Context Protocol servers.

Servers are declared in ``backend/mcp_servers.json`` (or CIVIC_MCP_CONFIG); if that file is missing, the
bundled rainfall server is used. Each entry is a stdio server:

    {"servers": {"rainfall": {"command": "python", "args": ["-m", "mcp_servers.rainfall_server"]}}}

Design
  * One background asyncio loop thread owns every session; agents call the synchronous ``call()``.
  * Sessions are persistent: the server process is spawned and initialised once, then reused, so a tool
    call costs one JSON-RPC round trip instead of a process start + handshake.
  * Results are cached per (server, tool, args) for a caller-chosen TTL.
  * Every call has a timeout. Failures return None, and a server that fails to start is not retried for
    60 s, so a missing dependency or offline network can never stall the pipeline (POL-AI-003).
  * Tool output is data: callers validate it before use and it is never fed to an LLM as instructions.

Disable entirely with CIVIC_MCP=off.
"""
import asyncio
import json
import logging
import os
import sys
import threading
import time
from concurrent.futures import TimeoutError as FutTimeout

log = logging.getLogger("civic.mcp")
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_PATH = os.environ.get("CIVIC_MCP_CONFIG", os.path.join(BACKEND_DIR, "mcp_servers.json"))
RETRY_AFTER_S = 60
CONNECT_TIMEOUT_S = 20

DEFAULT_SERVERS = {
    "rainfall": {"command": sys.executable, "args": ["-m", "mcp_servers.rainfall_server"], "cwd": BACKEND_DIR,
                 "description": "Open-Meteo rainfall forecast (bundled)"},
}


def load_config(path: str = CONFIG_PATH) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            servers = json.load(f).get("servers", {})
        for spec in servers.values():
            if spec.get("command") in ("python", "python3"):
                spec["command"] = sys.executable          # same interpreter/venv as the backend
            spec.setdefault("cwd", BACKEND_DIR)
        return servers
    return dict(DEFAULT_SERVERS)


class MCPHub:
    def __init__(self, servers: dict | None = None, enabled: bool | None = None):
        self.servers = servers if servers is not None else load_config()
        self.enabled = enabled if enabled is not None else os.environ.get("CIVIC_MCP", "on").lower() != "off"
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop: asyncio.Event | None = None
        self._sessions: dict = {}
        self._tasks: dict = {}
        self._tools: dict[str, list] = {}
        self._errors: dict[str, str] = {}
        self._failed_at: dict[str, float] = {}
        self._cache: dict = {}
        self._lock = threading.Lock()
        self.stats = {"calls": 0, "cache_hits": 0, "failures": 0, "total_ms": 0.0, "connects": 0}

    # ---- loop management ----
    def _ensure_loop(self):
        with self._lock:
            if self._loop is None:
                ready = threading.Event()

                def run():
                    self._loop = asyncio.new_event_loop()   # Proactor on Windows: supports subprocess pipes
                    asyncio.set_event_loop(self._loop)
                    self._stop = asyncio.Event()
                    ready.set()
                    self._loop.run_forever()

                self._thread = threading.Thread(target=run, name="mcp-client", daemon=True)
                self._thread.start()
                ready.wait(5)

    async def _serve(self, name: str, spec: dict, ready: asyncio.Future):
        """Own one server's lifetime inside a single task (anyio cancel scopes must not cross tasks)."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        params = StdioServerParameters(command=spec["command"], args=spec.get("args", []),
                                       env={**os.environ, **spec.get("env", {})}, cwd=spec.get("cwd"))
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    self._tools[name] = [{"name": t.name, "description": (t.description or "").strip().split("\n")[0]}
                                         for t in tools.tools]
                    self._sessions[name] = session
                    self._errors.pop(name, None)
                    self.stats["connects"] += 1
                    if not ready.done():
                        ready.set_result(True)
                    await self._stop.wait()
        except BaseException as e:  # noqa: BLE001 - includes anyio ExceptionGroups and cancellation
            self._errors[name] = f"{type(e).__name__}: {e}"[:300]
            if not ready.done():
                ready.set_exception(RuntimeError(self._errors[name]))
            if isinstance(e, asyncio.CancelledError):
                raise
        finally:
            self._sessions.pop(name, None)

    async def _start(self, name: str):
        ready = self._loop.create_future()
        self._tasks[name] = asyncio.create_task(self._serve(name, self.servers[name], ready))
        await asyncio.wait_for(ready, CONNECT_TIMEOUT_S)

    def _connect(self, name: str) -> bool:
        if name in self._sessions:
            return True
        if time.time() - self._failed_at.get(name, 0) < RETRY_AFTER_S:
            return False
        self._ensure_loop()
        try:
            asyncio.run_coroutine_threadsafe(self._start(name), self._loop).result(CONNECT_TIMEOUT_S + 2)
            return name in self._sessions
        except Exception as e:
            self._failed_at[name] = time.time()
            self._errors[name] = self._errors.get(name) or f"{type(e).__name__}: {e}"[:300]
            log.warning("MCP server '%s' unavailable: %s", name, self._errors[name])
            return False

    # ---- public API ----
    def call(self, server: str, tool: str, args: dict | None = None, timeout: float = 15, ttl: float = 0) -> dict | None:
        """Call *tool* on *server*. Returns the tool's structured result (dict) or None on any failure."""
        if not self.enabled or server not in self.servers:
            return None
        args = args or {}
        key = (server, tool, json.dumps(args, sort_keys=True))
        if ttl > 0:
            hit = self._cache.get(key)
            if hit and time.time() - hit[0] < ttl:
                self.stats["cache_hits"] += 1
                return hit[1]
        if not self._connect(server):
            return None
        t0 = time.perf_counter()
        fut = None
        try:
            session = self._sessions.get(server)
            if session is None:
                raise RuntimeError("session closed")
            fut = asyncio.run_coroutine_threadsafe(session.call_tool(tool, args), self._loop)
            res = fut.result(timeout)
            if res.isError:
                raise RuntimeError(" ".join(getattr(c, "text", "") for c in res.content)[:300] or "tool error")
            data = res.structuredContent
            if data is None:
                text = "".join(getattr(c, "text", "") for c in res.content)
                data = json.loads(text) if text else {}
            if isinstance(data, dict) and set(data) == {"result"}:   # FastMCP wraps non-dict returns
                data = data["result"]
            self._cache[key] = (time.time(), data)
            return data
        except (FutTimeout, Exception) as e:
            self.stats["failures"] += 1
            self._errors[server] = f"{tool}: {type(e).__name__}: {e}"[:300]
            log.warning("MCP call %s/%s failed: %s", server, tool, self._errors[server])
            if fut is not None and isinstance(e, FutTimeout):
                fut.cancel()
            task = self._tasks.get(server)
            if task is not None and task.done():          # server process died: let the next call reconnect
                self._sessions.pop(server, None)
            return None
        finally:
            self.stats["calls"] += 1
            self.stats["total_ms"] += (time.perf_counter() - t0) * 1000

    def status(self, connect: bool = False) -> dict:
        if connect and self.enabled:
            for name in self.servers:
                self._connect(name)
        calls = self.stats["calls"]
        return {
            "enabled": self.enabled, "config": CONFIG_PATH if os.path.exists(CONFIG_PATH) else "built-in defaults",
            "servers": [{"name": n, "description": s.get("description", ""), "connected": n in self._sessions,
                         "tools": self._tools.get(n, []), "last_error": self._errors.get(n)} for n, s in self.servers.items()],
            "stats": {**{k: v for k, v in self.stats.items() if k != "total_ms"},
                      "mean_ms": round(self.stats["total_ms"] / calls, 1) if calls else 0},
        }

    def close(self):
        if self._loop is None:
            return

        async def _shutdown():
            self._stop.set()
            tasks = list(self._tasks.values())
            if tasks:
                await asyncio.wait(tasks, timeout=5)
        try:
            asyncio.run_coroutine_threadsafe(_shutdown(), self._loop).result(7)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(3)
        self._loop = None
        self._sessions.clear()
        self._tasks.clear()


HUB = MCPHub()
