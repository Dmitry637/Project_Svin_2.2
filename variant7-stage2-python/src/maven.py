from __future__ import annotations

import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from src.config import AppConfig


class DependencyResolutionError(RuntimeError):
    """Raised when a Maven POM cannot be loaded or parsed."""


@dataclass(frozen=True)
class Dependency:
    group_id: str
    artifact_id: str
    version: str
    scope: str = "compile"
    optional: bool = False

    @property
    def coordinates(self) -> str:
        return f"{self.group_id}:{self.artifact_id}:{self.version}"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(element: ET.Element, name: str) -> ET.Element | None:
    return next((node for node in element if _local_name(node.tag) == name), None)


def _text(element: ET.Element, name: str, default: str = "") -> str:
    node = _child(element, name)
    return (node.text or "").strip() if node is not None else default


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [node for node in element if _local_name(node.tag) == name]


def _resolve_properties(value: str, properties: dict[str, str]) -> str:
    result = value.strip()
    # Resolve nested/simple Maven properties without depending on Maven itself.
    for _ in range(12):
        updated = re.sub(
            r"\$\{([^}]+)\}",
            lambda match: properties.get(match.group(1), match.group(0)),
            result,
        )
        if updated == result:
            break
        result = updated
    return result


class MavenRepository:
    """Read raw Maven POM files using only Python's standard library."""

    def __init__(self, config: AppConfig, timeout: float = 15.0) -> None:
        self.config = config
        self.timeout = timeout
        self.package_group, self.package_artifact = config.package_name.split(":", 1)

    def _pom_relative_path(self, group_id: str, artifact_id: str, version: str) -> Path:
        group_path = Path(*group_id.split("."))
        return group_path / artifact_id / version / f"{artifact_id}-{version}.pom"

    def _load_pom(self, group_id: str, artifact_id: str, version: str) -> bytes:
        repository = self.config.repository
        relative_path = self._pom_relative_path(group_id, artifact_id, version)
        if self.config.resolved_repository_mode == "remote":
            relative_url = "/".join(quote(part, safe=".-_~") for part in relative_path.parts)
            url = f"{repository.rstrip('/')}/{relative_url}"
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Variant7DependencyVisualizer/1.0"},
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return response.read()
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    raise DependencyResolutionError(
                        f"POM не найден (HTTP 404): {url}"
                    ) from exc
                raise DependencyResolutionError(
                    f"ошибка HTTP {exc.code} при запросе POM: {url}"
                ) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise DependencyResolutionError(
                    f"не удалось получить POM по адресу {url}: {exc}"
                ) from exc

        local_root = Path(repository)
        if local_root.is_file():
            # A single local POM is supported for the package requested in config.
            if (group_id, artifact_id, version) != (
                self.package_group,
                self.package_artifact,
                self.config.package_version,
            ):
                raise DependencyResolutionError(
                    "для получения POM зависимостей нужен каталог Maven-репозитория; "
                    "одиночный .pom-файл содержит только исходный пакет."
                )
            pom_path = local_root
        else:
            pom_path = local_root / relative_path
        try:
            return pom_path.read_bytes()
        except OSError as exc:
            raise DependencyResolutionError(
                f"POM не найден или недоступен для чтения: {pom_path}"
            ) from exc

    def _parse_pom(self, data: bytes, coordinates: tuple[str, str, str]) -> ET.Element:
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            raise DependencyResolutionError(f"POM содержит некорректный XML: {exc}") from exc
        if _local_name(root.tag) != "project":
            raise DependencyResolutionError("корневой XML-элемент POM должен быть project.")
        return root

    def _properties(self, root: ET.Element, coordinates: tuple[str, str, str]) -> dict[str, str]:
        group_id, artifact_id, version = coordinates
        properties = {
            "project.groupId": group_id,
            "pom.groupId": group_id,
            "project.artifactId": artifact_id,
            "pom.artifactId": artifact_id,
            "project.version": version,
            "pom.version": version,
            "project.parent.groupId": _text(_child(root, "parent") or root, "groupId"),
            "project.parent.version": _text(_child(root, "parent") or root, "version"),
        }
        props_node = _child(root, "properties")
        if props_node is not None:
            for child in props_node:
                properties[_local_name(child.tag)] = (child.text or "").strip()
        # Properties may reference other properties, so iterate to a fixed point.
        for _ in range(12):
            changed = False
            for key, value in list(properties.items()):
                resolved = _resolve_properties(value, properties)
                if resolved != value:
                    properties[key] = resolved
                    changed = True
            if not changed:
                break
        return properties

    def _managed_versions(
        self, root: ET.Element, properties: dict[str, str]
    ) -> dict[tuple[str, str], str]:
        result: dict[tuple[str, str], str] = {}
        management = _child(root, "dependencyManagement")
        deps_node = _child(management, "dependencies") if management is not None else None
        if deps_node is None:
            return result
        for dep in _children(deps_node, "dependency"):
            group = _resolve_properties(_text(dep, "groupId"), properties)
            artifact = _resolve_properties(_text(dep, "artifactId"), properties)
            version = _resolve_properties(_text(dep, "version"), properties)
            if group and artifact and version and "${" not in version:
                result[(group, artifact)] = version
        return result

    def direct_dependencies(self) -> list[Dependency]:
        coordinates = (
            self.package_group,
            self.package_artifact,
            self.config.package_version,
        )
        data = self._load_pom(*coordinates)
        root = self._parse_pom(data, coordinates)
        properties = self._properties(root, coordinates)
        managed_versions = self._managed_versions(root, properties)
        deps_node = _child(root, "dependencies")
        if deps_node is None:
            return []

        dependencies: list[Dependency] = []
        for node in _children(deps_node, "dependency"):
            group = _resolve_properties(_text(node, "groupId"), properties)
            artifact = _resolve_properties(_text(node, "artifactId"), properties)
            version = _resolve_properties(_text(node, "version"), properties)
            if not group or not artifact:
                raise DependencyResolutionError(
                    "в POM найдена зависимость без groupId или artifactId."
                )
            if not version or "${" in version:
                version = managed_versions.get((group, artifact), "версия не разрешена")
            scope = _resolve_properties(_text(node, "scope", "compile"), properties) or "compile"
            optional_text = _resolve_properties(_text(node, "optional", "false"), properties)
            dependencies.append(
                Dependency(
                    group_id=group,
                    artifact_id=artifact,
                    version=version,
                    scope=scope,
                    optional=optional_text.lower() == "true",
                )
            )
        return dependencies
