"""Minimal YAML subset loader (stdlib only) for formula config."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_yaml(path: Path | str) -> Any:
    text = Path(path).read_text(encoding="utf-8")
    return parse_yaml(text)


def parse_yaml(text: str) -> Any:
    lines = _preprocess(text)
    value, idx = _parse_block(lines, 0, 0)
    if idx < len(lines):
        raise ValueError(f"unexpected trailing content at line {lines[idx][0]}")
    return value


def _preprocess(text: str) -> list[tuple[int, int, str]]:
    """Return (lineno, indent, content) skipping blanks and comments."""
    out: list[tuple[int, int, str]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        # strip inline comments outside quotes
        content = _strip_inline_comment(raw.rstrip())
        if not content.strip():
            continue
        indent = len(content) - len(content.lstrip(" "))
        if "\t" in content[:indent]:
            raise ValueError(f"tabs not allowed (line {lineno})")
        out.append((lineno, indent, content.strip()))
    return out


def _strip_inline_comment(line: str) -> str:
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if i == 0 or line[i - 1].isspace():
                return line[:i].rstrip()
    return line


def _parse_block(
    lines: list[tuple[int, int, str]], idx: int, indent: int
) -> tuple[Any, int]:
    if idx >= len(lines):
        return None, idx
    lineno, line_indent, content = lines[idx]
    if line_indent < indent:
        return None, idx
    if content.startswith("- "):
        return _parse_list(lines, idx, line_indent)
    if ":" in content:
        return _parse_mapping(lines, idx, line_indent)
    return _parse_scalar(content), idx + 1


def _parse_mapping(
    lines: list[tuple[int, int, str]], idx: int, indent: int
) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while idx < len(lines):
        lineno, line_indent, content = lines[idx]
        if line_indent < indent:
            break
        if line_indent > indent:
            raise ValueError(f"bad indent at line {lineno}")
        if content.startswith("- "):
            break
        if ":" not in content:
            raise ValueError(f"expected key: value at line {lineno}")
        key, _, rest = content.partition(":")
        key = key.strip()
        rest = rest.strip()
        idx += 1
        if rest:
            result[key] = _parse_scalar(rest)
            continue
        if idx >= len(lines) or lines[idx][1] <= indent:
            result[key] = None
            continue
        child_indent = lines[idx][1]
        if child_indent <= indent:
            result[key] = None
            continue
        value, idx = _parse_block(lines, idx, child_indent)
        result[key] = value
    return result, idx


def _parse_list(
    lines: list[tuple[int, int, str]], idx: int, indent: int
) -> tuple[list[Any], int]:
    result: list[Any] = []
    while idx < len(lines):
        lineno, line_indent, content = lines[idx]
        if line_indent != indent or not content.startswith("- "):
            break
        item_text = content[2:].strip()
        idx += 1
        if not item_text:
            if idx < len(lines) and lines[idx][1] > indent:
                value, idx = _parse_block(lines, idx, lines[idx][1])
                result.append(value)
            else:
                result.append(None)
            continue
        if item_text.startswith("- "):
            raise ValueError(f"nested list shorthand unsupported at line {lineno}")
        if ":" in item_text and not (
            item_text.startswith("'") or item_text.startswith('"')
        ):
            # inline mapping start: key: value, then possible nested keys
            key, _, rest = item_text.partition(":")
            mapping: dict[str, Any] = {key.strip(): _parse_scalar(rest.strip()) if rest.strip() else None}
            while idx < len(lines) and lines[idx][1] > indent and not lines[idx][2].startswith("- "):
                child_lineno, child_indent, child = lines[idx]
                if ":" not in child:
                    raise ValueError(f"expected key: value at line {child_lineno}")
                ck, _, cv = child.partition(":")
                ck = ck.strip()
                cv = cv.strip()
                idx += 1
                if cv:
                    mapping[ck] = _parse_scalar(cv)
                else:
                    if idx < len(lines) and lines[idx][1] > child_indent:
                        nested, idx = _parse_block(lines, idx, lines[idx][1])
                        mapping[ck] = nested
                    else:
                        mapping[ck] = None
            result.append(mapping)
            continue
        result.append(_parse_scalar(item_text))
    return result, idx


def _parse_scalar(text: str) -> Any:
    if text == "" or text in ("null", "~", "Null", "NULL"):
        return None
    if text in ("true", "True", "TRUE"):
        return True
    if text in ("false", "False", "FALSE"):
        return False
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        return text[1:-1]
    try:
        if any(c in text for c in ".eE") and _is_float(text):
            return float(text)
        return int(text)
    except ValueError:
        return text


def _is_float(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False
