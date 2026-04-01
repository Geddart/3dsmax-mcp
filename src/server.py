import importlib
import logging
import os
import tomllib
from functools import lru_cache
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .max_client import MaxClientManager

logging.basicConfig(level=logging.INFO, format="%(message)s")

mcp = FastMCP("3dsmax-mcp")
client = MaxClientManager()

# --- Core tools (always loaded) ---
from .tools import (  # noqa: E402, F401
    execute, scene, objects, materials, render, viewport, identify,
    transform, hierarchy, modifiers, selection, clone, scene_manage,
    visibility, inspect, build, grid, floor_plan, scene_query, effects,
    material_ops, material_replace, state_sets, data_channel, wire_params,
    controllers, scattering, instances, capabilities, snapshots,
    verification, session_context, bridge, workflows, file_access,
    organize, learning,
)

# --- Plugin tools (loaded based on plugins.toml or env var) ---
_PLUGIN_MODULES = [
    "redshift", "tyflow", "rpmanager", "railclone", "forest_pack",
    "plugins", "plugin_workflows",
]

_plugins_toml = Path(__file__).resolve().parent / "plugins.toml"
_plugin_enabled: dict[str, bool] = {}
if _plugins_toml.exists():
    with open(_plugins_toml, "rb") as _f:
        _plugin_enabled = tomllib.load(_f).get("plugins", {})

# Env var override: 3DSMAX_MCP_PLUGINS=redshift,forest_pack
_env_override = os.environ.get("3DSMAX_MCP_PLUGINS")
if _env_override is not None:
    _allowed = {s.strip() for s in _env_override.split(",") if s.strip()}
    _plugin_enabled = {mod: mod in _allowed for mod in _PLUGIN_MODULES}

for _mod in _PLUGIN_MODULES:
    if _plugin_enabled.get(_mod, True):  # default: enabled if not in config
        try:
            importlib.import_module(f".tools.{_mod}", package=__package__)
        except ImportError:
            pass  # Plugin file doesn't exist yet
        except Exception as _exc:
            logging.warning("Failed to load plugin %s: %s", _mod, _exc)


SKILL_RESOURCE_URI = "resource://3dsmax-mcp/skill"
SKILL_FILE = (
    Path(__file__).resolve().parent.parent / "skills" / "3dsmax-mcp-dev" / "SKILL.md"
)


@lru_cache(maxsize=1)
def _read_skill_file() -> str:
    """Read the local skill guide once and cache it for prompt/resource calls."""
    try:
        return SKILL_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        logging.warning("Skill file not found: %s", SKILL_FILE)
        return "Skill file not found."
    except OSError as exc:
        logging.warning("Could not read skill file %s: %s", SKILL_FILE, exc)
        return "Skill file could not be loaded."


@mcp.resource(SKILL_RESOURCE_URI)
def get_skill() -> str:
    """3ds Max MCP development guide exposed as an MCP resource."""
    return _read_skill_file()


@mcp.prompt()
def max_assistant() -> str:
    """Default assistant instructions for MCP clients like Claude Desktop."""
    base_rules = (
        "You are a 3ds Max assistant connected via MCP.\n"
        "Use get_bridge_status if connection health or host state is uncertain.\n"
        "Start with get_session_context for fast live context when the scene state matters.\n"
        "Use inspect_active_target when you need the most relevant current target without manually deciding between selection and scene context.\n"
        "Use get_scene_snapshot / get_selection_snapshot when you need a smaller follow-up probe.\n"
        "Use inspect_track_view to browse an object's animation/controller hierarchy before targeting a specific param_path.\n"
        "When working with plugins or unfamiliar classes, start with discover_plugin_surface or get_plugin_manifest.\n"
        "Use inspect_plugin_class before making assumptions about a plugin class surface.\n"
        "Use inspect_plugin_instance for live plugin objects when generic object inspection is too shallow.\n"
        "Plugin resources are available under resource://3dsmax-mcp/plugins/{plugin_name}/manifest, /guide, /recipes, and /gotchas.\n"
        "For tyFlow maintenance, inspect with get_tyflow_info first; enable include_flow_properties/include_event_properties/include_operator_properties for deep readback before edits.\n"
        "For tyFlow creation/mutation, use create_tyflow, modify_tyflow_operator, set_tyflow_shape, set_tyflow_physx, and get_tyflow_particles.\n"
        "For fast onboarding tyFlow recipes, prefer create_tyflow_basic_verified or create_tyflow_scatter_from_objects_verified.\n"
        "For RailClone maintenance, use get_railclone_style_graph to read the exposed style graph (bases/segments/parameters) before edits.\n"
        "Prefer dedicated tools over raw MAXScript when available.\n"
        "Inspect objects/properties before edits.\n"
        "After any meaningful mutation, verify with a verification tool or get_scene_delta.\n"
        "Prefer verified workflow tools when available so action and verification stay coupled.\n"
        "Use set_material_verified and add_modifier_verified for common iterative edits.\n"
        "Use transform_object_verified and set_modifier_state_verified for geometry iteration without manual readback stitching.\n"
        "Use set_object_property_verified for direct object-level edits when no narrower verified wrapper exists.\n"
        "Work in natural language with the user, but keep tool usage structured and explicit.\n"
        "DO NOT render unless the user asks.\n"
        "Use capture_viewport/capture_model for fast viewport context. capture_screen is fullscreen and requires enabled=True.\n"
        f"Reference resource: {SKILL_RESOURCE_URI}\n"
    )
    return f"{base_rules}\nFull reference:\n\n{_read_skill_file()}"


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
