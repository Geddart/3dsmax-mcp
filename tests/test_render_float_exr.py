"""render_float_exr: path policy, MAXScript contract, header read-back; and the
stdlib EXR reader against synthetic NONE / ZIP / ZIPS files."""
import json
import os
import struct
import tempfile
import time
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from maxmcp.helpers.exr import (
    ExrError,
    _undo_zip,
    _zip_encode,
    pad_to_display_window,
    read_header,
    read_pixels,
)
from maxmcp.tools import render_exr
from maxmcp.tools.render_exr import build_render_float_exr_maxscript, render_float_exr


def _attr(name: str, type_name: str, value: bytes) -> bytes:
    return name.encode() + b"\0" + type_name.encode() + b"\0" + struct.pack("<i", len(value)) + value


def _reference_zip_encode(raw: bytes) -> bytes:
    """Straightforward per-byte encoder (independent of the module's fast one)."""
    half = (len(raw) + 1) // 2
    t = bytearray(len(raw))
    t[:half] = raw[0::2]
    t[half:] = raw[1::2]
    out = bytearray(t)
    for i in range(len(t) - 1, 0, -1):
        out[i] = (t[i] - t[i - 1] + 128 + 256) & 0xFF
    return zlib.compress(bytes(out))


def write_exr(path: Path, width: int, height: int, value_fn, *, pixel_type: int = 2,
              compression: int = 0, data_window=None, extra_attr: bool = False) -> None:
    """Minimal scanline EXR writer (channels B, G, R) used only by these tests."""
    dw = data_window or (0, 0, width - 1, height - 1)
    channels = b""
    for name in ("B", "G", "R"):
        channels += name.encode() + b"\0" + struct.pack("<iB3xii", pixel_type, 0, 1, 1)
    channels += b"\0"
    header = struct.pack("<iI", 20000630, 2)
    if extra_attr:
        header += _attr("owner", "string", b"mcp-test")
    header += _attr("channels", "chlist", channels)
    header += _attr("compression", "compression", bytes([compression]))
    header += _attr("dataWindow", "box2i", struct.pack("<4i", *dw))
    header += _attr("displayWindow", "box2i", struct.pack("<4i", 0, 0, width - 1, height - 1))
    header += _attr("lineOrder", "lineOrder", b"\0")
    header += b"\0"
    dw_w, dw_h = dw[2] - dw[0] + 1, dw[3] - dw[1] + 1
    fmt = "f" if pixel_type == 2 else "e"
    lines_per_chunk = {0: 1, 2: 1, 3: 16}[compression]
    chunks = []
    for y0 in range(0, dw_h, lines_per_chunk):
        raw = b""
        for y in range(y0, min(y0 + lines_per_chunk, dw_h)):
            for channel in ("B", "G", "R"):
                raw += struct.pack(f"<{dw_w}{fmt}", *[value_fn(channel, x, y) for x in range(dw_w)])
        payload = raw if compression == 0 else _reference_zip_encode(raw)
        if compression and len(payload) >= len(raw):
            payload = raw
        chunks.append(struct.pack("<ii", dw[1] + y0, len(payload)) + payload)
    offset = len(header) + 8 * len(chunks)
    table = b""
    for chunk in chunks:
        table += struct.pack("<Q", offset)
        offset += len(chunk)
    path.write_bytes(header + table + b"".join(chunks))


class ExrReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _value(self, channel, x, y):
        return {"R": 5.0 + x * 0.25, "G": 2.5, "B": float(y)}[channel]

    def test_uncompressed_float_round_trip(self) -> None:
        path = self.dir / "a.exr"
        write_exr(path, 8, 4, self._value)
        header, rows = read_pixels(path)
        self.assertTrue(header.full_frame)
        self.assertEqual([c.pixel_type for c in header.channels], ["float"] * 3)
        self.assertEqual(rows["R"][2][3], 5.75)
        self.assertEqual(rows["B"][3][0], 3.0)

    def test_zip_and_zips_half(self) -> None:
        for compression in (2, 3):
            path = self.dir / f"z{compression}.exr"
            write_exr(path, 40, 20, self._value, pixel_type=1, compression=compression)
            header, rows = read_pixels(path)
            self.assertEqual(header.compression, {2: "zips", 3: "zip"}[compression])
            self.assertEqual(len(rows["R"]), 20)
            self.assertEqual(rows["R"][19][4], 6.0)
            self.assertEqual(rows["G"][0][39], 2.5)

    def test_cropped_data_window_is_reported(self) -> None:
        path = self.dir / "crop.exr"
        write_exr(path, 16, 8, self._value, data_window=(2, 1, 9, 5))
        header = read_header(path)
        self.assertFalse(header.full_frame)
        self.assertEqual(header.summary()["dataWindow"], [2, 1, 9, 5])
        self.assertEqual(header.summary()["displayWindow"], [0, 0, 15, 7])

    def test_zip_filter_round_trip(self) -> None:
        payload = bytes((i * 37 + (i >> 3)) & 0xFF for i in range(4099))
        self.assertEqual(_undo_zip(zlib.decompress(_zip_encode(payload))), payload)
        self.assertEqual(_undo_zip(zlib.decompress(_zip_encode(b"\x07"))), b"\x07")

    def test_pad_region_render_to_full_frame(self) -> None:
        for pixel_type, compression in ((2, 0), (1, 3), (2, 2)):
            path = self.dir / f"region_{pixel_type}_{compression}.exr"
            write_exr(path, 16, 8, lambda c, x, y: 5.0 + x + 10 * y, pixel_type=pixel_type,
                      compression=compression, data_window=(3, 2, 9, 5), extra_attr=True)
            before = read_header(path)
            self.assertEqual(pad_to_display_window(path), (3, 2, 9, 5))
            header, rows = read_pixels(path)
            self.assertTrue(header.full_frame)
            self.assertEqual(header.compression, "zip")
            self.assertEqual([c.pixel_type for c in header.channels], [c.pixel_type for c in before.channels])
            self.assertIn(("owner", "string", b"mcp-test"), header.raw_attributes)
            # Region pixels land where they belong: data x=0,y=0 -> frame (3,2).
            self.assertEqual(rows["R"][2][3], 5.0)
            self.assertEqual(rows["R"][5][9], 5.0 + 6 + 30)
            self.assertEqual(rows["R"][0][0], 0.0)
            self.assertEqual(rows["G"][7][15], 0.0)
            self.assertEqual(rows["R"][3][2], 0.0)
            self.assertIsNone(pad_to_display_window(path))  # already full frame

    def test_rejects_non_exr(self) -> None:
        path = self.dir / "x.exr"
        path.write_bytes(b"not an exr file")
        with self.assertRaises(ExrError):
            read_header(path)


class RenderFloatExrToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.scene_dir = Path(self.tmp.name) / "scene"
        self.scene_dir.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_maxscript_sets_vray_raw_props_and_restores(self) -> None:
        script = build_render_float_exr_maxscript("C:\\proj\\out.exr", width=160, height=90, camera="Cam")
        for needle in ("#output_saveRawFile true", '#output_rawFileName "C:/proj/out.exr"',
                       "#output_rawExrUseHalf false", "#colorMapping_clampOutput false",
                       "#colorMapping_adaptationOnly 1", "renderType:#view", "V_Ray_settings",
                       "for e in mcpSaved do try (setProperty e[1] e[2] e[3])",
                       "fopenexr.setSaveRegion false", "bitmap (160) (90) hdr:true", "camera:cam"):
            self.assertIn(needle, script)
        self.assertNotIn("\\", script.split("mcpErr = undefined")[0].split("output_rawFileName")[1][:40])

    def test_color_mapping_kept_when_requested(self) -> None:
        script = build_render_float_exr_maxscript("C:/p/o.exr", apply_color_mapping=True, half=True)
        self.assertIn("if false do mcpSetProp cmHost #colorMapping_adaptationOnly 1", script)
        self.assertIn("#output_rawExrUseHalf true", script)
        self.assertIn("outputwidth:(renderWidth)", script)

    def test_refuses_path_outside_allowed_roots_without_rendering(self) -> None:
        with patch.object(render_exr.client, "send_command",
                          return_value={"result": str(self.scene_dir) + "\\"}) as send:
            result = json.loads(render_float_exr(output_path="C:/Windows/forbidden.exr"))
        self.assertEqual(result["code"], "SAFE_MODE")
        self.assertEqual(send.call_count, 1)  # only maxFilePath was read

    def test_rejects_non_exr_extension(self) -> None:
        result = json.loads(render_float_exr(output_path=str(self.scene_dir / "a.png")))
        self.assertEqual(result["code"], "BAD_PARAM")

    def test_renames_frame_numbered_file_and_reads_header(self) -> None:
        target = self.scene_dir / "beauty.exr"

        def fake_send(command, timeout=None):
            if command == "maxFilePath":
                return {"result": str(self.scene_dir) + "\\"}
            # V-Ray writes name.0000.exr next to the requested file.
            write_exr(self.scene_dir / "beauty.0000.exr", 8, 4, lambda c, x, y: 5.0)
            return {"result": "MCPEXR|OK|V_Ray_GPU_7|vray_raw|output_saveRawFile=true;output_rawExrUseHalf=false"}

        with patch.object(render_exr.client, "send_command", side_effect=fake_send):
            result = json.loads(render_float_exr(output_path=str(target), width=8, height=4))
        self.assertEqual(result["output"], str(target))
        self.assertTrue(target.exists())
        self.assertFalse((self.scene_dir / "beauty.0000.exr").exists())
        self.assertTrue(result["exr"]["fullFrame"])
        self.assertEqual(result["propertiesSet"], ["output_saveRawFile=true", "output_rawExrUseHalf=false"])
        self.assertNotIn("warnings", result)

    def test_region_cropped_render_is_padded(self) -> None:
        target = self.scene_dir / "region.exr"

        def fake_send(command, timeout=None):
            if command == "maxFilePath":
                return {"result": str(self.scene_dir) + "\\"}
            write_exr(target, 16, 8, lambda c, x, y: 5.0, compression=2, data_window=(3, 2, 9, 5))
            return {"result": "MCPEXR|OK|V_Ray_7|vray_raw|output_saveRawFile=true"}

        with patch.object(render_exr.client, "send_command", side_effect=fake_send):
            result = json.loads(render_float_exr(output_path=str(target), width=16, height=8))
        self.assertEqual(result["paddedFrom"], [3, 2, 9, 5])
        self.assertTrue(result["exr"]["fullFrame"])
        self.assertTrue(any("padded" in w for w in result["warnings"]))
        _, rows = read_pixels(target)
        self.assertEqual(rows["R"][2][3], 5.0)
        self.assertEqual(rows["R"][0][0], 0.0)

    def test_failed_render_keeps_previous_file(self) -> None:
        target = self.scene_dir / "keep.exr"
        target.write_bytes(b"previous render")
        old = time.time() - 3600
        os.utime(target, (old, old))

        def fake_send(command, timeout=None):
            if command == "maxFilePath":
                return {"result": str(self.scene_dir) + "\\"}
            return {"result": "MCPEXR|OK|V_Ray_7|vray_raw|"}  # claims success, writes nothing

        with patch.object(render_exr.client, "send_command", side_effect=fake_send):
            result = json.loads(render_float_exr(output_path=str(target)))
        self.assertIn("no EXR was written", result["error"])
        self.assertEqual(target.read_bytes(), b"previous render")

    def test_render_error_is_reported(self) -> None:
        def fake_send(command, timeout=None):
            if command == "maxFilePath":
                return {"result": str(self.scene_dir) + "\\"}
            return {"result": "MCPEXR|ERR|-- Runtime error: no camera"}

        with patch.object(render_exr.client, "send_command", side_effect=fake_send):
            result = json.loads(render_float_exr(output_path=str(self.scene_dir / "x.exr")))
        self.assertIn("Render failed", result["error"])


if __name__ == "__main__":
    unittest.main()
