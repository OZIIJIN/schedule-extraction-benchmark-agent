from __future__ import annotations

from pathlib import Path


def versioned_paths(path: Path) -> list[Path]:
    return sorted(path.parent.glob(f"{path.stem}-[0-9][0-9]{path.suffix}"))


def latest_versioned_path(path: Path) -> Path:
    paths = versioned_paths(path)
    if paths:
        return paths[-1]
    return path


def next_versioned_path(path: Path) -> Path:
    sequence = 1
    while True:
        candidate = path.with_name(f"{path.stem}-{sequence:02d}{path.suffix}")
        if not candidate.exists():
            return candidate
        sequence += 1


def write_text_with_version(path: Path, content: str, *, encoding: str = "utf-8") -> Path:
    path.write_text(content, encoding=encoding)
    versioned_path = next_versioned_path(path)
    versioned_path.write_text(content, encoding=encoding)
    return versioned_path


def write_text_version_only(path: Path, content: str, *, encoding: str = "utf-8") -> Path:
    versioned_path = next_versioned_path(path)
    versioned_path.write_text(content, encoding=encoding)
    return versioned_path
