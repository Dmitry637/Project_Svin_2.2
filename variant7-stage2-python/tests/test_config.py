from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.config import ConfigError, load_config

PROJECT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def test_sample_config_loads(self) -> None:
        config = load_config(PROJECT / "config.ini")
        self.assertEqual(config.package_name, "com.example:demo-app")
        self.assertEqual(config.package_version, "1.0.0")
        self.assertEqual(config.resolved_repository_mode, "local")
        self.assertEqual(config.package_name, "com.example:demo-app")

    def test_missing_config(self) -> None:
        with self.assertRaisesRegex(ConfigError, "не найден"):
            load_config(PROJECT / "missing.ini")

    def test_invalid_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.ini"
            path.write_text(
                "[package]\nname = invalid\nversion = 1.0\n"
                "[repository]\nlocation = repo\nmode = local\n"
                "[visualization]\ngraph_image = graph.png\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigError, "groupId:artifactId"):
                load_config(path)

    def test_empty_parameter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.ini"
            path.write_text(
                "[package]\nname = com.example:app\nversion = \n"
                "[repository]\nlocation = repo\nmode = local\n"
                "[visualization]\ngraph_image = graph.png\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigError, "не должен быть пустым"):
                load_config(path)

    def test_local_remote_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.ini"
            path.write_text(
                "[package]\nname = com.example:app\nversion = 1.0\n"
                "[repository]\nlocation = https://example.org/maven\nmode = local\n"
                "[visualization]\ngraph_image = graph.png\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigError, "локальным путём"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
