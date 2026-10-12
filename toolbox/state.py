from __future__ import annotations

import json
import platform
import sqlite3
import time

import psutil

from .core import BASE, CATALOG, CONFIG, ROOTS, STATE, TEXT_LIMIT, bounded, tool


def memory_connection():
    con = sqlite3.connect(STATE / "memory.sqlite3", timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS memories (namespace TEXT, key TEXT, value TEXT, updated REAL, PRIMARY KEY(namespace,key))")
    return con


def memory_keys(namespace, key):
    if not namespace or not key or len(namespace) > 100 or len(key) > 200:
        raise ValueError("namespace/key must be nonempty and bounded")


@tool("memory", write=True)
def memory_put(namespace: str, key: str, value: str) -> dict:
    """Persist a named note across server restarts; do not store passwords or API keys."""
    memory_keys(namespace, key)
    if len(value) > TEXT_LIMIT:
        raise ValueError("Memory value exceeds text limit")
    con = memory_connection()
    try:
        with con:
            con.execute("INSERT INTO memories VALUES (?,?,?,?) ON CONFLICT(namespace,key) DO UPDATE SET value=excluded.value,updated=excluded.updated", (namespace, key, value, time.time()))
        return {"namespace": namespace, "key": key, "saved": True}
    finally:
        con.close()


@tool("memory")
def memory_get(namespace: str, key: str) -> dict:
    """Read a persisted note by namespace and key."""
    memory_keys(namespace, key)
    con = memory_connection()
    try:
        row = con.execute("SELECT value,updated FROM memories WHERE namespace=? AND key=?", (namespace, key)).fetchone()
        return {"found": row is not None, "value": row[0] if row else None, "updated": row[1] if row else None}
    finally:
        con.close()


@tool("memory")
def memory_search(query: str = "", namespace: str = "", limit: int = 50) -> dict:
    """Search persisted note keys and values by literal substring."""
    bounded(limit, high=200)
    con = memory_connection()
    try:
        rows = con.execute("SELECT namespace,key,value,updated FROM memories WHERE (?='' OR namespace=?) AND (instr(key,?)>0 OR instr(value,?)>0) ORDER BY updated DESC LIMIT ?", (namespace, namespace, query, query, limit + 1)).fetchall()
        items, chars = [], 0
        for row in rows[:limit]:
            item = dict(zip(["namespace", "key", "value", "updated"], row))
            size = len(json.dumps(item, ensure_ascii=False))
            if chars + size > TEXT_LIMIT:
                break
            items.append(item)
            chars += size
        return {"memories": items, "truncated": len(items) < len(rows)}
    finally:
        con.close()


@tool("memory", write=True, destructive=True)
def memory_delete(namespace: str, key: str) -> dict:
    """Delete one explicitly named persisted note."""
    memory_keys(namespace, key)
    con = memory_connection()
    try:
        with con:
            result = con.execute("DELETE FROM memories WHERE namespace=? AND key=?", (namespace, key))
        return {"deleted": bool(result.rowcount)}
    finally:
        con.close()


@tool("system")
def toolbox_health() -> dict:
    """Show toolbox version, allowed roots, enabled modules, tool count and configured integrations."""
    return {"name": "codex-toolbox", "version": "1.0.0", "transport": "stdio",
            "allowed_roots": [str(p) for p in ROOTS], "modules": CONFIG.get("modules", []),
            "tool_count": len(CATALOG), "sqlite_writes": CONFIG.get("sqlite_writes", False),
            "services": list(CONFIG.get("services", {})), "tasks": list(CONFIG.get("tasks", {})),
            "note": "Restart the MCP server after changing settings. Background jobs are session-local."}


@tool("system")
def system_info() -> dict:
    """Return OS, Python, CPU, memory and allowed-root disk usage without environment secrets."""
    memory = psutil.virtual_memory()
    return {"os": platform.platform(), "python": platform.python_version(),
            "cpu_count": psutil.cpu_count(), "memory_total": memory.total,
            "memory_available": memory.available, "memory_percent": memory.percent,
            "disks": [{"root": str(p), "total": psutil.disk_usage(str(p)).total,
                       "free": psutil.disk_usage(str(p)).free} for p in ROOTS]}


@tool("system")
def processes_list(name_filter: str = "", limit: int = 100) -> dict:
    """List process names, PIDs and memory usage; command lines and environment variables are excluded."""
    bounded(limit)
    rows = []
    for process in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            item = process.info
            if name_filter.casefold() not in (item["name"] or "").casefold():
                continue
            rows.append({"pid": item["pid"], "name": item["name"],
                         "memory_bytes": item["memory_info"].rss if item["memory_info"] else None})
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return {"processes": rows[:limit], "truncated": len(rows) > limit}


@tool("system")
def ports_list(limit: int = 100) -> dict:
    """List listening TCP ports and process IDs where OS permissions allow."""
    bounded(limit)
    rows = [{"address": item.laddr.ip, "port": item.laddr.port, "pid": item.pid}
            for item in psutil.net_connections(kind="tcp") if item.status == psutil.CONN_LISTEN]
    return {"ports": rows[:limit], "truncated": len(rows) > limit}


@tool("system")
def audit_tail(limit: int = 50) -> dict:
    """Read recent tool names, success status and timing; logs do not store tool arguments or results."""
    from collections import deque
    bounded(limit, high=200)
    path = STATE / "audit.jsonl"
    if not path.exists():
        return {"events": []}
    with path.open(encoding="utf-8") as f:
        lines = deque(f, maxlen=limit)
    return {"events": [json.loads(line) for line in lines]}
