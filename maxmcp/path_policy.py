"""Where MCP write tools may create or overwrite files.

Safe mode (``[mcp] safe_mode``) is a substring blocklist on raw MAXScript; it
cannot reason about paths. Tools that take an output path (geometry export,
versioned save-as, EXR renders, job files) instead call
:func:`resolve_write_path`, which allows a path only when it lies inside

* a directory listed in ``[safe_mode] allowed_dirs`` of
  ``%LOCALAPPDATA%\\3dsmax-mcp\\mcp_config.ini`` (``;``- or newline-separated),
  or in the ``MCP_ALLOWED_DIRS`` environment variable,
* the folder of the scene currently open in that Max (passed by the caller),
* the MCP temp area ``%TEMP%\\3dsmax-mcp``.

``execute_maxscript`` is NOT governed by this policy; it stays under safe mode.
Paths are resolved (``..`` collapsed) and compared case-insensitively, so
``N:\\Proj\\..\\Other`` cannot escape an allowed root.
"""
from __future__ import annotations

import configparser
import os
import tempfile
from pathlib import Path

ALLOWED_ENV = "MCP_ALLOWED_DIRS"
CONFIG_SECTION = "safe_mode"
CONFIG_KEY = "allowed_dirs"


class PathNotAllowedError(ValueError):
    """A write tool was asked to write outside every allowed root."""


def config_path() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    base = Path(root) if root else Path.home() / "AppData" / "Local"
    return base / "3dsmax-mcp" / "mcp_config.ini"


def _split(value: str) -> list[str]:
    parts: list[str] = []
    for chunk in value.replace("\r", "\n").replace(";", "\n").split("\n"):
        chunk = chunk.strip().strip('"')
        if chunk:
            parts.append(chunk)
    return parts


def temp_root() -> Path:
    return Path(tempfile.gettempdir()) / "3dsmax-mcp"


def configured_dirs() -> list[Path]:
    """Allowed roots from the config file and the environment (no scene/temp)."""
    raw: list[str] = []
    parser = configparser.ConfigParser()
    try:
        parser.read(config_path(), encoding="utf-8-sig")
        raw += _split(parser.get(CONFIG_SECTION, CONFIG_KEY, fallback=""))
    except (OSError, configparser.Error):
        pass
    raw += _split(os.environ.get(ALLOWED_ENV, ""))
    seen: set[str] = set()
    out: list[Path] = []
    for item in raw:
        p = _normalize(item)
        key = os.path.normcase(str(p))
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _normalize(path: str | os.PathLike[str]) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(str(path)))
    return Path(os.path.abspath(expanded))


def _inside(path: Path, root: Path) -> bool:
    p = os.path.normcase(str(path))
    r = os.path.normcase(str(root)).rstrip("\\/")
    return p == r or p.startswith(r + os.sep)


def allowed_roots(scene_dir: str | os.PathLike[str] | None = None) -> list[Path]:
    roots = configured_dirs()
    if scene_dir:
        roots.append(_normalize(scene_dir))
    roots.append(_normalize(temp_root()))
    return roots


def resolve_write_path(path: str | os.PathLike[str], *, scene_dir: str | os.PathLike[str] | None = None) -> Path:
    """Return the absolute path if writing there is allowed, else raise PathNotAllowedError."""
    if not str(path).strip():
        raise PathNotAllowedError("An output path is required")
    candidate = _normalize(path)
    roots = allowed_roots(scene_dir)
    if any(_inside(candidate, root) for root in roots):
        return candidate
    listed = "; ".join(str(r) for r in roots)
    raise PathNotAllowedError(
        f"Refusing to write {candidate}: outside the allowed folders ({listed}). "
        f"Add the project folder to [{CONFIG_SECTION}] {CONFIG_KEY} in {config_path()} "
        f"or the {ALLOWED_ENV} environment variable."
    )
