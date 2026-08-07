"""论文级Python绘图模板库。

本文件以导入的配对柱状图、分组柱状图、置信带折线图、局部放大图、
雷达图、断轴散点图、聚类散点图和数值热表脚本为基础重构。所有函数
只接收调用方传入的真实数据；不内置历年赛题、示例论文或模拟结果。
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.patches import ConnectionPatch, Rectangle


PALETTE = {
    "navy": "#173F5F",
    "blue": "#20639B",
    "teal": "#2A9D8F",
    "green": "#3D7A3A",
    "orange": "#E07A1F",
    "red": "#B33A3A",
    "purple": "#6C4A9B",
    "gray": "#727272",
    "light_gray": "#D9DEE7",
    "grid": "#D7DEE8",
    "ink": "#1F2933",
    "baseline": "#AFC6DC",
}


def resolve_chinese_font_fallback(preferred: str | None = "Microsoft YaHei") -> list[str]:
    """按优先顺序返回当前环境实际可用的中文与通用字体。"""

    installed = {entry.name.casefold() for entry in font_manager.fontManager.ttflist}
    candidates = [
        preferred,
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Arial",
        "DejaVu Sans",
    ]
    fallback: list[str] = []
    for candidate in candidates:
        if candidate and candidate.casefold() in installed and candidate not in fallback:
            fallback.append(candidate)

    # Matplotlib自带DejaVu Sans；保留它可避免极简运行环境中字体列表异常时失败。
    return fallback or ["DejaVu Sans"]


def apply_paper_style(font_size: float = 14, font_family: str | None = "Microsoft YaHei") -> None:
    """应用白底、深色文字和浅灰虚线网格的论文绘图基础风格。

    font_size应依据最终插入Word后的图幅在12—18pt之间设置；本函数不
    强制固定字号，也不启用外部LaTeX渲染，避免出现未渲染公式源码。
    """

    fallback = resolve_chinese_font_fallback(font_family)
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": fallback,
            "axes.unicode_minus": False,
            "text.usetex": False,
            "mathtext.fontset": "stix",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "axes.edgecolor": PALETTE["ink"],
            "axes.labelcolor": PALETTE["ink"],
            "xtick.color": PALETTE["ink"],
            "ytick.color": PALETTE["ink"],
            "font.size": font_size,
            "axes.labelsize": font_size,
            "xtick.labelsize": max(12, font_size - 2),
            "ytick.labelsize": max(12, font_size - 2),
            "legend.fontsize": max(12, font_size - 2),
            "axes.linewidth": 1.1,
            "lines.linewidth": 1.5,
            "hatch.linewidth": 0.55,
        }
    )


def save_paper_figure(
    fig: plt.Figure,
    output_path: str | Path,
    *,
    dpi: int = 400,
    pad_inches: float = 0.05,
) -> Path:
    """导出PNG并进行最小尺寸检查，不添加图内总标题。"""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if dpi < 300 or dpi > 600:
        raise ValueError("dpi应按最终版面在300—600之间选择。")
    fig.savefig(output, dpi=dpi, bbox_inches="tight", pad_inches=pad_inches, facecolor="white")
    width_px = int(fig.get_figwidth() * dpi)
    height_px = int(fig.get_figheight() * dpi)
    if min(width_px, height_px) < 1000:
        raise ValueError("导出尺寸过小；请增大图幅或dpi后再用于论文。")
    return output


def _validate_labels(values: np.ndarray, labels: Sequence[str], axis: int = 0) -> None:
    if values.shape[axis] != len(labels):
        raise ValueError("数据维度与标签数量不一致。")


def _finish_axes(ax: plt.Axes, *, grid: bool = True, open_spines: bool = False) -> None:
    """统一坐标轴、网格与留白；仅在需要时使用开口式坐标轴。"""

    ax.set_axisbelow(True)
    if grid:
        ax.yaxis.grid(True, color=PALETTE["grid"], linewidth=0.75, linestyle="--", zorder=0)
    else:
        ax.grid(False)
    for name, spine in ax.spines.items():
        spine.set_linewidth(1.1)
        spine.set_color(PALETTE["ink"])
        if open_spines and name in ("top", "right"):
            spine.set_visible(False)
    ax.tick_params(direction="out", length=4, width=0.9, pad=4)


def grouped_bar(
    categories: Sequence[str],
    values: Sequence[Sequence[float]],
    series_labels: Sequence[str],
    *,
    ylabel: str,
    focus_index: int | None = None,
    colors: Sequence[str] | None = None,
    annotate: bool = True,
    y_limits: tuple[float, float] | None = None,
    figsize: tuple[float, float] = (8.2, 4.8),
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制2—4组系列的分组柱状图。

    focus_index仅用于突出具有论证意义的系列；斜线填充细且稀疏，避免遮挡
    柱顶数值。精确数值差异很小时应改用paired_delta_bar或差值分布图。
    """

    apply_paper_style(font_size)
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("values必须为[系列数,类别数]的二维数组。")
    _validate_labels(matrix, series_labels, axis=0)
    _validate_labels(matrix, categories, axis=1)
    if not 2 <= matrix.shape[0] <= 4:
        raise ValueError("分组柱状图适用于2—4个系列；更多系列请拆图或改用表格。")

    colors = list(colors or [PALETTE["blue"], PALETTE["orange"], PALETTE["green"], PALETTE["purple"]])
    if len(colors) < matrix.shape[0]:
        raise ValueError("colors数量不足。")

    fig, ax = plt.subplots(figsize=figsize)
    x = np.arange(len(categories))
    width = min(0.76 / matrix.shape[0], 0.34)
    best = np.nanmax(matrix, axis=0)
    lower, upper = y_limits if y_limits else (0.0, max(1.0, float(np.nanmax(matrix)) * 1.16))

    for idx, row in enumerate(matrix):
        offset = (idx - (matrix.shape[0] - 1) / 2) * width
        hatch = "//" if idx == focus_index else ""
        bars = ax.bar(
            x + offset,
            row,
            width=width,
            label=series_labels[idx],
            color=colors[idx],
            edgecolor=PALETTE["ink"] if hatch else "white",
            linewidth=0.55 if hatch else 0.7,
            hatch=hatch,
            zorder=3,
        )
        if annotate:
            for bar, value, max_value in zip(bars, row, best):
                if np.isfinite(value):
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        value + (upper - lower) * 0.015,
                        f"{value:.2f}",
                        ha="center",
                        va="bottom",
                        fontsize=max(10, font_size - 3),
                        fontweight="bold" if np.isclose(value, max_value) else "normal",
                        color=PALETTE["ink"],
                        clip_on=False,
                    )

    ax.set_xticks(x, categories)
    ax.set_ylabel(ylabel)
    ax.set_ylim(lower, upper)
    _finish_axes(ax)
    ax.legend(frameon=True, facecolor="white", edgecolor="#B9C2CE", ncols=min(2, matrix.shape[0]))
    fig.tight_layout()
    return fig, ax


def paired_delta_bar(
    categories: Sequence[str],
    baseline: Sequence[float],
    candidate: Sequence[float],
    *,
    baseline_label: str,
    candidate_label: str,
    ylabel: str,
    relative_delta: bool = False,
    y_limits: tuple[float, float] | None = None,
    figsize: tuple[float, float] = (8.4, 4.9),
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制严格配对的基线—方案柱状比较并标注差值。"""

    apply_paper_style(font_size)
    base = np.asarray(baseline, dtype=float)
    cand = np.asarray(candidate, dtype=float)
    if len(categories) != len(base) or base.shape != cand.shape:
        raise ValueError("categories、baseline和candidate长度必须一致。")

    fig, ax = plt.subplots(figsize=figsize)
    x = np.arange(len(categories))
    width = 0.32
    data_max = float(np.nanmax(np.r_[base, cand]))
    if y_limits is None:
        lower, upper = 0.0, max(1.0, data_max * 1.20)
    else:
        lower, upper = y_limits
        if lower > 0:
            raise ValueError("柱状比较的纵轴默认必须从零起；如需局部放大，请改用折线或差值图。")

    ax.bar(x - width / 2, base, width, label=baseline_label, color=PALETTE["baseline"], edgecolor="white", linewidth=0.7, zorder=3)
    ax.bar(x + width / 2, cand, width, label=candidate_label, color=PALETTE["navy"], edgecolor="white", linewidth=0.7, zorder=3)
    scale = upper - lower
    for i, (v0, v1) in enumerate(zip(base, cand)):
        delta = ((v1 - v0) / abs(v0) * 100) if relative_delta and v0 != 0 else (v1 - v0)
        label = f"{delta:+.1f}%" if relative_delta else f"{delta:+.2f}"
        ax.plot([x[i] - width / 2, x[i] + width / 2], [v0, v0], color=PALETTE["ink"], lw=0.7, ls="--", zorder=4)
        ax.annotate(
            "",
            xy=(x[i] + width / 2, v1 - scale * 0.012),
            xytext=(x[i] + width / 2, v0 + scale * 0.012),
            arrowprops={"arrowstyle": "->", "color": PALETTE["red"], "lw": 1.1},
            zorder=5,
        )
        ax.text(x[i] + width / 2, max(v0, v1) + scale * 0.022, label, color=PALETTE["red"], ha="center", va="bottom", fontsize=max(10, font_size - 3), fontweight="bold")

    ax.set_xticks(x, categories)
    ax.set_ylabel(ylabel)
    ax.set_ylim(lower, upper)
    _finish_axes(ax)
    ax.legend(frameon=True, facecolor="white", edgecolor="#B9C2CE")
    fig.tight_layout()
    return fig, ax


def line_with_band(
    x: Sequence[float],
    series: Mapping[str, Sequence[float]],
    *,
    ylabel: str,
    xlabel: str,
    lower_band: Mapping[str, Sequence[float]] | None = None,
    upper_band: Mapping[str, Sequence[float]] | None = None,
    colors: Mapping[str, str] | None = None,
    reference_lines: Sequence[tuple[float, str, str]] | None = None,
    y_limits: tuple[float, float] | None = None,
    figsize: tuple[float, float] = (8.2, 4.8),
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制原始序列及其置信区间/预测区间。"""

    apply_paper_style(font_size)
    xv = np.asarray(x, dtype=float)
    if xv.ndim != 1 or xv.size < 2:
        raise ValueError("x必须至少包含两个数值。")
    if (lower_band is None) != (upper_band is None):
        raise ValueError("lower_band与upper_band必须同时提供或同时省略。")
    if lower_band is not None and set(lower_band) != set(series):
        raise ValueError("区间系列名称必须与series一致。")

    fallback_colors = [PALETTE["navy"], PALETTE["orange"], PALETTE["green"], PALETTE["purple"]]
    fig, ax = plt.subplots(figsize=figsize)
    for idx, (label, y) in enumerate(series.items()):
        yv = np.asarray(y, dtype=float)
        if yv.shape != xv.shape:
            raise ValueError(f"{label}与x长度不一致。")
        color = (colors or {}).get(label, fallback_colors[idx % len(fallback_colors)])
        if lower_band is not None:
            lo = np.asarray(lower_band[label], dtype=float)
            hi = np.asarray(upper_band[label], dtype=float)
            if lo.shape != xv.shape or hi.shape != xv.shape or np.any(lo > hi):
                raise ValueError(f"{label}的区间维度或上下界不合法。")
            ax.fill_between(xv, lo, hi, color=color, alpha=0.18, linewidth=0, zorder=1)
        ax.plot(xv, yv, color=color, label=label, zorder=3)

    for value, label, color in reference_lines or []:
        ax.axhline(value, color=color, lw=1.2, ls=(0, (2, 2)), label=label, zorder=2)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if y_limits:
        ax.set_ylim(*y_limits)
    _finish_axes(ax)
    ax.legend(frameon=True, facecolor="white", edgecolor="#B9C2CE")
    fig.tight_layout()
    return fig, ax


def line_with_inset(
    x: Sequence[float],
    series: Mapping[str, Sequence[float]],
    *,
    xlabel: str,
    ylabel: str,
    zoom_x: tuple[float, float],
    zoom_y: tuple[float, float],
    colors: Mapping[str, str] | None = None,
    inset_bounds: tuple[float, float, float, float] = (0.58, 0.48, 0.36, 0.36),
    figsize: tuple[float, float] = (8.8, 4.9),
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes, plt.Axes]:
    """绘制全量趋势与有来源标记的局部放大图。"""

    fig, ax = line_with_band(x, series, xlabel=xlabel, ylabel=ylabel, colors=colors, figsize=figsize, font_size=font_size)
    xv = np.asarray(x, dtype=float)
    inset = fig.add_axes(inset_bounds)
    fallback_colors = [PALETTE["navy"], PALETTE["orange"], PALETTE["green"], PALETTE["purple"]]
    for idx, (label, y) in enumerate(series.items()):
        color = (colors or {}).get(label, fallback_colors[idx % len(fallback_colors)])
        inset.plot(xv, np.asarray(y, dtype=float), color=color, lw=1.35, zorder=3)
    inset.set_xlim(*zoom_x)
    inset.set_ylim(*zoom_y)
    _finish_axes(inset, grid=False)
    inset.tick_params(labelsize=max(10, font_size - 4))

    rect = Rectangle((zoom_x[0], zoom_y[0]), zoom_x[1] - zoom_x[0], zoom_y[1] - zoom_y[0], fill=False, edgecolor=PALETTE["ink"], linestyle="--", linewidth=0.9, zorder=5)
    ax.add_patch(rect)
    for y in zoom_y:
        fig.add_artist(ConnectionPatch(xyA=(zoom_x[1], y), coordsA=ax.transData, xyB=(zoom_x[0], y), coordsB=inset.transData, color=PALETTE["gray"], lw=0.7, ls="--"))
    return fig, ax, inset


def radar_comparison(
    metric_labels: Sequence[str],
    values: Mapping[str, Sequence[float]],
    ranges: Sequence[tuple[float, float]],
    *,
    colors: Mapping[str, str] | None = None,
    directions: Sequence[int] | None = None,
    figsize: tuple[float, float] = (7.0, 6.2),
    font_size: float = 13,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制按明确范围归一化的少指标雷达图。"""

    apply_paper_style(font_size)
    n = len(metric_labels)
    if n < 3 or n > 8 or len(ranges) != n:
        raise ValueError("雷达图适用于3—8个指标，且每个指标必须给出归一化范围。")
    dirs = np.ones(n, dtype=float) if directions is None else np.asarray(directions, dtype=float)
    if dirs.shape != (n,) or not set(np.unique(dirs)).issubset({-1.0, 1.0}):
        raise ValueError("directions必须由1和-1组成。")

    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    angles_closed = np.r_[angles, angles[0]]
    fig, ax = plt.subplots(figsize=figsize, subplot_kw={"projection": "polar"})
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_frame_on(False)
    ax.set_ylim(0, 1.22)

    for radius in np.linspace(0.2, 1.0, 5):
        ax.plot(angles_closed, np.r_[np.full(n, radius), radius], color="#BEC7D1", lw=0.7, ls="--", zorder=1)
    for angle in angles:
        ax.plot([angle, angle], [0, 1], color="#BEC7D1", lw=0.7, ls="--", zorder=1)

    default_colors = [PALETTE["navy"], PALETTE["orange"], PALETTE["green"], PALETTE["purple"]]
    for idx, (name, raw) in enumerate(values.items()):
        array = np.asarray(raw, dtype=float)
        if array.shape != (n,):
            raise ValueError(f"{name}的指标数与metric_labels不一致。")
        normal = []
        for value, (low, high), direction in zip(array, ranges, dirs):
            if not high > low:
                raise ValueError("每个指标范围必须满足上界大于下界。")
            scaled = np.clip((value - low) / (high - low), 0, 1)
            normal.append(scaled if direction > 0 else 1 - scaled)
        normal = np.asarray(normal)
        color = (colors or {}).get(name, default_colors[idx % len(default_colors)])
        ax.fill(angles_closed, np.r_[normal, normal[0]], color=color, alpha=0.16, zorder=2)
        ax.plot(angles_closed, np.r_[normal, normal[0]], color=color, lw=2.0 if idx == 0 else 1.45, label=name, zorder=3)

    for angle, label in zip(angles, metric_labels):
        horizontal = "center" if abs(np.sin(angle)) < 0.2 else ("left" if np.sin(angle) > 0 else "right")
        ax.text(angle, 1.17, label, ha=horizontal, va="center", fontsize=max(10, font_size - 1), color=PALETTE["ink"])
    ax.legend(loc="upper left", bbox_to_anchor=(-0.08, 1.12), frameon=False)
    fig.tight_layout()
    return fig, ax


def broken_axis_scatter(
    left_series: Sequence[Mapping[str, object]],
    right_series: Sequence[Mapping[str, object]],
    *,
    x_left: tuple[float, float],
    x_right: tuple[float, float],
    y_limits: tuple[float, float],
    xlabel: str,
    ylabel: str,
    figsize: tuple[float, float] = (8.8, 4.8),
    font_size: float = 14,
) -> tuple[plt.Figure, tuple[plt.Axes, plt.Axes]]:
    """绘制具有真实结构性空档的断轴散点图。"""

    apply_paper_style(font_size)
    fig, (left, right) = plt.subplots(1, 2, figsize=figsize, sharey=True, gridspec_kw={"width_ratios": [4.5, 1.5], "wspace": 0.05})

    def draw(ax: plt.Axes, entries: Sequence[Mapping[str, object]]) -> None:
        for entry in entries:
            x = np.asarray(entry["x"], dtype=float)
            y = np.asarray(entry["y"], dtype=float)
            if x.shape != y.shape:
                raise ValueError("散点图每个系列的x与y长度必须一致。")
            color = str(entry.get("color", PALETTE["blue"]))
            marker = str(entry.get("marker", "o"))
            size = float(entry.get("size", 48))
            alpha = float(entry.get("alpha", 0.85))
            label = str(entry.get("label", ""))
            if bool(entry.get("line", False)):
                ax.plot(x, y, color=color, lw=1.25, zorder=2)
            ax.scatter(x, y, s=size, marker=marker, color=color, edgecolors="white", linewidths=0.45, alpha=alpha, label=label, zorder=3)

    draw(left, left_series)
    draw(right, right_series)
    left.set_xlim(*x_left)
    right.set_xlim(*x_right)
    left.set_ylim(*y_limits)
    left.set_xlabel(xlabel)
    left.set_ylabel(ylabel)
    _finish_axes(left)
    _finish_axes(right)
    right.set_yticks([])
    right.spines["left"].set_visible(False)
    left.spines["right"].set_visible(False)
    d = 0.014
    left.plot((1 - d, 1 + d), (-d, d), transform=left.transAxes, color=PALETTE["ink"], clip_on=False, lw=1.1)
    right.plot((-d, d), (-d, d), transform=right.transAxes, color=PALETTE["ink"], clip_on=False, lw=1.1)
    handles, labels = left.get_legend_handles_labels()
    handles_r, labels_r = right.get_legend_handles_labels()
    unique = dict(zip(labels + labels_r, handles + handles_r))
    left.legend(unique.values(), unique.keys(), loc="best", frameon=True, facecolor="white", edgecolor="#B9C2CE")
    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.16, top=0.96, wspace=0.05)
    return fig, (left, right)


def clustered_scatter(
    coordinates: Sequence[Sequence[float]],
    labels: Sequence[str | int],
    *,
    xlabel: str,
    ylabel: str,
    cluster_names: Mapping[str | int, str] | None = None,
    annotate_centers: bool = True,
    figsize: tuple[float, float] = (7.2, 5.7),
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制已计算二维坐标的类别/聚类散点图。"""

    apply_paper_style(font_size)
    points = np.asarray(coordinates, dtype=float)
    labels_array = np.asarray(labels)
    if points.ndim != 2 or points.shape[1] != 2 or points.shape[0] != labels_array.size:
        raise ValueError("coordinates必须为[n,2]，并与labels一一对应。")
    unique = list(dict.fromkeys(labels_array.tolist()))
    if len(unique) > 8:
        raise ValueError("类别超过8个时图例和颜色易失效；请聚合、拆图或使用其他图形。")
    colors = [PALETTE["navy"], PALETTE["orange"], PALETTE["green"], PALETTE["purple"], PALETTE["red"], PALETTE["teal"], PALETTE["gray"], "#7A5C3E"]
    fig, ax = plt.subplots(figsize=figsize)
    for idx, cls in enumerate(unique):
        mask = labels_array == cls
        name = (cluster_names or {}).get(cls, str(cls))
        ax.scatter(points[mask, 0], points[mask, 1], s=21, color=colors[idx], alpha=0.66, linewidths=0, label=name, rasterized=True, zorder=2)
        if annotate_centers and mask.sum() >= 3:
            center = np.nanmedian(points[mask], axis=0)
            ax.annotate(name, xy=center, ha="center", va="center", fontsize=max(10, font_size - 2), bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": colors[idx], "alpha": 0.9, "linewidth": 0.8}, zorder=4)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    _finish_axes(ax)
    ax.legend(frameon=True, facecolor="white", edgecolor="#B9C2CE", ncols=1)
    fig.tight_layout()
    return fig, ax


def heat_value_table(
    values: Sequence[Sequence[float]],
    row_labels: Sequence[str],
    column_labels: Sequence[str],
    *,
    higher_is_better: bool = True,
    cmap: str = "YlOrRd",
    figsize: tuple[float, float] | None = None,
    font_size: float = 13,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制适合附录或横向页面的数值热表。"""

    apply_paper_style(font_size)
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("values必须为二维数组。")
    _validate_labels(matrix, row_labels, axis=0)
    _validate_labels(matrix, column_labels, axis=1)
    figsize = figsize or (max(7.2, len(column_labels) * 0.62), max(2.8, len(row_labels) * 0.62 + 1.4))
    fig, ax = plt.subplots(figsize=figsize)
    image = ax.imshow(matrix if higher_is_better else -matrix, cmap=cmap, aspect="auto", interpolation="nearest")
    ax.set_xticks(np.arange(len(column_labels)), column_labels, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(row_labels)), row_labels)
    text_size = max(9, min(font_size - 2, 13))
    threshold = float(np.nanmedian(matrix))
    for r in range(matrix.shape[0]):
        for c in range(matrix.shape[1]):
            value = matrix[r, c]
            text_color = "white" if (value >= threshold) == higher_is_better else PALETTE["ink"]
            ax.text(c, r, f"{value:.2f}", ha="center", va="center", fontsize=text_size, color=text_color)
    colorbar = fig.colorbar(image, ax=ax, pad=0.02)
    colorbar.ax.tick_params(labelsize=max(10, font_size - 3))
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)
    fig.tight_layout()
    return fig, ax

# 从扩展模板模块重新导出，调用方始终只需从paper_plot_library导入。
from extended_templates import (
    annual_risk_trend,
    correlation_heatmap,
    diverging_bar,
    ecdf_risk_comparison,
    lollipop_ranking,
    observed_predicted_scatter,
    paired_difference_distribution,
    pareto_front,
    process_flowchart,
    residual_scatter,
    risk_boxplot,
    sensitivity_curve,
    sensitivity_tornado,
    spatial_bubble,
    stacked_composition_bar,
)