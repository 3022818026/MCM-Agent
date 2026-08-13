"""Pure geometry and validation for formal serpentine flowcharts."""

from __future__ import annotations

from math import ceil, isfinite
from typing import Mapping, Sequence


Point = tuple[float, float]
Segment = tuple[Point, Point, str]
Edge = tuple[str, str]


def display_label(label: str) -> str:
    """Keep node text to at most two compact lines."""

    lines = label.splitlines()
    if len(lines) > 2 or any(len(line) > 10 for line in lines):
        if len(lines) != 1 or len(label) > 20:
            raise ValueError("流程图节点文字应控制在两行内，每行不超过10个字符。")
        split_at = ceil(len(label) / 2)
        return f"{label[:split_at]}\n{label[split_at:]}"
    return label


def node_dimensions(display_labels: Mapping[str, str]) -> tuple[float, float]:
    longest_line = max(len(line) for text in display_labels.values() for line in text.splitlines())
    width = min(0.24, max(0.18, 0.09 + 0.014 * longest_line))
    height = 0.15 if any("\n" in text for text in display_labels.values()) else 0.12
    return width, height


def serpentine_positions(labels: Sequence[str]) -> dict[str, Point]:
    """Return aligned positions for a one-way three-column serpentine flow."""

    count = len(labels)
    if count <= 3:
        if count == 2:
            x_values = (0.3, 0.7)
        elif count == 3:
            x_values = (0.18, 0.5, 0.82)
        else:
            x_values = (0.5,)
        return {label: (x_values[index], 0.5) for index, label in enumerate(labels)}

    columns = 3
    rows = ceil(count / columns)
    x_values = (0.18, 0.5, 0.82)
    if rows == 1:
        y_values = (0.5,)
    else:
        y_values = tuple(0.82 - index * (0.64 / (rows - 1)) for index in range(rows))
    positions: dict[str, Point] = {}
    for index, label in enumerate(labels):
        row, slot = divmod(index, columns)
        column = slot if row % 2 == 0 else columns - 1 - slot
        positions[label] = (x_values[column], y_values[row])
    return positions


def _normalize_positions(labels: Sequence[str], positions: Mapping[str, Point]) -> dict[str, Point]:
    if set(positions) != set(labels):
        raise ValueError("positions必须恰好包含每个节点。")
    result: dict[str, Point] = {}
    for label, raw_position in positions.items():
        if len(raw_position) != 2:
            raise ValueError("每个positions坐标必须包含x和y两个数值。")
        x_value, y_value = float(raw_position[0]), float(raw_position[1])
        if not (isfinite(x_value) and isfinite(y_value)) or not (
            0.08 <= x_value <= 0.92 and 0.08 <= y_value <= 0.92
        ):
            raise ValueError("positions坐标必须为[0.08, 0.92]内的有限数值。")
        result[label] = (x_value, y_value)
    return result


def _segment(source: Point, target: Point, width: float, height: float) -> Segment:
    source_x, source_y = source
    target_x, target_y = target
    tolerance = 1e-9
    if abs(source_y - target_y) <= tolerance:
        direction = 1.0 if target_x > source_x else -1.0
        if abs(target_x - source_x) <= width + 0.02:
            raise ValueError("水平相邻节点间距不足，无法放置清晰箭头。")
        return (
            (source_x + direction * width / 2, source_y),
            (target_x - direction * width / 2, target_y),
            "horizontal",
        )
    if abs(source_x - target_x) <= tolerance:
        direction = 1.0 if target_y > source_y else -1.0
        if abs(target_y - source_y) <= height + 0.02:
            raise ValueError("垂直相邻节点间距不足，无法放置清晰箭头。")
        return (
            (source_x, source_y + direction * height / 2),
            (target_x, target_y - direction * height / 2),
            "vertical",
        )
    raise ValueError("显式positions必须使每条边水平或垂直对齐，以保证正交直线箭头。")


def _segment_hits_node(
    start: Point,
    end: Point,
    orientation: str,
    center: Point,
    width: float,
    height: float,
) -> bool:
    tolerance = 1e-9
    center_x, center_y = center
    if orientation == "horizontal":
        low, high = sorted((start[0], end[0]))
        return (
            center_y - height / 2 - tolerance <= start[1] <= center_y + height / 2 + tolerance
            and max(low, center_x - width / 2) < min(high, center_x + width / 2) - tolerance
        )
    low, high = sorted((start[1], end[1]))
    return (
        center_x - width / 2 - tolerance <= start[0] <= center_x + width / 2 + tolerance
        and max(low, center_y - height / 2) < min(high, center_y + height / 2) - tolerance
    )


def _segments_cross(first: Segment, second: Segment) -> bool:
    """Detect visible overlap or crossing between two axis-aligned arrow segments."""

    first_start, first_end, first_orientation = first
    second_start, second_end, second_orientation = second
    tolerance = 1e-9
    if first_orientation == second_orientation == "horizontal":
        if abs(first_start[1] - second_start[1]) > tolerance:
            return False
        first_low, first_high = sorted((first_start[0], first_end[0]))
        second_low, second_high = sorted((second_start[0], second_end[0]))
        return max(first_low, second_low) < min(first_high, second_high) - tolerance
    if first_orientation == second_orientation == "vertical":
        if abs(first_start[0] - second_start[0]) > tolerance:
            return False
        first_low, first_high = sorted((first_start[1], first_end[1]))
        second_low, second_high = sorted((second_start[1], second_end[1]))
        return max(first_low, second_low) < min(first_high, second_high) - tolerance

    horizontal = first if first_orientation == "horizontal" else second
    vertical = second if first_orientation == "horizontal" else first
    horizontal_low, horizontal_high = sorted((horizontal[0][0], horizontal[1][0]))
    vertical_low, vertical_high = sorted((vertical[0][1], vertical[1][1]))
    crossing_x = vertical[0][0]
    crossing_y = horizontal[0][1]
    return (
        horizontal_low - tolerance <= crossing_x <= horizontal_high + tolerance
        and vertical_low - tolerance <= crossing_y <= vertical_high + tolerance
    )


def prepare_layout(
    labels: Sequence[str],
    edges: Sequence[Edge],
    positions: Mapping[str, Point] | None,
    width: float,
    height: float,
) -> tuple[dict[str, Point], int, list[Segment]]:
    """Validate a flow and return positions, row count, and safe straight segments."""

    edge_list = list(edges)
    if not edge_list or len(set(edge_list)) != len(edge_list):
        raise ValueError("edges必须包含不重复的流程连接。")
    for source, target in edge_list:
        if source not in labels or target not in labels:
            raise ValueError("每条边的端点都必须属于nodes。")
        if source == target:
            raise ValueError("不支持节点到自身的回路箭头。")

    if positions is None:
        expected_edges = list(zip(labels, labels[1:]))
        if edge_list != expected_edges:
            raise ValueError("默认蛇形布局只接受按nodes顺序连接的线性流程；分支或回路请显式提供positions。")
        position_map = serpentine_positions(labels)
        row_count = 1 if len(labels) <= 3 else ceil(len(labels) / 3)
    else:
        position_map = _normalize_positions(labels, positions)
        row_count = len({round(value[1], 6) for value in position_map.values()})

    segments: list[Segment] = []
    for source, target in edge_list:
        candidate = _segment(position_map[source], position_map[target], width, height)
        for label, center in position_map.items():
            if label not in (source, target) and _segment_hits_node(*candidate, center, width, height):
                raise ValueError(f"箭头{source!r}→{target!r}穿过节点{label!r}；请调整positions。")
        if any(_segments_cross(candidate, existing) for existing in segments):
            raise ValueError(f"箭头{source!r}→{target!r}与已有箭头交叉或重叠；请调整positions。")
        segments.append(candidate)
    return position_map, row_count, segments
