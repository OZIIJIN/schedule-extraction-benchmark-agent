from __future__ import annotations

from pathlib import Path
import re


VERSION_PATTERN = re.compile(r"-(\d{2})$")


def version_number(path: Path) -> int:
    match = VERSION_PATTERN.search(path.stem)
    if not match:
        return 0
    return int(match.group(1))


def versioned_paths(path: Path) -> list[Path]:
    return sorted(
        path.parent.glob(f"{path.stem}-[0-9][0-9]{path.suffix}"),
        key=version_number,
    )


def latest_versioned_path(path: Path) -> Path:
    paths = versioned_paths(path)
    if paths:
        return paths[-1]
    return path


def next_versioned_path(path: Path) -> Path:
    sequence = max([version_number(candidate) for candidate in versioned_paths(path)], default=0) + 1
    return path.with_name(f"{path.stem}-{sequence:02d}{path.suffix}")


def write_text_with_version(path: Path, content: str, *, encoding: str = "utf-8") -> Path:
    path.write_text(content, encoding=encoding)
    versioned_path = next_versioned_path(path)
    versioned_path.write_text(content, encoding=encoding)
    return versioned_path


def write_text_version_only(path: Path, content: str, *, encoding: str = "utf-8") -> Path:
    versioned_path = next_versioned_path(path)
    versioned_path.write_text(content, encoding=encoding)
    return versioned_path
