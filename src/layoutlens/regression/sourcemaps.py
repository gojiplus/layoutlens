"""Decode CSS source locations using the ECMA-426 source map format."""

from __future__ import annotations

from urllib.parse import urljoin

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def _vlq(segment: str) -> list[int]:
    values, value, shift = [], 0, 0
    for character in segment:
        digit = _ALPHABET.index(character)
        value += (digit & 31) << shift
        if digit & 32:
            shift += 5
            if shift > 35:
                raise ValueError("source map VLQ is too large")
        else:
            values.append(-(value >> 1) if value & 1 else value >> 1)
            value, shift = 0, 0
    if shift:
        raise ValueError("truncated source map VLQ")
    return values


def original_position(
    source_map: dict, line: int, column: int, base_url: str
) -> dict | None:
    """Find a mapped location at or before a generated zero-based column.

    Args:
        source_map: Parsed version-three regular or indexed source map.
        line: Zero-based generated line.
        column: Zero-based generated column.
        base_url: Absolute map URL used to resolve relative source names.

    Returns:
        Original URL, one-based location, and optional original content.
    """
    if source_map.get("version") != 3 or line < 0 or column < 0:
        raise ValueError("invalid source map version or position")
    if "sections" in source_map:
        sections = source_map["sections"]
        eligible = [
            s
            for s in sections
            if (s["offset"]["line"], s["offset"]["column"]) <= (line, column)
        ]
        if not eligible:
            return None
        section = eligible[-1]
        if "map" not in section:
            raise ValueError("external indexed source map sections are unsupported")
        offset = section["offset"]
        return original_position(
            section["map"],
            line - offset["line"],
            column - offset["column"] if line == offset["line"] else column,
            base_url,
        )
    source_index, original_line, original_column = 0, 0, 0
    best = None
    for generated_line, segments in enumerate(source_map["mappings"].split(";")):
        if generated_line > line:
            break
        generated_column = 0
        for segment in segments.split(","):
            if not segment:
                continue
            values = _vlq(segment)
            if len(values) not in {1, 4, 5}:
                raise ValueError("invalid source map segment")
            generated_column += values[0]
            if len(values) == 1:
                if generated_line == line and generated_column <= column:
                    best = None
                continue
            source_index += values[1]
            original_line += values[2]
            original_column += values[3]
            if (
                source_index < 0
                or source_index >= len(source_map["sources"])
                or original_line < 0
                or original_column < 0
            ):
                raise ValueError("source map location is out of range")
            if generated_line == line and generated_column <= column:
                source_root = source_map.get("sourceRoot", "")
                source = source_map["sources"][source_index]
                url = urljoin(
                    urljoin(
                        base_url, source_root.rstrip("/") + "/" if source_root else ""
                    ),
                    source,
                )
                contents = source_map.get("sourcesContent") or []
                best = {
                    "url": url,
                    "line": original_line + 1,
                    "column": original_column + 1,
                    "source_content": contents[source_index]
                    if source_index < len(contents)
                    else None,
                }
    return best
