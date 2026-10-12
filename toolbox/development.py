from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid

import psutil

from .core import CONFIG, TEXT_LIMIT, bounded, resolve, tool

JOBS: dict = {}
JOB_LOCK = threading.RLock()


def kill_tree(process):
    if process.poll() is not None:
        return
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in reversed(children):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
        psutil.wait_procs(children + [parent], timeout=3)
    except psutil.NoSuchProcess:
        pass


def command_job(command: list[str], cwd: str, timeout: int, label: str, env=None) -> str:
    bounded(timeout, high=3600)
    if not command or not all(isinstance(arg, str) for arg in command):
        raise ValueError("Task command must be a nonempty string array")
    workdir = resolve(cwd, exists=True)
    if not workdir.is_dir():
        raise ValueError("Task working directory must be a directory")
    command = [sys.executable if arg == "{python}" else arg for arg in command]
    with JOB_LOCK:
        if sum(not job["done"].is_set() for job in JOBS.values()) >= 4:
            raise ValueError("At most four background jobs can run")
        if len(JOBS) >= 100:
            completed = [key for key, job in JOBS.items() if job["done"].is_set()]
            for key in completed[:50]:
                del JOBS[key]
        process = subprocess.Popen(command, cwd=workdir, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        ident = uuid.uuid4().hex
        job = {"id": ident, "task": label, "process": process, "status": "running",
               "started": time.time(), "output": bytearray(), "truncated": False,
               "done": threading.Event(), "returncode": None}
        JOBS[ident] = job
    def expire():
        with JOB_LOCK:
            if process.poll() is None and job["status"] == "running":
                job["status"] = "timed_out"
                kill_tree(process)
    def monitor():
        timer = threading.Timer(timeout, expire)
        timer.daemon = True
        timer.start()
        try:
            for chunk in iter(lambda: process.stdout.read1(8192), b""):
                with JOB_LOCK:
                    available = TEXT_LIMIT * 4 - len(job["output"])
                    job["output"].extend(chunk[:max(available, 0)])
                    if len(chunk) > available:
                        job["truncated"] = True
            code = process.wait()
            with JOB_LOCK:
                job["returncode"] = code
                if job["status"] == "running":
                    job["status"] = "succeeded" if code == 0 else "failed"
        except Exception as exc:
            with JOB_LOCK:
                job["status"] = "failed"
                job["error"] = str(exc)
            kill_tree(process)
        finally:
            timer.cancel()
            process.stdout.close()
            job["done"].set()
    threading.Thread(target=monitor, daemon=True, name="toolbox-job-" + ident).start()
    return ident


def snapshot(ident: str) -> dict:
    with JOB_LOCK:
        if ident not in JOBS:
            raise ValueError("Unknown job; jobs do not survive a server restart")
        job = JOBS[ident]
        text = bytes(job["output"]).decode("utf-8", errors="replace")
        return {"id": ident, "task": job["task"], "status": job["status"],
                "returncode": job["returncode"], "started_epoch": job["started"],
                "output": text[:TEXT_LIMIT], "truncated": job["truncated"] or len(text) > TEXT_LIMIT,
                "error": job.get("error")}


def task_start(name: str, cwd: str) -> str:
    task = CONFIG.get("tasks", {}).get(name)
    if not task:
        raise ValueError("Unknown task; configure a fixed command array in settings.json")
    return command_job(task["command"], task.get("cwd", cwd), int(task.get("timeout_seconds", 120)), name)


@tool("development")
def tasks_list() -> dict:
    """List named development commands configured by the user; arbitrary shell input is not accepted."""
    return {"tasks": [{"name": key, "description": value.get("description", ""),
                       "timeout_seconds": value.get("timeout_seconds", 120)}
                      for key, value in CONFIG.get("tasks", {}).items()]}


@tool("development", write=True)
def task_run(name: str, cwd: str = ".", wait_seconds: int = 20) -> dict:
    """Run a configured task and wait briefly; return a job ID if it is still running."""
    bounded(wait_seconds, high=30)
    ident = task_start(name, cwd)
    JOBS[ident]["done"].wait(wait_seconds)
    return snapshot(ident)


@tool("development", write=True)
def job_start(name: str, cwd: str = ".") -> dict:
    """Start a configured named task in the background with a timeout and bounded output."""
    return snapshot(task_start(name, cwd))


@tool("development")
def job_status(job_id: str) -> dict:
    """Read background task output, state and exit code."""
    return snapshot(job_id)


@tool("development", write=True, destructive=True)
def job_cancel(job_id: str) -> dict:
    """Cancel a toolbox background task and terminate its current process tree."""
    with JOB_LOCK:
        if job_id not in JOBS:
            raise ValueError("Unknown job")
        job = JOBS[job_id]
        if job["process"].poll() is None:
            job["status"] = "cancelled"
            kill_tree(job["process"])
    job["done"].wait(5)
    return snapshot(job_id)


@tool("development")
def jobs_list() -> dict:
    """List the most recent session-local jobs with status and task name."""
    with JOB_LOCK:
        return {"jobs": [{"id": key, "task": job["task"], "status": job["status"],
                          "returncode": job["returncode"]} for key, job in list(JOBS.items())[-100:]]}


def shutdown_jobs():
    with JOB_LOCK:
        jobs = list(JOBS.values())
    for job in jobs:
        if job["process"].poll() is None:
            kill_tree(job["process"])


def git(path: str, args: list[str]) -> dict:
    root = resolve(path, exists=True)
    if not root.is_dir():
        raise ValueError("Expected a repository directory")
    executable = CONFIG.get("git_executable") or shutil.which("git")
    if not executable:
        raise ValueError("Git executable not found")
    prefix = [executable, "--no-pager", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=", "-C", str(root)]
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    probe = subprocess.run(prefix + ["rev-parse", "--show-toplevel"], capture_output=True,
                           timeout=8, env=env, stdin=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if probe.returncode:
        raise ValueError("Path is not a Git working tree")
    resolve(probe.stdout.decode("utf-8", errors="replace").strip(), exists=True)
    ident = command_job(prefix + args, str(root), 20, "git:" + args[0], env=env)
    JOBS[ident]["done"].wait(25)
    result = snapshot(ident)
    if result["status"] != "succeeded":
        raise ValueError(result["output"] or f"Git {result['status']}")
    return {"output": result["output"], "truncated": result["truncated"]}


def revision(ref: str):
    if not re.fullmatch(r"[A-Za-z0-9_./~^:@{}+\-]{1,200}", ref) or ref.startswith("-"):
        raise ValueError("Invalid Git revision")
    return ref


@tool("git")
def git_status(path: str) -> dict:
    """Show Git branch and changed/untracked files without modifying the repository."""
    return git(path, ["status", "--short", "--branch", "--untracked-files=normal"])


@tool("git")
def git_diff(path: str, staged: bool = False) -> dict:
    """Show unstaged or staged Git diffs with external diff commands and text conversion disabled."""
    args = ["diff", "--no-ext-diff", "--no-textconv", "--ignore-submodules=all"]
    if staged:
        args.append("--cached")
    return git(path, args + ["--"])


@tool("git")
def git_log(path: str, limit: int = 20) -> dict:
    """Show recent Git commit hashes, timestamps and subjects."""
    bounded(limit, high=200)
    return git(path, ["log", f"-{limit}", "--format=%h %aI %s", "--"])


@tool("git")
def git_show(path: str, ref: str = "HEAD") -> dict:
    """Show a Git commit or blob by validated revision, without external diff helpers."""
    return git(path, ["show", "--no-ext-diff", "--no-textconv", "--format=fuller", revision(ref), "--"])


@tool("git")
def git_branches(path: str) -> dict:
    """List local and remote Git branches and their latest commit subjects."""
    return git(path, ["branch", "--all", "--no-color", "--format=%(refname:short) %(objectname:short) %(subject)"])
