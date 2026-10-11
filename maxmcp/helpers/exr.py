"""Minimal OpenEXR reader: header (windows, channels, compression) and pixels
of single-part scanline files with NONE / RLE / ZIPS / ZIP compression.

Pure standard library so the MCP server can read back what a render wrote
(dataWindow vs displayWindow, float vs half channels) and acceptance scripts
can check pixel values without OpenImageIO/OpenEXR wheels.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

MAGIC = 20000630
PIXEL_TYPES = {0: "uint", 1: "half", 2: "float"}
PIXEL_SIZES = {0: 4, 1: 2, 2: 4}
COMPRESSIONS = {
    0: "none", 1: "rle", 2: "zips", 3: "zip", 4: "piz", 5: "pxr24",
    6: "b44", 7: "b44a", 8: "dwaa", 9: "dwab", 10: "htj2k",
}
LINES_PER_CHUNK = {0: 1, 1: 1, 2: 1, 3: 16, 4: 32, 5: 16, 6: 32, 7: 32, 8: 32, 9: 256}

_TILED = 0x200       # version-field bit 9: single-part tiled
_MULTIPART = 0x1000  # bit 12: multi-part file


class ExrError(ValueError):
    """Not an EXR file, or a layout this reader does not handle."""


@dataclass
class ExrChannel:
    name: str
    pixel_type: str
    x_sampling: int = 1
    y_sampling: int = 1


@dataclass
class ExrHeader:
    version: int
    flags: int
    channels: list[ExrChannel] = field(default_factory=list)
    compression: str = "none"
    compression_id: int = 0
    data_window: tuple[int, int, int, int] = (0, 0, 0, 0)
    display_window: tuple[int, int, int, int] = (0, 0, 0, 0)
    line_order: int = 0
    attributes: dict[str, str] = field(default_factory=dict)
    header_end: int = 0

    @property
    def tiled(self) -> bool:
        return bool(self.flags & _TILED)

    @property
    def multipart(self) -> bool:
        return bool(self.flags & _MULTIPART)

    @property
    def data_size(self) -> tuple[int, int]:
        x0, y0, x1, y1 = self.data_window
        return x1 - x0 + 1, y1 - y0 + 1

    @property
    def full_frame(self) -> bool:
        return self.data_window == self.display_window

    def summary(self) -> dict:
        return {
            "dataWindow": list(self.data_window),
            "displayWindow": list(self.display_window),
            "fullFrame": self.full_frame,
            "compression": self.compression,
            "tiled": self.tiled,
            "multipart": self.multipart,
            "channels": [{"name": c.name, "type": c.pixel_type} for c in self.channels],
        }


def _cstring(buf: bytes, pos: int) -> tuple[str, int]:
    end = buf.index(b"\0", pos)
    return buf[pos:end].decode("latin-1"), end + 1


def read_header(path: str | Path) -> ExrHeader:
    """Parse the first (or only) header of an EXR file."""
    data = Path(path).read_bytes()
    return _parse_header(data)


def _parse_header(data: bytes) -> ExrHeader:
    if len(data) < 8:
        raise ExrError("file too short for an EXR header")
    magic, version_field = struct.unpack_from("<iI", data, 0)
    if magic != MAGIC:
        raise ExrError("not an OpenEXR file (bad magic number)")
    header = ExrHeader(version=version_field & 0xFF, flags=version_field & ~0xFF)
    pos = 8
    while True:
        if pos >= len(data):
            raise ExrError("truncated header")
        if data[pos] == 0:
            pos += 1
            break
        name, pos = _cstring(data, pos)
        type_name, pos = _cstring(data, pos)
        (size,) = struct.unpack_from("<i", data, pos)
        pos += 4
        value = data[pos:pos + size]
        pos += size
        if name == "channels" and type_name == "chlist":
            header.channels = _parse_chlist(value)
        elif name == "compression":
            header.compression_id = value[0]
            header.compression = COMPRESSIONS.get(value[0], f"unknown({value[0]})")
        elif name == "dataWindow" and type_name == "box2i":
            header.data_window = struct.unpack("<4i", value)
        elif name == "displayWindow" and type_name == "box2i":
            header.display_window = struct.unpack("<4i", value)
        elif name == "lineOrder":
            header.line_order = value[0]
        else:
            header.attributes[name] = type_name
    header.header_end = pos
    return header


def _parse_chlist(value: bytes) -> list[ExrChannel]:
    channels: list[ExrChannel] = []
    pos = 0
    while pos < len(value) and value[pos] != 0:
        name, pos = _cstring(value, pos)
        pixel_type, _linear, xs, ys = struct.unpack_from("<iB3xii", value, pos)
        pos += 16
        channels.append(ExrChannel(name, PIXEL_TYPES.get(pixel_type, str(pixel_type)), xs, ys))
    return channels


def _undo_zip(raw: bytes) -> bytes:
    # OpenEXR ZIP: predictor (byte deltas, +128 bias) then two interleaved halves.
    t = bytearray(raw)
    for i in range(1, len(t)):
        t[i] = (t[i - 1] + t[i] - 128) & 0xFF
    out = bytearray(len(t))
    half = (len(t) + 1) // 2
    out[0::2] = t[:half]
    out[1::2] = t[half:]
    return bytes(out)


def _undo_rle(raw: bytes, expected: int) -> bytes:
    out = bytearray()
    pos = 0
    while pos < len(raw) and len(out) < expected:
        count = struct.unpack_from("b", raw, pos)[0]
        pos += 1
        if count < 0:
            out += raw[pos:pos - count]
            pos += -count
        else:
            out += bytes([raw[pos]]) * (count + 1)
            pos += 1
    # RLE data is also predictor-encoded and interleaved, like ZIP.
    return _undo_zip(bytes(out))


def read_pixels(path: str | Path) -> tuple[ExrHeader, dict[str, list[list[float]]]]:
    """Decode every channel of a single-part scanline EXR into rows of floats."""
    data = Path(path).read_bytes()
    header = _parse_header(data)
    if header.tiled or header.multipart:
        raise ExrError("tiled and multi-part EXR files are not supported by this reader")
    if header.compression_id not in (0, 1, 2, 3):
        raise ExrError(f"compression {header.compression} is not supported by this reader")
    if any(c.x_sampling != 1 or c.y_sampling != 1 for c in header.channels):
        raise ExrError("sub-sampled channels are not supported by this reader")
    width, height = header.data_size
    lines = LINES_PER_CHUNK[header.compression_id]
    chunk_count = (height + lines - 1) // lines
    offsets = struct.unpack_from(f"<{chunk_count}Q", data, header.header_end)
    channels = sorted(header.channels, key=lambda c: c.name)
    rows: dict[str, list[list[float]]] = {c.name: [] for c in channels}
    y0 = header.data_window[1]
    line_bytes = sum(PIXEL_SIZES[_type_id(c.pixel_type)] * width for c in channels)
    decoded: dict[int, bytes] = {}
    for offset in offsets:
        y, size = struct.unpack_from("<ii", data, offset)
        payload = data[offset + 8:offset + 8 + size]
        n_lines = min(lines, y0 + height - y)
        expected = line_bytes * n_lines
        if size == expected or header.compression_id == 0:
            block = payload
        elif header.compression_id in (2, 3):
            block = _undo_zip(zlib.decompress(payload))
        else:
            block = _undo_rle(payload, expected)
        decoded[y] = block
    for y in sorted(decoded):
        block = decoded[y]
        n_lines = len(block) // line_bytes if line_bytes else 0
        pos = 0
        for _ in range(n_lines):
            for c in channels:
                tid = _type_id(c.pixel_type)
                fmt = {0: "I", 1: "e", 2: "f"}[tid]
                values = struct.unpack_from(f"<{width}{fmt}", block, pos)
                pos += PIXEL_SIZES[tid] * width
                rows[c.name].append([float(v) for v in values])
    return header, rows


def _type_id(name: str) -> int:
    for key, value in PIXEL_TYPES.items():
        if value == name:
            return key
    raise ExrError(f"unknown pixel type {name}")
