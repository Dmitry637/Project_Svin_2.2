from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.config import load_config
from src.maven import DependencyResolutionError, MavenRepository

PROJECT = Path(__file__).resolve().parents[1]


class MavenTests(unittest.TestCase):
    def test_reads_direct_dependencies_and_resolves_properties(self) -> None:
        config = load_config(PROJECT / "config.ini")
        dependencies = MavenRepository(config).direct_dependencies()
        self.assertEqual(len(dependencies), 2)
        self.assertEqual(dependencies[0].coordinates, "org.example:demo-core:2.1.0")
        self.assertEqual(dependencies[0].scope, "compile")
        self.assertEqual(dependencies[1].coordinates, "org.example:demo-utils:1.4.0")
        self.assertEqual(dependencies[1].scope, "runtime")
        self.assertTrue(dependencies[1].optional)

    def test_missing_target_pom_is_an_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path = Path(temp) / "config.ini"
            config_path.write_text(
                "[package]\nname = com.example:missing\nversion = 99\n"
                "[repository]\nlocation = .\nmode = local\n"
                "[visualization]\ngraph_image = graph.png\n",
                encoding="utf-8",
            )
            config = load_config(config_path)
            with self.assertRaisesRegex(DependencyResolutionError, "POM не найден"):
                MavenRepository(config).direct_dependencies()

    def test_pom_without_dependencies_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "org/example/empty/1.0"
            root.mkdir(parents=True)
            (root / "empty-1.0.pom").write_text(
                '<project xmlns="http://maven.apache.org/POM/4.0.0">'
                '<modelVersion>4.0.0</modelVersion></project>',
                encoding="utf-8",
            )
            config_path = Path(temp) / "config.ini"
            config_path.write_text(
                "[package]\nname = org.example:empty\nversion = 1.0\n"
                "[repository]\nlocation = .\nmode = local\n"
                "[visualization]\ngraph_image = graph.png\n",
                encoding="utf-8",
            )
            config = load_config(config_path)
            self.assertEqual(MavenRepository(config).direct_dependencies(), [])

    def test_single_pom_is_accepted_for_target_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            pom = Path(temp) / "demo.pom"
            pom.write_text(
                '<project xmlns="http://maven.apache.org/POM/4.0.0">'
                '<dependencies><dependency><groupId>org.demo</groupId>'
                '<artifactId>child</artifactId><version>1.2</version>'
                '</dependency></dependencies></project>',
                encoding="utf-8",
            )
            config_path = Path(temp) / "config.ini"
            config_path.write_text(
                "[package]\nname = com.example:demo\nversion = 1.0\n"
                f"[repository]\nlocation = {pom}\nmode = local\n"
                "[visualization]\ngraph_image = graph.png\n",
                encoding="utf-8",
            )
            config = load_config(config_path)
            deps = MavenRepository(config).direct_dependencies()
            self.assertEqual(deps[0].coordinates, "org.demo:child:1.2")


if __name__ == "__main__":
    unittest.main()
