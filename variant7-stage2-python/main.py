from __future__ import annotations

import argparse
import sys

from src.config import ConfigError, load_config
from src.maven import DependencyResolutionError, MavenRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Вариант №7, этап 2: получение и вывод прямых зависимостей "
            "Maven-пакета заданной версии."
        )
    )
    parser.add_argument(
        "--config",
        default="config.ini",
        metavar="FILE",
        help="путь к INI-файлу (по умолчанию: config.ini)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        dependencies = MavenRepository(config).direct_dependencies()
    except ConfigError as exc:
        print(f"Ошибка конфигурации: {exc}", file=sys.stderr)
        return 2
    except DependencyResolutionError as exc:
        print(f"Ошибка получения зависимостей: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nОперация отменена пользователем.", file=sys.stderr)
        return 130

    print(f"Пакет: {config.package_name}:{config.package_version}")
    print("Прямые зависимости Maven:")
    if not dependencies:
        print("Прямые зависимости не объявлены.")
    else:
        for dependency in dependencies:
            details = [f"scope={dependency.scope}"]
            if dependency.optional:
                details.append("optional=true")
            print(f"- {dependency.coordinates} [{', '.join(details)}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
