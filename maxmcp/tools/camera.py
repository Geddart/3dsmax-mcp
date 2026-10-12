"""Camera match tools: build cameras from solved data, export/import them as
JSON, project world points to render pixels and capture the exact camera
frame over a background plate.

Conventions (verified live against Scanline renders of marker spheres):

* Camera space is the node transform: row1 = right (+X), row2 = up (+Y),
  row3 = back (+Z). A Max camera looks down -back.
* ``fov_deg`` is the horizontal field of view Max reports in ``camera.fov``.
  For the Physical camera it already includes lens breathing and zoom.
* ``f_px = (render_width / 2) / tan(fov / 2)``.
* Pixel coordinates are continuous, origin at the top-left corner of the
  render frame, x right, y down; the centre of the first pixel is (0.5, 0.5).
* ``shift_x`` / ``shift_y`` are the Physical camera's ``horizontal_shift`` /
  ``vertical_shift`` divided by 100: fractions of the render WIDTH on both
  axes. Positive shift_x moves the principal point right, positive shift_y
  moves it up: ``cx = W/2 + shift_x*W``, ``cy = H/2 - shift_y*W*pixel_aspect``.
* Floats travel from Max as IEEE-754 bit patterns (``bit.floatAsInt``) and to
  Max as fixed-point literals, so nothing depends on the Windows locale.
"""
from __future__ import annotations

import glob
import json
import math
import os
import struct
import uuid
from typing import Any, Sequence

from .. import path_policy
from ..helpers.maxscript import safe_string
from ..server import client, mcp

SCHEMA = "3dsmax-mcp/camera@1"
ORTHO_TOLERANCE = 1e-4      # basis deviation accepted as-is
MAX_CORRECTION = 0.05       # basis deviation re-orthonormalised (with a warning)
POS_TOLERANCE = 1e-5        # relative position readback tolerance
AXIS_TOLERANCE = 1e-5
FOV_TOLERANCE_DEG = 1e-4
SHIFT_TOLERANCE = 1e-5

_PHYSICAL_PROPS = (
    "horizontal_shift", "vertical_shift", "film_width_mm", "focal_length_mm",
    "specify_fov", "lens_breathing_amount", "zoom_factor",
    "horizontal_tilt_correction", "vertical_tilt_correction",
    "auto_vertical_tilt_correction", "distortion_type", "distortion_cubic_amount",
    "clip_on", "clip_near", "clip_far", "targeted", "target_distance",
)
_STANDARD_PROPS = ("clipManually", "nearclip", "farclip", "orthoProjection", "fovType")
_READ_PROPS = _PHYSICAL_PROPS + _STANDARD_PROPS
_STANDARD_CLASSES = ("Freecamera", "Targetcamera")
_SUPPORTED_CLASSES = ("Physical",) + _STANDARD_CLASSES


class CameraReadbackError(RuntimeError):
    """A camera property read back from Max differs from what was written."""


# ── small vector helpers ─────────────────────────────────────────────

Vec = tuple[float, float, float]


def _vec(v: Sequence[float], label: str) -> Vec:
    if v is None or len(v) != 3:
        raise ValueError(f"{label} must be three numbers [x, y, z]")
    out = tuple(float(c) for c in v)
    if not all(math.isfinite(c) for c in out):
        raise ValueError(f"{label} contains a non-finite value: {list(v)}")
    return out  # type: ignore[return-value]


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(a: Vec, s: float) -> Vec:
    return (a[0] * s, a[1] * s, a[2] * s)


def _norm(a: Vec) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a: Vec, label: str) -> Vec:
    n = _norm(a)
    if n < 1e-9:
        raise ValueError(f"degenerate {label}: zero-length vector")
    return _scale(a, 1.0 / n)


# ── basis validation ─────────────────────────────────────────────────

def basis_deviation(right: Vec, up: Vec, back: Vec) -> float:
    """Largest departure from an orthonormal basis (unit lengths, zero dots)."""
    return max(
        abs(1.0 - _norm(right)), abs(1.0 - _norm(up)), abs(1.0 - _norm(back)),
        abs(_dot(right, up)), abs(_dot(right, back)), abs(_dot(up, back)),
    )


def orthonormalize_basis(
    right: Sequence[float],
    up: Sequence[float],
    back: Sequence[float],
    *,
    tolerance: float = ORTHO_TOLERANCE,
    max_correction: float = MAX_CORRECTION,
) -> tuple[Vec, Vec, Vec, float, bool]:
    """Validate a right/up/back camera basis and return it orthonormalised.

    The view direction (back) is kept exactly, up is made perpendicular to it
    and right is rebuilt as up x back. Returns (right, up, back, deviation,
    corrected). Raises ValueError for degenerate, left-handed or grossly
    non-orthonormal input.
    """
    r, u, b = _vec(right, "right"), _vec(up, "up"), _vec(back, "back")
    for label, v in (("right", r), ("up", u), ("back", b)):
        if _norm(v) < 1e-9:
            raise ValueError(f"degenerate basis: {label} is a zero vector")
    deviation = basis_deviation(r, u, b)
    if deviation > max_correction:
        raise ValueError(
            f"basis is not orthonormal (max deviation {deviation:.4g} > {max_correction}); "
            "pass right/up/back as unit vectors at right angles"
        )
    if _dot(_cross(r, u), b) <= 0.0:
        raise ValueError("basis is left-handed or degenerate: right x up must point along back")
    bn = _unit(b, "back")
    un = _unit(_sub(u, _scale(bn, _dot(u, bn))), "up (parallel to back)")
    rn = _cross(un, bn)
    if _dot(rn, _unit(r, "right")) < 1.0 - 2.0 * max_correction:
        raise ValueError("right does not agree with up x back")
    return rn, un, bn, deviation, deviation > tolerance


def look_at_basis(
    position: Sequence[float], target: Sequence[float], up_hint: Sequence[float] | None = None
) -> tuple[Vec, Vec, Vec, list[str]]:
    """Basis for a camera at position looking at target with no roll."""
    warnings: list[str] = []
    p, t = _vec(position, "position"), _vec(target, "target")
    hint = _vec(up_hint, "up_hint") if up_hint is not None else (0.0, 0.0, 1.0)
    back = _unit(_sub(p, t), "view direction (position equals target)")
    hint = _unit(hint, "up_hint")
    side = _cross(hint, back)
    if _norm(side) < 1e-6:
        fallback = (0.0, 1.0, 0.0) if abs(back[1]) < 0.9 else (1.0, 0.0, 0.0)
        warnings.append(f"view direction is parallel to up_hint; using {list(fallback)} as up hint")
        side = _cross(fallback, back)
    right = _unit(side, "right")
    up = _cross(back, right)
    return right, up, back, warnings


# ── lens helpers ─────────────────────────────────────────────────────

def fov_from_f_px(f_px: float, render_width: float) -> float:
    if f_px <= 0 or render_width <= 0:
        raise ValueError("f_px and render_width must be positive")
    return math.degrees(2.0 * math.atan((render_width / 2.0) / f_px))


def f_px_from_fov(fov_deg: float, render_width: float) -> float:
    if not 0.0 < fov_deg < 180.0:
        raise ValueError("fov_deg must be between 0 and 180")
    return (render_width / 2.0) / math.tan(math.radians(fov_deg) / 2.0)


def fov_from_focal_mm(focal_mm: float, film_width_mm: float) -> float:
    if focal_mm <= 0 or film_width_mm <= 0:
        raise ValueError("focal_mm and film_width_mm must be positive")
    return math.degrees(2.0 * math.atan(film_width_mm / (2.0 * focal_mm)))


def focal_mm_from_fov(fov_deg: float, film_width_mm: float) -> float:
    if not 0.0 < fov_deg < 180.0:
        raise ValueError("fov_deg must be between 0 and 180")
    return film_width_mm / (2.0 * math.tan(math.radians(fov_deg) / 2.0))


# ── projection ───────────────────────────────────────────────────────

def principal_point(cam: dict[str, Any]) -> tuple[float, float]:
    w, h = float(cam["render_width"]), float(cam["render_height"])
    pa = float(cam.get("pixel_aspect", 1.0) or 1.0)
    return (w / 2.0 + float(cam.get("shift_x", 0.0)) * w,
            h / 2.0 - float(cam.get("shift_y", 0.0)) * w * pa)


def project_camera_points(cam: dict[str, Any], points: Sequence[Sequence[float]]) -> list[dict[str, Any]]:
    """Project world points through a camera dict (export_camera schema)."""
    pos = _vec(cam["position"], "position")
    right, up, back = (_vec(cam[k], k) for k in ("right", "up", "back"))
    w, h = float(cam["render_width"]), float(cam["render_height"])
    pa = float(cam.get("pixel_aspect", 1.0) or 1.0)
    fpx = f_px_from_fov(float(cam["fov_deg"]), w)
    cx, cy = principal_point(cam)
    near = cam.get("near")
    far = cam.get("far")
    out: list[dict[str, Any]] = []
    for index, raw in enumerate(points):
        p = _vec(raw, f"points[{index}]")
        d = _sub(p, pos)
        xc, yc, zc = _dot(d, right), _dot(d, up), _dot(d, back)
        depth = -zc
        item: dict[str, Any] = {"depth": depth}
        if depth <= 1e-9:
            item.update(x=None, y=None, behind=True, in_frame=False)
        else:
            x = cx + fpx * xc / depth
            y = cy - fpx * pa * yc / depth
            item.update(x=x, y=y, behind=False, in_frame=(0.0 <= x <= w and 0.0 <= y <= h))
        if near is not None or far is not None:
            item["clipped"] = bool(depth <= 0 or (near is not None and depth < near) or (far is not None and depth > far))
        out.append(item)
    return out


# ── Max transport ────────────────────────────────────────────────────

def _msf(value: float) -> str:
    """Locale-free MAXScript float literal."""
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(f"non-finite number {value!r}")
    text = f"{v:.10f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return "0.0" if text in ("-0.0", "0.0") else text


def _msp3(v: Sequence[float]) -> str:
    return "[" + ",".join(_msf(c) for c in v) + "]"


def _from_bits(text: str) -> float:
    return struct.unpack("<f", struct.pack("<I", int(text) & 0xFFFFFFFF))[0]


def _parse_vec(text: str) -> Vec:
    parts = text.split(",")
    return (_from_bits(parts[0]), _from_bits(parts[1]), _from_bits(parts[2]))


def _parse_typed(text: str) -> Any:
    kind, body = text[:1], text[1:]
    if kind == "f":
        return _from_bits(body)
    if kind == "i":
        return int(body)
    if kind == "b":
        return body.lower() == "true"
    return None


def _read_script(name: str) -> str:
    props = ", ".join(f"#{p}" for p in _READ_PROPS)
    return f"""(
fn mcpFB v = (bit.floatAsInt (v as float)) as string
fn mcpP3 v = (mcpFB v.x) + "," + (mcpFB v.y) + "," + (mcpFB v.z)
fn mcpVal v = (
  local k = classOf v
  if k == Float or k == Double then "f" + (mcpFB v)
  else if k == Integer then "i" + (v as string)
  else if k == BooleanClass then "b" + (v as string)
  else "s"
)
local c = getNodeByName "{safe_string(name)}" exact:true
if c == undefined then "ERR=not_found"
else if superClassOf c != camera then ("ERR=not_camera:" + ((classOf c) as string))
else at time currentTime (
  local tm = c.transform
  local s = "cls=" + ((classOf c) as string)
  s += "|r=" + (mcpP3 tm.row1) + "|u=" + (mcpP3 tm.row2) + "|b=" + (mcpP3 tm.row3) + "|p=" + (mcpP3 tm.row4)
  s += "|fov=" + (mcpFB c.fov)
  s += "|W=" + (renderWidth as string) + "|H=" + (renderHeight as string) + "|pa=" + (mcpFB renderPixelAspect)
  s += "|frame=" + (mcpFB currentTime.frame)
  s += "|units=" + (units.SystemType as string)
  s += "|hastarget=" + ((c.target != undefined) as string)
  s += "|animated=" + ((try (c.pos.isAnimated or c.rotation.isAnimated) catch false) as string)
  for pn in #({props}) where isProperty c pn do s += "|" + (pn as string) + "=" + (mcpVal (getProperty c pn))
  s
)
)"""


def _send(script: str, timeout: float | None = None) -> str:
    response = client.send_command(script, timeout=timeout) if timeout else client.send_command(script)
    result = response.get("result", "")
    return result if isinstance(result, str) else json.dumps(result)


def _parse_state(raw: str, name: str) -> dict[str, Any]:
    raw = raw.strip().strip('"')
    if raw.startswith("ERR="):
        reason = raw[4:]
        if reason == "not_found":
            raise ValueError(f"camera {name!r} not found")
        raise ValueError(f"{name!r} is not a camera ({reason})")
    fields: dict[str, str] = {}
    for chunk in raw.split("|"):
        key, sep, value = chunk.partition("=")
        if sep:
            fields[key] = value
    if "cls" not in fields or "r" not in fields:
        raise RuntimeError(f"unexpected camera readback: {raw[:200]}")
    props = {p: _parse_typed(fields[p]) for p in _READ_PROPS if p in fields}
    return {
        "class": fields["cls"],
        "right": _parse_vec(fields["r"]),
        "up": _parse_vec(fields["u"]),
        "back": _parse_vec(fields["b"]),
        "position": _parse_vec(fields["p"]),
        "fov": _from_bits(fields["fov"]),
        "render_width": int(fields["W"]),
        "render_height": int(fields["H"]),
        "pixel_aspect": _from_bits(fields["pa"]),
        "frame": _from_bits(fields["frame"]),
        "units": fields.get("units", ""),
        "has_target": fields.get("hastarget", "false").lower() == "true",
        "animated": fields.get("animated", "false").lower() == "true",
        "props": props,
    }


def _read_camera_state(name: str) -> dict[str, Any]:
    if not name or not str(name).strip():
        raise ValueError("camera name is required")
    return _parse_state(_send(_read_script(name)), name)


def _round(v: float, digits: int = 9) -> float:
    r = round(float(v), digits)
    return 0.0 if r == 0 else r


def camera_dict_from_state(name: str, state: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Build the export schema from a raw readback; returns (camera, warnings)."""
    warnings: list[str] = []
    props = state["props"]
    axes = [state["right"], state["up"], state["back"]]
    scales = [_norm(a) for a in axes]
    if any(abs(s - 1.0) > 1e-4 for s in scales):
        warnings.append(f"camera node is scaled (axis lengths {[round(s, 6) for s in scales]}); exported axes are normalised")
    right, up, back = (tuple(c / s for c in a) for a, s in zip(axes, scales))
    w, h = state["render_width"], state["render_height"]
    pa = state["pixel_aspect"]
    fov = state["fov"]
    shift_x = (props.get("horizontal_shift") or 0.0) / 100.0
    shift_y = (props.get("vertical_shift") or 0.0) / 100.0
    if props.get("orthoProjection"):
        warnings.append("camera uses orthographic projection; project_points models a perspective camera only")
    for key in ("horizontal_tilt_correction", "vertical_tilt_correction", "distortion_cubic_amount"):
        if abs(props.get(key) or 0.0) > 1e-9:
            warnings.append(f"{key} = {props[key]:g} is not modelled by project_points (pinhole model)")
    if props.get("auto_vertical_tilt_correction"):
        warnings.append("auto_vertical_tilt_correction is on and is not modelled by project_points")
    if (props.get("distortion_type") or 0) != 0:
        warnings.append(f"distortion_type = {props['distortion_type']} is not modelled by project_points")
    if state["animated"]:
        warnings.append(f"camera transform is animated; values are for frame {state['frame']:g}")
    near = far = None
    if props.get("clip_on"):
        near, far = props.get("clip_near"), props.get("clip_far")
    elif props.get("clipManually"):
        near, far = props.get("nearclip"), props.get("farclip")
    cam: dict[str, Any] = {
        "schema": SCHEMA,
        "name": name,
        "class": state["class"],
        "position": [_round(c) for c in state["position"]],
        "right": [_round(c) for c in right],
        "up": [_round(c) for c in up],
        "back": [_round(c) for c in back],
        "fov_deg": _round(fov),
        "f_px": _round(f_px_from_fov(fov, w)),
        "render_width": w,
        "render_height": h,
        "pixel_aspect": _round(pa),
        "shift_x": _round(shift_x),
        "shift_y": _round(shift_y),
        "near": _round(near) if near is not None else None,
        "far": _round(far) if far is not None else None,
        "units": state["units"],
        "frame": _round(state["frame"]),
    }
    cam["principal_point"] = [_round(c) for c in principal_point(cam)]
    if "film_width_mm" in props:
        cam["film_width_mm"] = _round(props["film_width_mm"])
        cam["focal_length_mm"] = _round(props.get("focal_length_mm") or 0.0)
        cam["lens_breathing_amount"] = _round(props.get("lens_breathing_amount") or 0.0)
    return cam, warnings


def _scene_dir() -> str | None:
    raw = _send("maxFilePath").strip().strip('"')
    return raw or None


# ── set_camera core ──────────────────────────────────────────────────

def _resolve_fov(
    *, fov_deg: float | None, f_px: float | None, focal_mm: float | None,
    film_width_mm: float | None, render_width: float,
) -> float | None:
    given = [k for k, v in (("fov_deg", fov_deg), ("f_px", f_px), ("focal_mm", focal_mm)) if v is not None]
    if len(given) > 1:
        raise ValueError(f"give only one of fov_deg, f_px, focal_mm (got {given})")
    if fov_deg is not None:
        if not 0.0 < float(fov_deg) < 180.0:
            raise ValueError("fov_deg must be between 0 and 180")
        return float(fov_deg)
    if f_px is not None:
        return fov_from_f_px(float(f_px), float(render_width))
    if focal_mm is not None:
        if film_width_mm is None:
            raise ValueError("focal_mm needs film_width_mm")
        return fov_from_focal_mm(float(focal_mm), float(film_width_mm))
    return None


def _resolve_shift(
    *, shift_x: float | None, shift_y: float | None,
    shift_x_px: float | None, shift_y_px: float | None,
    render_width: float, pixel_aspect: float,
) -> tuple[float | None, float | None]:
    if shift_x is not None and shift_x_px is not None:
        raise ValueError("give shift_x or shift_x_px, not both")
    if shift_y is not None and shift_y_px is not None:
        raise ValueError("give shift_y or shift_y_px, not both")
    sx = float(shift_x) if shift_x is not None else (
        float(shift_x_px) / render_width if shift_x_px is not None else None)
    sy = float(shift_y) if shift_y is not None else (
        -float(shift_y_px) / (render_width * pixel_aspect) if shift_y_px is not None else None)
    return sx, sy


def _build_set_script(
    *, name: str, create_class: str, exists: bool, state: dict[str, Any] | None,
    position: Vec | None, basis: tuple[Vec, Vec, Vec] | None,
    fov: float | None, film_width_mm: float | None,
    shift: tuple[float | None, float | None], near: float | None, far: float | None,
    render_size: tuple[int, int] | None, untarget: bool,
    clip: bool | None = None, pixel_aspect: float | None = None,
) -> tuple[str, list[str]]:
    notes: list[str] = []
    cls = state["class"] if state else create_class
    physical = cls == "Physical"
    lines = [f'local c = getNodeByName "{safe_string(name)}" exact:true']
    if not exists:
        ctor = {"Physical": "Physical", "Freecamera": "Freecamera", "Targetcamera": "Freecamera"}[create_class]
        extra = " targeted:false" if ctor == "Physical" else ""
        lines.append(f'if c == undefined do c = {ctor} name:"{safe_string(name)}"{extra}')
        if create_class == "Targetcamera":
            notes.append("created a Freecamera: a Targetcamera cannot hold an arbitrary roll")
    lines.append('if c == undefined or superClassOf c != camera do throw "MCP camera: target is not a camera"')
    has_target = bool(state and state["has_target"])
    if has_target and untarget:
        if not physical:
            raise ValueError(f"untarget is only supported for Physical cameras, not {cls}")
        lines.append("c.targeted = false")
        has_target = False
        notes.append("converted the targeted Physical camera to a free camera")
    if fov is not None:
        if physical:
            film = film_width_mm if film_width_mm is not None else (
                (state or {}).get("props", {}).get("film_width_mm") or 36.0)
            focal = focal_mm_from_fov(fov, film)
            lines += [
                "c.specify_fov = false",
                "c.lens_breathing_amount = 0.0",
                "c.zoom_factor = 1.0",
                "c.horizontal_tilt_correction = 0.0",
                "c.vertical_tilt_correction = 0.0",
                "c.auto_vertical_tilt_correction = false",
                "c.distortion_type = 0",
                f"c.film_width_mm = {_msf(film)}",
                f"c.focal_length_mm = {_msf(focal)}",
            ]
        else:
            if film_width_mm is not None:
                notes.append(f"film_width_mm ignored: {cls} has no film back")
            lines.append(f"c.fov = {_msf(fov)}")
    sx, sy = shift
    if sx is not None or sy is not None:
        if not physical:
            if abs(sx or 0.0) > 0 or abs(sy or 0.0) > 0:
                raise ValueError(f"{cls} has no lens shift; create a Physical camera for shifted frames")
        else:
            if sx is not None:
                lines.append(f"c.horizontal_shift = {_msf(sx * 100.0)}")
            if sy is not None:
                lines.append(f"c.vertical_shift = {_msf(sy * 100.0)}")
    if clip is False:
        if near is not None or far is not None:
            raise ValueError("clip=False turns clipping off; do not pass near/far with it")
        lines.append("c.clip_on = false" if physical else "c.clipManually = false")
    elif near is not None or far is not None:
        if physical:
            lines.append("c.clip_on = true")
            if near is not None:
                lines.append(f"c.clip_near = {_msf(near)}")
            if far is not None:
                lines.append(f"c.clip_far = {_msf(far)}")
        else:
            lines.append("c.clipManually = true")
            if near is not None:
                lines.append(f"c.nearclip = {_msf(near)}")
            if far is not None:
                lines.append(f"c.farclip = {_msf(far)}")
    if position is not None and basis is not None:
        r, u, b = basis
        if has_target:
            lines += [
                "local d = distance c.pos c.target.pos",
                "if d < 1e-3 do d = 100.0",
                f"c.pos = {_msp3(position)}",
                f"c.target.pos = {_msp3(position)} - {_msp3(b)} * d",
            ]
            notes.append("targeted camera: orientation set through its target; roll follows the look-at controller")
        else:
            lines.append(f"c.transform = matrix3 {_msp3(r)} {_msp3(u)} {_msp3(b)} {_msp3(position)}")
    if render_size is not None or pixel_aspect is not None:
        # An open Render Setup writes its stale values back and the image-aspect lock
        # rewrites the other side: close / release both, restore them even on a throw.
        sets = []
        if render_size is not None:
            sets += [f"renderWidth = {int(render_size[0])}", f"renderHeight = {int(render_size[1])}"]
        if pixel_aspect is not None:
            sets.append(f"renderPixelAspect = {_msf(pixel_aspect)}")
        lines += [
            "local mcpDlg = renderSceneDialog.isOpen()",
            "local mcpLock = rendLockImageAspectRatio",
            "local mcpErr = undefined",
            "if mcpDlg do renderSceneDialog.close()",
            "rendLockImageAspectRatio = false",
            f"try ({'; '.join(sets)}) catch (mcpErr = getCurrentException())",
            "rendLockImageAspectRatio = mcpLock",
            "if mcpDlg and not (renderSceneDialog.isOpen()) do renderSceneDialog.open()",
            "if mcpErr != undefined do throw mcpErr",
        ]
    body = "\n".join(lines)
    script = f'(\nundo "MCP set camera" on (\nwith animate off (\n{body}\n)\n)\n"OK"\n)'
    return script, notes


def _check(label: str, got: float, want: float, tol: float, mismatches: list[str]) -> None:
    if not abs(got - want) <= tol:
        mismatches.append(f"{label}: wrote {want!r}, read back {got!r}")


def _verify_readback(
    state: dict[str, Any], *, position: Vec | None, basis: tuple[Vec, Vec, Vec] | None,
    fov: float | None, shift: tuple[float | None, float | None],
    near: float | None, far: float | None,
    clip: bool | None = None, render_size: tuple[int, int] | None = None,
    pixel_aspect: float | None = None,
) -> None:
    mismatches: list[str] = []
    props = state["props"]
    if render_size is not None:
        got_size = (state["render_width"], state["render_height"])
        if got_size != tuple(render_size):
            mismatches.append(f"render size: wrote {list(render_size)}, read back {list(got_size)}")
    if pixel_aspect is not None:
        _check("pixel_aspect", state["pixel_aspect"], pixel_aspect, 1e-6 * max(1.0, abs(pixel_aspect)), mismatches)
    if clip is False:
        flag = "clip_on" if "clip_on" in props else "clipManually"
        if props.get(flag) is not False:
            mismatches.append(f"{flag}: wrote False, read back {props.get(flag)!r}")
    if position is not None:
        tol = POS_TOLERANCE * max(1.0, max(abs(c) for c in position))
        for i, axis in enumerate("xyz"):
            _check(f"position.{axis}", state["position"][i], position[i], tol, mismatches)
    if basis is not None:
        for label, want, got in zip(("right", "up", "back"), basis, (state["right"], state["up"], state["back"])):
            for i, axis in enumerate("xyz"):
                _check(f"{label}.{axis}", got[i], want[i], AXIS_TOLERANCE, mismatches)
    if fov is not None:
        _check("fov_deg", state["fov"], fov, FOV_TOLERANCE_DEG, mismatches)
    sx, sy = shift
    if sx is not None and "horizontal_shift" in props:
        _check("shift_x", props["horizontal_shift"] / 100.0, sx, SHIFT_TOLERANCE, mismatches)
    if sy is not None and "vertical_shift" in props:
        _check("shift_y", props["vertical_shift"] / 100.0, sy, SHIFT_TOLERANCE, mismatches)
    near_key, far_key = ("clip_near", "clip_far") if "clip_near" in props else ("nearclip", "farclip")
    if near is not None:
        _check("near", props.get(near_key, float("nan")), near, 1e-5 * max(1.0, abs(near)), mismatches)
    if far is not None:
        _check("far", props.get(far_key, float("nan")), far, 1e-5 * max(1.0, abs(far)), mismatches)
    if mismatches:
        raise CameraReadbackError("camera readback mismatch: " + "; ".join(mismatches))


def apply_camera(
    *,
    name: str,
    position: Sequence[float] | None = None,
    right: Sequence[float] | None = None,
    up: Sequence[float] | None = None,
    back: Sequence[float] | None = None,
    target: Sequence[float] | None = None,
    up_hint: Sequence[float] | None = None,
    fov_deg: float | None = None,
    f_px: float | None = None,
    focal_mm: float | None = None,
    film_width_mm: float | None = None,
    render_width: int | None = None,
    render_height: int | None = None,
    set_render_size: bool = False,
    shift_x: float | None = None,
    shift_y: float | None = None,
    shift_x_px: float | None = None,
    shift_y_px: float | None = None,
    near: float | None = None,
    far: float | None = None,
    camera_class: str = "Physical",
    create: bool = True,
    untarget: bool = False,
    clip: bool | None = None,
    pixel_aspect: float | None = None,
) -> dict[str, Any]:
    """Shared core of set_camera / import_camera.

    clip=False turns the camera's clipping off (None leaves it unless near/far are
    given). pixel_aspect is written as renderPixelAspect together with
    set_render_size; without it, a value that differs from the scene's is
    reported as a warning.
    """
    if not name or not name.strip():
        raise ValueError("name is required")
    if camera_class not in _SUPPORTED_CLASSES:
        raise ValueError(f"camera_class must be one of {list(_SUPPORTED_CLASSES)}")
    warnings: list[str] = []
    try:
        state: dict[str, Any] | None = _read_camera_state(name)
    except ValueError as exc:
        if "not found" not in str(exc):
            raise
        state = None
    if state is None and not create:
        raise ValueError(f"camera {name!r} not found and create=False")
    if state is not None and state["class"] not in _SUPPORTED_CLASSES:
        raise ValueError(f"camera class {state['class']} is not supported (supported: {list(_SUPPORTED_CLASSES)})")
    scene_w = int((state or {}).get("render_width") or 0) or int(_send("renderWidth as string").strip('"'))
    scene_h = int((state or {}).get("render_height") or 0) or int(_send("renderHeight as string").strip('"'))
    if state is not None:
        scene_pa = float(state.get("pixel_aspect") or 1.0)
    elif shift_y_px is not None or pixel_aspect is not None:
        # New camera: renderPixelAspect is a scene setting, never assume square pixels.
        scene_pa = _from_bits(_send("(bit.floatAsInt (renderPixelAspect as float)) as string").strip('"'))
    else:
        scene_pa = 1.0
    if pixel_aspect is not None:
        pixel_aspect = float(pixel_aspect)
        if not math.isfinite(pixel_aspect) or pixel_aspect <= 0:
            raise ValueError("pixel_aspect must be a positive number")
    write_pa = pixel_aspect if (set_render_size and pixel_aspect is not None) else None
    pa = write_pa if write_pa is not None else scene_pa
    if pixel_aspect is not None and write_pa is None and abs(pixel_aspect - scene_pa) > 1e-6 * pixel_aspect:
        warnings.append(
            f"camera pixel_aspect {pixel_aspect:g} differs from the scene's renderPixelAspect {scene_pa:g}: "
            "vertical framing will differ; pass set_render_size=True to apply it")
    if (render_width is None) != (render_height is None) and set_render_size:
        raise ValueError("set_render_size needs both render_width and render_height")
    lens_w = float(render_width) if render_width else float(scene_w)

    pos_v: Vec | None = _vec(position, "position") if position is not None else None
    basis: tuple[Vec, Vec, Vec] | None = None
    if target is not None:
        if any(v is not None for v in (right, up, back)):
            raise ValueError("give either target (look-at) or right/up/back, not both")
        if pos_v is None:
            raise ValueError("look-at needs position")
        r, u, b, notes = look_at_basis(pos_v, target, up_hint)
        basis = (r, u, b)
        warnings += notes
    elif any(v is not None for v in (right, up, back)):
        if not all(v is not None for v in (right, up, back)):
            raise ValueError("right, up and back must be given together")
        r, u, b, deviation, corrected = orthonormalize_basis(right, up, back)  # type: ignore[arg-type]
        basis = (r, u, b)
        if corrected:
            warnings.append(f"basis re-orthonormalised (input deviation {deviation:.3g})")
    if basis is not None and pos_v is None:
        if state is None:
            raise ValueError("a new camera needs position")
        pos_v = state["position"]
    if pos_v is not None and basis is None:
        if state is None:
            raise ValueError("a new camera needs an orientation: right/up/back or target")
        basis = (_unit(state["right"], "right"), _unit(state["up"], "up"), _unit(state["back"], "back"))

    fov = _resolve_fov(fov_deg=fov_deg, f_px=f_px, focal_mm=focal_mm,
                       film_width_mm=film_width_mm, render_width=lens_w)
    shift = _resolve_shift(shift_x=shift_x, shift_y=shift_y, shift_x_px=shift_x_px,
                           shift_y_px=shift_y_px, render_width=lens_w, pixel_aspect=pa)
    for label, value in (("near", near), ("far", far)):
        if value is not None and (not math.isfinite(float(value)) or float(value) < 0):
            raise ValueError(f"{label} must be a non-negative number")
    if near is not None and far is not None and float(far) <= float(near):
        raise ValueError("far must be greater than near")
    render_size = None
    if set_render_size:
        if not render_width or not render_height or render_width <= 0 or render_height <= 0:
            raise ValueError("set_render_size needs positive render_width and render_height")
        render_size = (int(render_width), int(render_height))
    elif render_width and int(render_width) != scene_w:
        warnings.append(
            f"render_width {render_width} differs from the scene's {scene_w}; the FOV and shift fractions "
            "are resolution independent, pixel values follow the scene render size")

    script, notes = _build_set_script(
        name=name, create_class=camera_class, exists=state is not None, state=state,
        position=pos_v, basis=basis, fov=fov, film_width_mm=film_width_mm, shift=shift,
        near=float(near) if near is not None else None, far=float(far) if far is not None else None,
        render_size=render_size, untarget=untarget, clip=clip, pixel_aspect=write_pa,
    )
    warnings += notes
    _send(script)
    after = _read_camera_state(name)
    near_f = float(near) if near is not None else None
    far_f = float(far) if far is not None else None
    checks = {"clip": clip, "render_size": render_size, "pixel_aspect": write_pa}
    if after["has_target"] and basis is not None:
        # A look-at controller owns the rotation: check position and view direction, report roll.
        _verify_readback(after, position=pos_v, basis=None, fov=fov, shift=shift, near=near_f, far=far_f,
                         **checks)
        if max(abs(a - b) for a, b in zip(basis[2], after["back"])) > 1e-4:
            raise CameraReadbackError(
                f"targeted camera view direction mismatch: wrote {list(basis[2])}, read {list(after['back'])}")
        if max(abs(a - b) for a, b in zip(basis[0], after["right"])) > 1e-4:
            raise CameraReadbackError(
                f"targeted camera: its look-at controller set right={list(after['right'])} instead of "
                f"{list(basis[0])} (roll); pass untarget=True (Physical) or use a Freecamera. "
                "Position and view direction were applied (undo restores them).")
    else:
        _verify_readback(after, position=pos_v, basis=basis, fov=fov, shift=shift, near=near_f, far=far_f,
                         **checks)
    cam, readback_warnings = camera_dict_from_state(name, after)
    return {"created": state is None, "camera": cam, "warnings": warnings + readback_warnings}


def _load_camera_json(data: dict[str, Any] | str | None, path: str) -> dict[str, Any]:
    if data is not None and path:
        raise ValueError("give data or path, not both")
    if path:
        with open(path, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    elif isinstance(data, str):
        loaded = json.loads(data)
    elif isinstance(data, dict):
        loaded = data
    else:
        raise ValueError("data (camera JSON) or path is required")
    if not isinstance(loaded, dict):
        raise ValueError("camera JSON must be an object")
    if isinstance(loaded.get("camera"), dict) and "position" not in loaded:
        loaded = loaded["camera"]
    missing = [k for k in ("position", "right", "up", "back") if k not in loaded]
    if missing:
        raise ValueError(f"camera JSON is missing {missing}")
    if loaded.get("fov_deg") is None and loaded.get("f_px") is None:
        raise ValueError("camera JSON needs fov_deg or f_px")
    return loaded


def _write_json(path: str, payload: dict[str, Any]) -> str:
    target = path_policy.resolve_write_path(path, scene_dir=_scene_dir())
    os.makedirs(target.parent, exist_ok=True)
    tmp = target.with_name(target.name + f".{uuid.uuid4().hex[:8]}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, target)
    return str(target)


# ── MCP tools ────────────────────────────────────────────────────────

@mcp.tool()
def set_camera(
    name: str,
    position: list[float] | None = None,
    right: list[float] | None = None,
    up: list[float] | None = None,
    back: list[float] | None = None,
    target: list[float] | None = None,
    up_hint: list[float] | None = None,
    fov_deg: float | None = None,
    f_px: float | None = None,
    focal_mm: float | None = None,
    film_width_mm: float | None = None,
    render_width: int | None = None,
    render_height: int | None = None,
    set_render_size: bool = False,
    shift_x: float | None = None,
    shift_y: float | None = None,
    shift_x_px: float | None = None,
    shift_y_px: float | None = None,
    near: float | None = None,
    far: float | None = None,
    camera_class: str = "Physical",
    create: bool = True,
    untarget: bool = False,
) -> dict[str, Any]:
    """Create or update a camera from solved/match-move data, then read every value back.

    Orientation: world `position` plus an orthonormal right/up/back basis (the
    camera looks down -back; small errors are re-orthonormalised, degenerate or
    left-handed bases are rejected) OR `target` (look-at, optional `up_hint`,
    default world Z). Lens: one of `fov_deg` (horizontal), `f_px` (pixels at
    `render_width`, default the scene render width) or `focal_mm` +
    `film_width_mm`. Shift: `shift_x`/`shift_y` as fractions of render width
    (Physical horizontal/vertical_shift / 100, +y up) or `shift_x_px`/`shift_y_px`
    as the principal point offset from frame centre in pixels (+y down).
    New cameras are `Physical` (supports shift) unless `camera_class` says
    Freecamera. Setting a lens resets Physical lens breathing, zoom, tilt
    correction and distortion so the camera is a pure pinhole. Raises when any
    read-back value differs from what was written. Returns the export_camera JSON.
    """
    params = dict(locals())  # must stay the first statement: forwards exactly the tool arguments
    return apply_camera(**params)


@mcp.tool()
def export_camera(name: str, path: str = "") -> dict[str, Any]:
    """Export a scene camera as JSON (schema 3dsmax-mcp/camera@1).

    Fields: name, class, position, right, up, back (world, scene units), fov_deg
    (horizontal), f_px, render_width, render_height, pixel_aspect, shift_x/shift_y
    (fractions of render width), principal_point [cx, cy] px, near/far (null when
    clipping is off), plus film/focal mm for Physical cameras. With `path` the JSON
    is also written there (allowed folders only: [safe_mode] allowed_dirs, the scene
    folder, or %TEMP%/3dsmax-mcp).
    """
    cam, warnings = camera_dict_from_state(name, _read_camera_state(name))
    result: dict[str, Any] = {"camera": cam, "warnings": warnings}
    if path:
        result["file"] = _write_json(path, cam)
    return result


@mcp.tool()
def import_camera(
    data: dict[str, Any] | str | None = None,
    path: str = "",
    name: str = "",
    set_render_size: bool = False,
    untarget: bool = False,
) -> dict[str, Any]:
    """Create or update a camera from export_camera JSON (`data` object/string or a file `path`).

    `name` overrides the JSON name. The FOV is taken from fov_deg (else f_px with
    the JSON render_width); shift_x/shift_y are fractions of render width, so the
    camera frames the same image at any resolution. `set_render_size` also applies
    the JSON render_width/render_height/pixel_aspect to the scene (otherwise a
    different pixel_aspect is reported as a warning). near/far null (clipping off
    at export) turns clipping off. Every value is read back.
    """
    cam = _load_camera_json(data, path)
    target_name = name or cam.get("name") or ""
    cls = cam.get("class") or "Physical"
    if cls not in _SUPPORTED_CLASSES:
        raise ValueError(f"camera class {cls} is not supported (supported: {list(_SUPPORTED_CLASSES)})")
    rw, rh = cam.get("render_width"), cam.get("render_height")
    fov = cam.get("fov_deg")
    if fov is None:
        if not rw:
            raise ValueError("f_px needs render_width in the camera JSON")
        fov = fov_from_f_px(float(cam["f_px"]), float(rw))
    # export_camera writes near/far as null when clipping is off: that is an explicit
    # "clipping off", not "leave the target camera's clipping as it is".
    clip_off = "near" in cam and "far" in cam and cam["near"] is None and cam["far"] is None
    pa = cam.get("pixel_aspect")
    return apply_camera(
        name=target_name,
        position=cam["position"], right=cam["right"], up=cam["up"], back=cam["back"],
        fov_deg=float(fov),
        film_width_mm=cam.get("film_width_mm") if cls == "Physical" else None,
        render_width=int(rw) if rw else None, render_height=int(rh) if rh else None,
        set_render_size=set_render_size,
        shift_x=cam.get("shift_x") if cls == "Physical" else None,
        shift_y=cam.get("shift_y") if cls == "Physical" else None,
        near=cam.get("near"), far=cam.get("far"),
        camera_class=cls if cls != "Targetcamera" else "Freecamera",
        untarget=untarget,
        clip=False if clip_off else None,
        pixel_aspect=float(pa) if pa is not None else None,
    )


@mcp.tool()
def project_points(camera: str | dict[str, Any], points: list[list[float]]) -> dict[str, Any]:
    """Project world points to render-resolution pixels through a camera.

    `camera` is a scene camera name (read live from Max) or an export_camera JSON
    object. Pixel coordinates: origin top-left of the render frame, x right, y
    down, continuous (first pixel centre = 0.5, 0.5). Each point returns x, y
    (null when behind), depth along the view axis, `behind` (depth <= 0),
    `in_frame` (inside 0..W, 0..H) and `clipped` when the camera clips.
    Matches Max's own renders to well under 0.5 px (verified with marker renders).
    """
    warnings: list[str] = []
    if isinstance(camera, dict):
        cam = camera
    elif isinstance(camera, str) and camera.strip().startswith("{"):
        cam = json.loads(camera)
    else:
        cam, warnings = camera_dict_from_state(str(camera), _read_camera_state(str(camera)))
    if not points:
        raise ValueError("points must contain at least one [x, y, z]")
    projected = project_camera_points(cam, points)
    cx, cy = principal_point(cam)
    return {
        "camera": cam.get("name"),
        "render_width": cam["render_width"],
        "render_height": cam["render_height"],
        "f_px": f_px_from_fov(float(cam["fov_deg"]), float(cam["render_width"])),
        "principal_point": [cx, cy],
        "points": projected,
        "warnings": warnings,
    }


# ── capture_camera ───────────────────────────────────────────────────

_COMPOSITOR_CLASS = "McpCameraCompositorV1"
_COMPOSITOR_CS = r"""
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Drawing.Drawing2D;
using System.Runtime.InteropServices;
public class McpCameraCompositorV1 {
  static Bitmap Load(string path) {
    using (Bitmap src = new Bitmap(path)) {
      Bitmap bmp = new Bitmap(src.Width, src.Height, PixelFormat.Format32bppArgb);
      using (Graphics g = Graphics.FromImage(bmp)) {
        g.CompositingMode = CompositingMode.SourceCopy;
        g.InterpolationMode = InterpolationMode.NearestNeighbor;
        g.PixelOffsetMode = PixelOffsetMode.Half;
        g.DrawImage(src, new Rectangle(0, 0, src.Width, src.Height), 0, 0, src.Width, src.Height, GraphicsUnit.Pixel);
      }
      return bmp;
    }
  }
  static int[] Read(Bitmap b) {
    BitmapData d = b.LockBits(new Rectangle(0, 0, b.Width, b.Height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
    int[] px = new int[b.Width * b.Height];
    Marshal.Copy(d.Scan0, px, 0, px.Length);
    b.UnlockBits(d);
    return px;
  }
  static void Write(Bitmap b, int[] px) {
    BitmapData d = b.LockBits(new Rectangle(0, 0, b.Width, b.Height), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
    Marshal.Copy(px, 0, d.Scan0, px.Length);
    b.UnlockBits(d);
  }
  public string Run(string framePath, string cleanPath, string platePath,
                    double cx, double cy, double cw, double ch,
                    int outW, int outH, double opacity, string outPath, string mattePath) {
    using (Bitmap a = Load(framePath)) {
      if (cleanPath.Length > 0) {
        using (Bitmap b = Load(cleanPath)) {
          if (a.Width != b.Width || a.Height != b.Height) throw new Exception("capture sizes differ");
          int[] pa = Read(a);
          int[] pb = Read(b);
          for (int i = 0; i < pa.Length; i++) {
            if (pa[i] == pb[i]) pa[i] = 0;
            else pa[i] = pa[i] | unchecked((int)0xFF000000);
          }
          Write(a, pa);
        }
      }
      using (Bitmap matte = new Bitmap(outW, outH, PixelFormat.Format32bppArgb)) {
        using (Graphics g = Graphics.FromImage(matte)) {
          g.Clear(Color.Transparent);
          g.CompositingMode = CompositingMode.SourceCopy;
          g.InterpolationMode = InterpolationMode.HighQualityBicubic;
          g.PixelOffsetMode = PixelOffsetMode.HighQuality;
          using (ImageAttributes ia = new ImageAttributes()) {
            ia.SetWrapMode(WrapMode.TileFlipXY);
            g.DrawImage(a, new Rectangle(0, 0, outW, outH), (float)cx, (float)cy, (float)cw, (float)ch, GraphicsUnit.Pixel, ia);
          }
        }
        if (mattePath.Length > 0) matte.Save(mattePath, ImageFormat.Png);
        using (Bitmap outB = new Bitmap(outW, outH, PixelFormat.Format32bppArgb)) {
          using (Graphics g = Graphics.FromImage(outB)) {
            g.Clear(Color.Black);
            g.InterpolationMode = InterpolationMode.HighQualityBicubic;
            g.PixelOffsetMode = PixelOffsetMode.HighQuality;
            if (platePath.Length > 0) {
              using (Bitmap plate = Load(platePath)) {
                using (ImageAttributes ip = new ImageAttributes()) {
                  ip.SetWrapMode(WrapMode.TileFlipXY);
                  g.DrawImage(plate, new Rectangle(0, 0, outW, outH), 0, 0, plate.Width, plate.Height, GraphicsUnit.Pixel, ip);
                }
              }
            }
            ColorMatrix cm = new ColorMatrix();
            cm.Matrix33 = (float)opacity;
            using (ImageAttributes io = new ImageAttributes()) {
              io.SetColorMatrix(cm);
              g.CompositingMode = CompositingMode.SourceOver;
              g.InterpolationMode = InterpolationMode.NearestNeighbor;
              g.PixelOffsetMode = PixelOffsetMode.Half;
              g.DrawImage(matte, new Rectangle(0, 0, outW, outH), 0, 0, outW, outH, GraphicsUnit.Pixel, io);
            }
          }
          outB.Save(outPath, ImageFormat.Png);
        }
      }
    }
    return "OK";
  }
}
"""

_NATIVE_PLATE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff"}


def _ms_path(path: str | os.PathLike[str]) -> str:
    return safe_string(str(path).replace("\\", "/"))


def frame_rect_in_viewport(vw: float, vh: float, render_w: float, render_h: float, pixel_aspect: float = 1.0) -> tuple[float, float, float, float]:
    """Safe-frame (live area) rectangle of a camera viewport: x, y, w, h in viewport pixels.

    Max fits the render aspect inside the viewport, centred, touching either
    the top/bottom or the left/right edges.
    """
    aspect = render_w * pixel_aspect / render_h
    if vw / vh > aspect:
        h = float(vh)
        w = h * aspect
        return ((vw - w) / 2.0, 0.0, w, h)
    w = float(vw)
    h = w / aspect
    return (0.0, (vh - h) / 2.0, w, h)


def resolve_capture_size(size: Any, render_w: int, render_h: int) -> tuple[int, int]:
    if size is None or size == [] or size == 0:
        return int(render_w), int(render_h)
    if isinstance(size, str):
        text = size.strip().lower().replace("x", ",")
        size = [int(float(s)) for s in text.split(",") if s.strip()]
    if isinstance(size, (int, float)):
        size = [int(size)]
    vals = [int(v) for v in size]
    if len(vals) == 1:
        w = vals[0]
        h = int(round(w * render_h / render_w))
    elif len(vals) == 2:
        w, h = vals
        expected = w * render_h / render_w
        if abs(h - expected) > 1.0:
            raise ValueError(
                f"size {w}x{h} does not keep the render aspect {render_w}x{render_h}; "
                f"use {w}x{int(round(expected))} or pass only the width")
    else:
        raise ValueError("size must be a width or [width, height]")
    if w < 8 or h < 8 or w > 16384 or h > 16384:
        raise ValueError("size must be between 8 and 16384 pixels per side")
    return w, h


def _state_save_restore_script(inner: str) -> str:
    """Wrap viewport-changing MAXScript so view state always comes back."""
    return f"""(
local vpType = viewport.getType()
local vpCam = viewport.getCamera()
local vpTM = viewport.getTM()
local vpFov = viewport.GetFOV()
local vpLevel = viewport.GetRenderLevel()
local vpSafe = displaySafeFrames
local vpSolid = viewport.IsSolidBackgroundColorMode()
local vpButtons = ViewportButtonMgr.EnableButtons
local hc = #(hideByCategory.geometry, hideByCategory.shapes, hideByCategory.lights, hideByCategory.cameras, hideByCategory.helpers, hideByCategory.spacewarps, hideByCategory.particles, hideByCategory.bones)
local sel = selection as array
local mcpResult = undefined
local mcpErr = undefined
try (
{inner}
) catch (mcpErr = getCurrentException())
hideByCategory.geometry = hc[1]; hideByCategory.shapes = hc[2]; hideByCategory.lights = hc[3]; hideByCategory.cameras = hc[4]
hideByCategory.helpers = hc[5]; hideByCategory.spacewarps = hc[6]; hideByCategory.particles = hc[7]; hideByCategory.bones = hc[8]
ViewportButtonMgr.EnableButtons = vpButtons
viewport.EnableSolidBackgroundColorMode vpSolid
displaySafeFrames = vpSafe
if vpCam != undefined and isValidNode vpCam then viewport.setCamera vpCam
else (
  viewport.setType vpType
  try (viewport.setTM vpTM) catch ()
  try (viewport.SetFOV vpFov) catch ()
)
viewport.SetRenderLevel vpLevel
if sel.count > 0 then (try (select sel) catch ()) else clearSelection()
completeRedraw()
if mcpErr != undefined do throw ("MCP capture_camera: " + mcpErr)
mcpResult
)"""


@mcp.tool()
def capture_camera(
    camera: str,
    plate_path: str = "",
    size: list[int] | int | str | None = None,
    mode: str = "shaded",
    opacity: float = 0.5,
    output_path: str = "",
) -> dict[str, Any]:
    """Capture exactly the camera's render frame and composite it over a plate.

    The image covers the render aspect / safe-frame live area only (never the
    whole viewport) at `size` (width, or [width, height] keeping the render
    aspect; default the render resolution). `mode="shaded"` uses Max's Make
    Preview at render resolution with a clean alpha matte (only geometry is laid
    over the plate); `mode="wire"` grabs the camera viewport in wireframe, keeps
    only the wires (overlays cancelled by a geometry-hidden second grab) and is
    limited to the viewport's on-screen frame size. The matte is drawn over the
    plate (`plate_path`, stretched to `size`; black when empty) at `opacity`.
    Saved under %TEMP%/3dsmax-mcp unless `output_path` (allowed folders only).
    Viewport type, camera, shading, safe frames and display filters are restored.
    """
    mode = (mode or "shaded").strip().lower()
    if mode not in ("shaded", "wire"):
        raise ValueError('mode must be "shaded" or "wire"')
    opacity = float(opacity)
    if not 0.0 <= opacity <= 1.0:
        raise ValueError("opacity must be between 0 and 1")
    state = _read_camera_state(camera)
    cam, warnings = camera_dict_from_state(camera, state)
    rw, rh, pa = cam["render_width"], cam["render_height"], cam["pixel_aspect"]
    out_w, out_h = resolve_capture_size(size, rw, rh)
    if plate_path:
        if not os.path.isfile(plate_path):
            raise ValueError(f"plate not found: {plate_path}")
    scene_dir = _scene_dir()
    tmp_root = path_policy.temp_root()
    os.makedirs(tmp_root, exist_ok=True)
    token = uuid.uuid4().hex[:10]
    if output_path:
        out_file = path_policy.resolve_write_path(output_path, scene_dir=scene_dir)
        if out_file.suffix.lower() != ".png":
            raise ValueError("output_path must end in .png")
    else:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in camera)[:60] or "camera"
        out_file = tmp_root / f"camera_capture_{safe}_{token}.png"
    os.makedirs(out_file.parent, exist_ok=True)
    matte_file = out_file.with_name(out_file.stem + "_matte.png")
    path_policy.resolve_write_path(matte_file, scene_dir=scene_dir)
    temp_files: list[str] = []
    plate_for_gdi = ""
    try:
        if plate_path:
            plate_for_gdi = os.path.abspath(plate_path)
            if os.path.splitext(plate_path)[1].lower() not in _NATIVE_PLATE_EXT:
                converted = tmp_root / f"_plate_{token}.png"
                _send(f"""(
local b = openBitmap "{_ms_path(os.path.abspath(plate_path))}"
if b == undefined do throw "cannot open plate"
local c2 = copy b
c2.filename = "{_ms_path(converted)}"
save c2
close c2
close b
"OK"
)""", timeout=120.0)
                temp_files.append(str(converted))
                plate_for_gdi = str(converted)
                warnings.append("plate converted to 8-bit PNG through Max (display gamma applied)")
        name_ms = safe_string(camera)
        if mode == "shaded":
            prefix = tmp_root / f"_preview_{token}_"
            inner = f"""
local c = getNodeByName "{name_ms}" exact:true
viewport.setCamera c
viewport.EnableSolidBackgroundColorMode true
local fr = (currentTime.frame as integer)
createPreview filename:"{_ms_path(prefix)}.png" outputAVI:false percentSize:100 start:fr end:fr skip:1 dspGeometry:true dspShapes:true dspLights:false dspCameras:false dspHelpers:false dspSpaceWarps:false dspParticles:true dspBones:false dspGrid:false dspSafeFrame:false dspFrameNums:false autoPlay:false
mcpResult = "OK"
"""
            _send(_state_save_restore_script(inner), timeout=600.0)
            produced = sorted(glob.glob(str(prefix) + "*.png"))
            temp_files += produced
            if not produced:
                raise RuntimeError("Make Preview produced no image")
            frame_path, clean_path = produced[0], ""
            crop = (0.0, 0.0, float(rw), float(rh))
            source = "make_preview"
            source_px = [rw, rh]
        else:
            frame_path = str(tmp_root / f"_wire_{token}_a.png")
            clean_path = str(tmp_root / f"_wire_{token}_b.png")
            temp_files += [frame_path, clean_path]
            inner = f"""
local c = getNodeByName "{name_ms}" exact:true
clearSelection()
viewport.setCamera c
displaySafeFrames = true
viewport.SetRenderLevel #wireFrame
ViewportButtonMgr.EnableButtons = false
hideByCategory.lights = true; hideByCategory.cameras = true; hideByCategory.helpers = true
hideByCategory.spacewarps = true; hideByCategory.bones = true
completeRedraw()
local da = gw.getViewportDib captureAlpha:true
-- the DIB is in physical pixels; gw.getWinSizeX/Y are DPI-scaled logical pixels
local dibSize = (da.width as string) + "," + (da.height as string)
da.filename = "{_ms_path(frame_path)}"
save da
close da
hideByCategory.geometry = true; hideByCategory.shapes = true; hideByCategory.particles = true
completeRedraw()
local db = gw.getViewportDib captureAlpha:true
db.filename = "{_ms_path(clean_path)}"
save db
close db
mcpResult = dibSize
"""
            raw = _send(_state_save_restore_script(inner), timeout=300.0).strip().strip('"')
            vw, vh = (int(v) for v in raw.split(","))
            crop = frame_rect_in_viewport(vw, vh, rw, rh, pa)
            source = "viewport_wire"
            source_px = [round(crop[2], 2), round(crop[3], 2)]
            if crop[2] < out_w * 0.999:
                warnings.append(
                    f"wire capture comes from a {crop[2]:.0f}x{crop[3]:.0f} px viewport frame and was upscaled "
                    f"to {out_w}x{out_h}; maximise the viewport for more detail")
        composite = f"""(
global {_COMPOSITOR_CLASS}_inst
if {_COMPOSITOR_CLASS}_inst == undefined do (
  local prov = dotNetObject "Microsoft.CSharp.CSharpCodeProvider"
  local cp = dotNetObject "System.CodeDom.Compiler.CompilerParameters"
  cp.ReferencedAssemblies.Add "System.dll"
  cp.ReferencedAssemblies.Add "System.Drawing.dll"
  cp.GenerateInMemory = true
  cp.GenerateExecutable = false
  local res = prov.CompileAssemblyFromSource cp #("{safe_string(_COMPOSITOR_CS)}")
  if res.Errors.HasErrors do throw ("compositor compile failed: " + (res.Errors.Item[0].ToString()))
  {_COMPOSITOR_CLASS}_inst = res.CompiledAssembly.CreateInstance "{_COMPOSITOR_CLASS}"
)
{_COMPOSITOR_CLASS}_inst.Run "{_ms_path(frame_path)}" "{_ms_path(clean_path) if clean_path else ''}" "{_ms_path(plate_for_gdi) if plate_for_gdi else ''}" {_msf(crop[0])} {_msf(crop[1])} {_msf(crop[2])} {_msf(crop[3])} {int(out_w)} {int(out_h)} {_msf(opacity)} "{_ms_path(out_file)}" "{_ms_path(matte_file)}"
)"""
        _send(composite, timeout=300.0)
    finally:
        for f in temp_files:
            try:
                os.remove(f)
            except OSError:
                pass
    if not out_file.is_file():
        raise RuntimeError(f"composite was not written: {out_file}")
    return {
        "type": "image_file",
        "file": str(out_file),
        "matte_file": str(matte_file),
        "mime_type": "image/png",
        "width": out_w,
        "height": out_h,
        "camera": camera,
        "mode": mode,
        "opacity": opacity,
        "plate": os.path.abspath(plate_path) if plate_path else None,
        "render_size": [rw, rh],
        "source": source,
        "source_frame_px": source_px,
        "scale": out_w / float(rw),
        "warnings": warnings,
    }
