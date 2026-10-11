"""Minimal OpenEXR reader: header (windows, channels, compression) and pixels
of single-part scanline files with NONE / RLE / ZIPS / ZIP compression.

Pure standard library so the MCP server can read back what a render wrote
(dataWindow vs displayWindow, float vs half channels) and acceptance scripts
can check pixel values without OpenImageIO/OpenEXR wheels.
"""
from __future__ import annotations

import struct
import zlib
from itertools import accumulate, chain
from operator import sub
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
    # Every attribute as stored (name, type, value bytes), in file order.
    raw_attributes: list[tuple[str, str, bytes]] = field(default_factory=list)

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
        header.raw_attributes.append((name, type_name, value))
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
    """OpenEXR ZIP/RLE post-filter: undo the +128 byte predictor, de-interleave.

    The predictor is a running sum mod 256 of (byte - 128), so it is computed
    with C-level accumulate/map instead of a per-byte Python loop (a 4K RGBA
    float frame is ~130 MB of samples).
    """
    if not raw:
        return b""
    deltas = chain((raw[0],), map((-128).__add__, raw[1:]))
    t = bytes(map((255).__and__, accumulate(deltas)))
    out = bytearray(len(t))
    half = (len(t) + 1) // 2
    out[0::2] = t[:half]
    out[1::2] = t[half:]
    return bytes(out)


def _zip_encode(raw: bytes) -> bytes:
    """Inverse of :func:`_undo_zip`: interleave halves, byte-delta (+128), zlib."""
    if not raw:
        return zlib.compress(b"")
    t = raw[0::2] + raw[1::2]
    diffs = map((255).__and__, map((128).__add__, map(sub, t[1:], t[:-1])))
    return zlib.compress(t[:1] + bytes(diffs))


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


def _scanline_blocks(data: bytes, header: ExrHeader) -> list[tuple[int, bytes]]:
    """Decoded (first y, bytes) per chunk, sorted by y, for a supported file."""
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
    y0 = header.data_window[1]
    line_bytes = _line_bytes(header, width)
    blocks = []
    for offset in offsets:
        y, size = struct.unpack_from("<ii", data, offset)
        payload = data[offset + 8:offset + 8 + size]
        expected = line_bytes * min(lines, y0 + height - y)
        if size == expected or header.compression_id == 0:
            block = payload  # stored uncompressed
        elif header.compression_id in (2, 3):
            block = _undo_zip(zlib.decompress(payload))
        else:
            block = _undo_rle(payload, expected)
        blocks.append((y, block))
    blocks.sort(key=lambda item: item[0])
    return blocks


def _sorted_channels(header: ExrHeader) -> list[ExrChannel]:
    return sorted(header.channels, key=lambda c: c.name)


def _line_bytes(header: ExrHeader, width: int) -> int:
    return sum(PIXEL_SIZES[_type_id(c.pixel_type)] * width for c in header.channels)


def read_pixels(path: str | Path) -> tuple[ExrHeader, dict[str, list[list[float]]]]:
    """Decode every channel of a single-part scanline EXR into rows of floats."""
    data = Path(path).read_bytes()
    header = _parse_header(data)
    width, _ = header.data_size
    channels = _sorted_channels(header)
    rows: dict[str, list[list[float]]] = {c.name: [] for c in channels}
    line_bytes = _line_bytes(header, width)
    for _, block in _scanline_blocks(data, header):
        pos = 0
        for _line in range(len(block) // line_bytes if line_bytes else 0):
            for c in channels:
                tid = _type_id(c.pixel_type)
                fmt = {0: "I", 1: "e", 2: "f"}[tid]
                values = struct.unpack_from(f"<{width}{fmt}", block, pos)
                pos += PIXEL_SIZES[tid] * width
                rows[c.name].append([float(v) for v in values])
    return header, rows


def pad_to_display_window(path: str | Path) -> tuple[int, int, int, int] | None:
    """Rewrite a cropped single-part scanline EXR so dataWindow == displayWindow.

    Pixels outside the original dataWindow become 0 (a region render keeps its
    pixels where they belong in the full frame). Works on raw sample bytes
    (zero bytes are 0.0 for half/float/uint), keeps every other header
    attribute byte for byte, and rewrites the file ZIP-compressed in
    increasing Y. Returns the original dataWindow, or None when the file
    already was full frame.
    """
    path = Path(path)
    data = path.read_bytes()
    header = _parse_header(data)
    if header.full_frame:
        return None
    dx0, dy0, dx1, dy1 = header.display_window
    full_w, full_h = dx1 - dx0 + 1, dy1 - dy0 + 1
    x0, y0, _, _ = header.data_window
    data_w, _ = header.data_size
    channels = _sorted_channels(header)
    sizes = [PIXEL_SIZES[_type_id(c.pixel_type)] for c in channels]
    # Columns of the data window that land inside the display window.
    col_lo = max(0, dx0 - x0)
    col_hi = min(data_w, dx1 - x0 + 1)
    in_line = _line_bytes(header, data_w)

    full_lines: dict[int, bytes] = {}
    for first_y, block in _scanline_blocks(data, header):
        for k in range(len(block) // in_line if in_line else 0):
            y = first_y + k
            if not dy0 <= y <= dy1:
                continue
            line = bytearray()
            pos = k * in_line
            for size in sizes:
                channel = block[pos:pos + size * data_w]
                pos += size * data_w
                left = (x0 + col_lo - dx0) * size
                kept = channel[col_lo * size:col_hi * size]
                line += bytes(left) + kept + bytes(full_w * size - left - len(kept))
            full_lines[y] = bytes(line)

    replacements = {
        "dataWindow": struct.pack("<4i", *header.display_window),
        "compression": bytes([3]),  # ZIP, 16 scanlines per chunk
        "lineOrder": bytes([0]),    # increasing Y
    }
    out = bytearray(struct.pack("<iI", MAGIC, header.version | header.flags))
    for name, type_name, value in header.raw_attributes:
        value = replacements.get(name, value)
        out += name.encode("latin-1") + b"\0" + type_name.encode("latin-1") + b"\0"
        out += struct.pack("<i", len(value)) + value
    out += b"\0"

    empty_line = bytes(sum(size * full_w for size in sizes))
    lines = LINES_PER_CHUNK[3]
    chunks: list[bytes] = []
    for first in range(dy0, dy1 + 1, lines):
        raw = b"".join(full_lines.get(y, empty_line) for y in range(first, min(first + lines, dy1 + 1)))
        payload = _zip_encode(raw)
        if len(payload) >= len(raw):
            payload = raw  # stored uncompressed, as OpenEXR does
        chunks.append(struct.pack("<ii", first, len(payload)) + payload)
    offset = len(out) + 8 * len(chunks)
    table = bytearray()
    for chunk in chunks:
        table += struct.pack("<Q", offset)
        offset += len(chunk)
    tmp = path.with_name(path.name + ".padtmp")
    tmp.write_bytes(bytes(out) + bytes(table) + b"".join(chunks))
    tmp.replace(path)
    return header.data_window


def _type_id(name: str) -> int:
    for key, value in PIXEL_TYPES.items():
        if value == name:
            return key
    raise ExrError(f"unknown pixel type {name}")
