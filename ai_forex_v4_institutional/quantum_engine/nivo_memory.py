"""
nivo_memory.py — Nivo FX RAM Manager
=====================================
Provides aggressive memory release after each bot cycle.

KEY INSIGHT: Python's `gc.collect()` destroys Python objects but does NOT
return memory to the OS — CPython keeps it in its internal allocator pool
(PyMalloc). To actually free RAM visible in `htop`, you must call
`malloc_trim(0)` from glibc, which forces the OS-level heap trim.

Usage:
    from quantum_engine.nivo_memory import release_memory
    release_memory(logger=logger)   # call after each cycle's finally block
"""

import gc
import logging
import os
import ctypes
import ctypes.util

# Try to load glibc for malloc_trim (Linux only — silently skips on other OS)
_libc = None
try:
    _libc_path = ctypes.util.find_library("c")
    if _libc_path:
        _libc = ctypes.CDLL(_libc_path)
except Exception:
    pass


def _get_ram_usage_mb() -> float:
    """Reads current RSS (Resident Set Size) in MB from /proc/self/status."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        pass
    return 0.0


def _get_system_ram_mb() -> dict:
    """Returns used/total system RAM from /proc/meminfo in MB."""
    info = {"used": 0.0, "total": 0.0, "available": 0.0}
    try:
        meminfo = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    meminfo[parts[0].rstrip(":")] = int(parts[1])
        total = meminfo.get("MemTotal", 0) / 1024.0
        avail = meminfo.get("MemAvailable", 0) / 1024.0
        info["total"] = round(total, 1)
        info["available"] = round(avail, 1)
        info["used"] = round(total - avail, 1)
    except Exception:
        pass
    return info


def release_memory(logger: logging.Logger = None) -> dict:
    """
    Performs a full 3-stage memory release:
      1. gc.collect(2)   — Full generational garbage collection
      2. malloc_trim(0)  — Forces glibc to return unused heap pages to the OS
      3. Reports RAM delta in MB

    Returns a dict with before/after stats for logging.
    """
    log = logger or logging.getLogger(__name__)

    # --- Stage 1: Read RAM before ---
    proc_before = _get_ram_usage_mb()
    sys_before = _get_system_ram_mb()

    # --- Stage 2: Python GC (all 3 generations) ---
    collected = gc.collect(2)

    # --- Stage 3: OS-level heap trim (Linux/glibc only) ---
    trimmed = False
    if _libc is not None:
        try:
            _libc.malloc_trim(0)
            trimmed = True
        except Exception:
            pass

    # --- Stage 4: Read RAM after ---
    proc_after = _get_ram_usage_mb()
    sys_after = _get_system_ram_mb()

    proc_freed = proc_before - proc_after
    sys_freed = sys_before["used"] - sys_after["used"]

    log.info(
        f"[RAM RELEASE] 🧹 GC collected {collected} objects | "
        f"malloc_trim={'✅' if trimmed else '⚠️ (non-Linux)'} | "
        f"Process: {proc_before:.0f}→{proc_after:.0f} MB (freed {proc_freed:+.0f} MB) | "
        f"System: {sys_before['used']:.0f}/{sys_before['total']:.0f} MB "
        f"→ {sys_after['used']:.0f}/{sys_after['total']:.0f} MB"
    )

    # Warn if system RAM is critically high (>85% used)
    if sys_after["total"] > 0:
        pct = sys_after["used"] / sys_after["total"] * 100
        if pct > 85:
            log.warning(
                f"[RAM ALERT] ⚠️ System RAM at {pct:.0f}% ({sys_after['used']:.0f}/{sys_after['total']:.0f} MB). "
                f"Consider rebooting services if this persists."
            )

    return {
        "gc_objects_collected": collected,
        "malloc_trim_used": trimmed,
        "proc_before_mb": proc_before,
        "proc_after_mb": proc_after,
        "proc_freed_mb": proc_freed,
        "sys_before_mb": sys_before["used"],
        "sys_after_mb": sys_after["used"],
    }
