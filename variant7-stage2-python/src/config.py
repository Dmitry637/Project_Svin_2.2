from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class ConfigError(ValueError):
    """Raised when the user configuration is missing or invalid."""


@dataclass(frozen=True)
class AppConfig:
    package_name: str
    repository: str
    repository_mode: str
    resolved_repository_mode: str
    package_version: str
    graph_image: str
    config_path: Path


def _required(parser: configparser.ConfigParser, section: str, key: str) -> str:
    if not parser.has_section(section):
        raise ConfigError(f"в INI-файле отсутствует секция [{section}].")
    if not parser.has_option(section, key):
        raise ConfigError(
            f"в секции [{section}] отсутствует параметр {key}."
        )
    value = parser.get(section, key, fallback="").strip()
    if not value:
        raise ConfigError(
            f"параметр [{section}] {key} не должен быть пустым."
        )
    return value


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme.lower() in {"http", "https"} and bool(parsed.hostname)
    except ValueError:
        return False


def _validate_coordinates(value: str) -> str:
    parts = value.strip().split(":")
    if len(parts) != 2 or not all(parts):
        raise ConfigError(
            "package.name должен иметь Maven-формат groupId:artifactId, "
            "например com.example:demo-app."
        )
    if any(any(ch.isspace() for ch in part) for part in parts):
        raise ConfigError("package.name не должен содержать пробелы.")
    if any(part in {".", ".."} for part in parts):
        raise ConfigError("package.name содержит недопустимый сегмент.")
    return f"{parts[0]}:{parts[1]}"


def load_config(config_file: str | Path) -> AppConfig:
    """Read and validate settings from an INI file."""
    supplied_path = Path(config_file).expanduser()
    if not supplied_path.is_absolute():
        supplied_path = Path.cwd() / supplied_path
    config_path = supplied_path.resolve()
    if not config_path.exists():
        raise ConfigError(f"конфигурационный файл не найден: {config_path}")
    if not config_path.is_file():
        raise ConfigError(f"путь конфигурации должен быть файлом: {config_path}")

    parser = configparser.ConfigParser(interpolation=None)
    try:
        with config_path.open("r", encoding="utf-8-sig") as stream:
            parser.read_file(stream)
    except (OSError, configparser.Error) as exc:
        raise ConfigError(f"не удалось прочитать INI-файл: {exc}") from exc

    package_name = _validate_coordinates(_required(parser, "package", "name"))
    package_version = _required(parser, "package", "version")
    if any(ch.isspace() for ch in package_version) or "/" in package_version or "\\" in package_version:
        raise ConfigError("package.version содержит недопустимые символы.")

    repository_text = _required(parser, "repository", "location")
    repository_mode = _required(parser, "repository", "mode").lower()
    if repository_mode not in {"auto", "local", "remote"}:
        raise ConfigError(
            "repository.mode должен быть одним из значений: auto, local, remote."
        )

    is_url = _is_http_url(repository_text)
    if "://" in repository_text and not is_url:
        raise ConfigError(
            "repository.location содержит некорректный URL; "
            "поддерживаются http:// и https:// с именем хоста."
        )
    if repository_mode == "remote" and not is_url:
        raise ConfigError("для remote repository.location должен быть HTTP(S)-URL.")
    if repository_mode == "local" and is_url:
        raise ConfigError("для local repository.location должен быть локальным путём.")

    if is_url:
        repository = repository_text.rstrip("/")
        resolved_mode = "remote"
    else:
        local_path = Path(repository_text).expanduser()
        if not local_path.is_absolute():
            local_path = config_path.parent / local_path
        local_path = local_path.resolve()
        if not local_path.exists():
            raise ConfigError(f"локальный репозиторий не найден: {local_path}")
        if not (local_path.is_file() or local_path.is_dir()):
            raise ConfigError("repository.location должен указывать на файл или каталог.")
        if local_path.is_file() and local_path.suffix.lower() != ".pom":
            raise ConfigError("локальный файл репозитория должен иметь расширение .pom.")
        repository = str(local_path)
        resolved_mode = "local"

    graph_image = _required(parser, "visualization", "graph_image")
    return AppConfig(
        package_name=package_name,
        repository=repository,
        repository_mode=repository_mode,
        resolved_repository_mode=resolved_mode,
        package_version=package_version,
        graph_image=graph_image,
        config_path=config_path,
    )

