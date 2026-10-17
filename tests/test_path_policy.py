import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from maxmcp import path_policy
from maxmcp.path_policy import PathNotAllowedError, resolve_write_path


class PathPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.local = Path(self.tmp.name) / "local"
        (self.local / "3dsmax-mcp").mkdir(parents=True)
        env = patch.dict(os.environ, {"LOCALAPPDATA": str(self.local), path_policy.ALLOWED_ENV: ""}, clear=False)
        env.start()
        self.addCleanup(env.stop)

    def write_config(self, dirs: str) -> None:
        (self.local / "3dsmax-mcp" / "mcp_config.ini").write_text(
            f"[mcp]\nsafe_mode = true\n[safe_mode]\nallowed_dirs = {dirs}\n", encoding="utf-8")

    def test_configured_dir_is_allowed_case_insensitively(self) -> None:
        project = Path(self.tmp.name) / "Proj"
        self.write_config(str(project))
        out = resolve_write_path(str(project).upper() + r"\max\geo.obj")
        self.assertTrue(str(out).lower().endswith(r"proj\max\geo.obj"))

    def test_traversal_cannot_escape_an_allowed_root(self) -> None:
        project = Path(self.tmp.name) / "Proj"
        self.write_config(str(project))
        with self.assertRaises(PathNotAllowedError):
            resolve_write_path(str(project / ".." / "Other" / "x.obj"))

    def test_sibling_with_shared_prefix_is_not_inside(self) -> None:
        project = Path(self.tmp.name) / "Proj"
        self.write_config(str(project))
        with self.assertRaises(PathNotAllowedError):
            resolve_write_path(str(Path(self.tmp.name) / "Proj2" / "x.obj"))

    def test_scene_dir_and_temp_are_always_allowed(self) -> None:
        scene = Path(self.tmp.name) / "scene"
        self.assertTrue(resolve_write_path(scene / "out.exr", scene_dir=scene))
        self.assertTrue(resolve_write_path(path_policy.temp_root() / "a.obj"))

    def test_multiple_dirs_and_env(self) -> None:
        a, b, c = (Path(self.tmp.name) / n for n in ("A", "B", "C"))
        self.write_config(f"{a}; {b}")
        with patch.dict(os.environ, {path_policy.ALLOWED_ENV: str(c)}):
            for root in (a, b, c):
                self.assertTrue(resolve_write_path(root / "f.obj"))

    def test_nothing_configured_refuses_arbitrary_paths(self) -> None:
        with self.assertRaises(PathNotAllowedError) as ctx:
            resolve_write_path(r"Z:\elsewhere\f.obj")
        self.assertIn("allowed_dirs", str(ctx.exception))

    def test_empty_path_refused(self) -> None:
        with self.assertRaises(PathNotAllowedError):
            resolve_write_path("  ")


if __name__ == "__main__":
    unittest.main()
