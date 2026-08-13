"""扩展论文图表模板。

全部函数只接收调用方提供的已核验数据。图内不放长标题，正式图号和图题
由Word图下注释提供。字体大小应依据最终插入尺寸在12—18pt之间传入。
"""

from __future__ import annotations

from math import ceil, comb, erf, sqrt
from typing import Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, Rectangle

try:
    from .flowchart_geometry import display_label, node_dimensions, prepare_layout
except ImportError:  # 支持将本目录直接加入sys.path后导入。
    from flowchart_geometry import display_label, node_dimensions, prepare_layout

try:
    from .paper_plot_library import PALETTE, _finish_axes, apply_paper_style
except ImportError:  # 支持将本目录直接加入sys.path后导入。
    from paper_plot_library import PALETTE, _finish_axes, apply_paper_style


def _finite_vector(values: Sequence[float], name: str) -> np.ndarray:
    result = np.asarray(values, dtype=float).reshape(-1)
    result = result[np.isfinite(result)]
    if result.size == 0:
        raise ValueError(f"{name}不包含有效数值。")
    return result


def _ecdf(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x_values = np.sort(values)
    y_values = np.arange(1, x_values.size + 1) / x_values.size
    return x_values, y_values


def paired_difference_stats(
    diff_array: Sequence[float] | np.ndarray,
    *,
    n_bootstrap: int = 10_000,
    confidence: float = 0.95,
    random_seed: int = 2026,
) -> dict[str, float | int | str]:
    """计算逐对差值的均值、Bootstrap区间、胜率和双侧符号检验。

    ``diff_array``应按“候选方案−基线方案”定义；正值因此表示候选方案
    在该配对上更优。零差值不计入符号检验，但保留在均值和胜率分母中。
    """

    differences = np.asarray(diff_array, dtype=float).reshape(-1)
    if differences.size < 2:
        raise ValueError("配对差值至少需要两个观测。")
    if not np.isfinite(differences).all():
        raise ValueError("配对差值不能包含缺失值或无穷值；请先完成数据清洗。")
    if n_bootstrap < 1_000:
        raise ValueError("n_bootstrap至少为1000，才能提供稳定的区间估计。")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence必须在0和1之间。")

    n_pairs = differences.size
    rng = np.random.default_rng(random_seed)
    bootstrap_means = np.empty(n_bootstrap, dtype=float)
    batch_size = max(1, min(n_bootstrap, 1_000_000 // n_pairs))
    for start in range(0, n_bootstrap, batch_size):
        stop = min(n_bootstrap, start + batch_size)
        sampled = rng.integers(0, n_pairs, size=(stop - start, n_pairs))
        bootstrap_means[start:stop] = differences[sampled].mean(axis=1)

    alpha = (1.0 - confidence) / 2.0
    ci_lower, ci_upper = np.quantile(bootstrap_means, [alpha, 1.0 - alpha])
    positive_count = int(np.count_nonzero(differences > 0))
    negative_count = int(np.count_nonzero(differences < 0))
    tie_count = int(n_pairs - positive_count - negative_count)
    nonzero_count = positive_count + negative_count
    if nonzero_count == 0:
        sign_pvalue, sign_method = 1.0, "all_ties"
    elif nonzero_count <= 10_000:
        lower_tail = min(positive_count, negative_count)
        tail_probability = sum(comb(nonzero_count, k) for k in range(lower_tail + 1)) / (1 << nonzero_count)
        sign_pvalue, sign_method = min(1.0, 2.0 * tail_probability), "exact_binomial"
    else:
        z_value = max(0.0, abs(positive_count - nonzero_count / 2.0) - 0.5) / sqrt(nonzero_count / 4.0)
        sign_pvalue, sign_method = 1.0 - erf(z_value / sqrt(2.0)), "normal_approximation"

    return {
        "n_pairs": int(n_pairs),
        "mean_difference": float(differences.mean()),
        "ci_lower": float(ci_lower),
        "ci_upper": float(ci_upper),
        "confidence_level": float(confidence),
        "ci_method": "paired_bootstrap_percentile",
        "bootstrap_resamples": int(n_bootstrap),
        "win_rate": float(positive_count / n_pairs),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "tie_count": tie_count,
        "sign_test_pvalue": float(sign_pvalue),
        "sign_test_method": sign_method,
    }

def stacked_composition_bar(
    scenarios: Sequence[str],
    categories: Sequence[str],
    values: Sequence[Sequence[float]],
    *,
    ylabel: str,
    normalize: bool = False,
    colors: Sequence[str] | None = None,
    hatches: Sequence[str] | None = None,
    share_label_threshold: float = 0.05,
    show_totals: bool = True,
    figsize: tuple[float, float] = (8.0, 5.1),
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制方案或时期的组成结构堆叠柱状图。

    values的形状为[方案数,类别数]。normalize为True时显示100%组成，原始
    总量仍可在外部表格保留；不要把绝对结构与百分比结构混在同一张图中。
    """

    apply_paper_style(font_size)
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim != 2 or matrix.shape != (len(scenarios), len(categories)):
        raise ValueError("values必须为[方案数,类别数]，并与scenarios和categories匹配。")
    if np.any(matrix < 0):
        raise ValueError("组成结构不能含负数；含正负效应时应使用diverging_bar。")
    totals = matrix.sum(axis=1)
    if np.any(totals <= 0):
        raise ValueError("每个方案的组成总量必须为正。")

    display = matrix / totals[:, None] * 100 if normalize else matrix
    colors = list(colors or [PALETTE["navy"], PALETTE["teal"], PALETTE["orange"], PALETTE["purple"], "#8A6D3B", PALETTE["red"]])
    hatches = list(hatches or ["", "//", "", "..", "", "\\\\"])
    if len(colors) < len(categories) or len(hatches) < len(categories):
        raise ValueError("colors和hatches的长度不得小于类别数。")

    fig, ax = plt.subplots(figsize=figsize)
    positions = np.arange(len(scenarios))
    bottoms = np.zeros(len(scenarios))
    for idx, category in enumerate(categories):
        heights = display[:, idx]
        bars = ax.bar(
            positions,
            heights,
            bottom=bottoms,
            width=0.58,
            color=colors[idx],
            edgecolor=PALETTE["ink"],
            linewidth=0.55,
            hatch=hatches[idx],
            label=category,
            zorder=3,
        )
        shares = matrix[:, idx] / totals
        for scenario_idx, bar in enumerate(bars):
            if shares[scenario_idx] >= share_label_threshold:
                label = f"{shares[scenario_idx] * 100:.1f}%"
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bottoms[scenario_idx] + heights[scenario_idx] / 2,
                    label,
                    ha="center",
                    va="center",
                    fontsize=max(10, font_size - 4),
                    color=PALETTE["ink"],
                    bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.66, "pad": 0.8},
                    zorder=4,
                )
        bottoms += heights

    ax.set_xticks(positions, scenarios)
    ax.set_ylabel("构成比例（%）" if normalize else ylabel)
    if normalize:
        ax.set_ylim(0, 100)
    else:
        ax.set_ylim(0, float(totals.max()) * 1.16)
        if show_totals:
            for position, total in zip(positions, totals):
                ax.text(
                    position,
                    total + float(totals.max()) * 0.018,
                    f"{total:.2f}",
                    ha="center",
                    va="bottom",
                    fontsize=max(10, font_size - 3),
                    color=PALETTE["ink"],
                )
    _finish_axes(ax, open_spines=True)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.16),
        ncols=min(3, len(categories)),
        frameon=False,
        handlelength=1.7,
        columnspacing=1.0,
    )
    fig.tight_layout()
    return fig, ax


def annual_risk_trend(
    periods: Sequence[float | str],
    scenario_values: Sequence[Sequence[float]],
    *,
    xlabel: str,
    ylabel: str,
    interval: tuple[float, float] = (0.05, 0.95),
    show_median: bool = True,
    annotate_mean: bool = False,
    figsize: tuple[float, float] = (8.8, 5.0),
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes]:
    """从逐情景、逐时期的真实结果绘制均值、中位数和风险区间。

    scenario_values形状为[情景数,时期数]。区间必须来自真实情景、重复试验或
    bootstrap结果，不得仅为装饰给折线添加阴影。
    """

    apply_paper_style(font_size)
    values = np.asarray(scenario_values, dtype=float)
    if values.ndim != 2 or values.shape[1] != len(periods) or values.shape[0] < 2:
        raise ValueError("scenario_values必须为至少两条情景的[情景数,时期数]数组。")
    low_q, high_q = interval
    if not 0 <= low_q < high_q <= 1:
        raise ValueError("interval必须满足0≤下分位<上分位≤1。")
    means = np.nanmean(values, axis=0)
    medians = np.nanquantile(values, 0.5, axis=0)
    lows = np.nanquantile(values, low_q, axis=0)
    highs = np.nanquantile(values, high_q, axis=0)
    x = np.arange(len(periods))

    fig, ax = plt.subplots(figsize=figsize)
    ax.fill_between(x, lows, highs, color=PALETTE["blue"], alpha=0.22, label=f"{int((high_q - low_q) * 100)}%收益区间", zorder=1)
    ax.plot(x, means, color=PALETTE["navy"], marker="o", markersize=5.8, markerfacecolor="white", markeredgewidth=1.25, label="平均值", zorder=3)
    if show_median:
        ax.plot(x, medians, color=PALETTE["orange"], linestyle="--", marker="s", markersize=4.6, label="中位数", zorder=3)
    if annotate_mean:
        span = max(float(np.nanmax(highs) - np.nanmin(lows)), 1.0)
        for xp, value in zip(x, means):
            ax.text(
                xp,
                value + span * 0.024,
                f"{value:.2f}",
                ha="center",
                va="bottom",
                fontsize=max(10, font_size - 4),
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.72, "pad": 0.7},
            )
    span = max(float(np.nanmax(highs) - np.nanmin(lows)), 1.0)
    ax.set_ylim(float(np.nanmin(lows) - span * 0.10), float(np.nanmax(highs) + span * 0.16))
    ax.set_xticks(x, periods)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    _finish_axes(ax, open_spines=True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.04), ncols=3, frameon=False)
    fig.tight_layout()
    return fig, ax


def risk_boxplot(
    samples: Mapping[str, Sequence[float]],
    *,
    ylabel: str,
    tail_quantile: float = 0.05,
    show_points: bool = True,
    random_seed: int = 42,
    figsize: tuple[float, float] = (7.8, 5.2),
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制少量方案的样本外收益或误差分布箱线图。

    箱体范围采用5%—95%分位，菱形表示均值，三角表示tail_quantile。原始点
    仅作半透明抖动辅助，不以删除离群点获得更规整的视觉效果。
    """

    apply_paper_style(font_size)
    labels = list(samples)
    if not 2 <= len(labels) <= 6:
        raise ValueError("风险箱线图适用于2—6个方案；更多方案请拆图或筛选。")
    arrays = [_finite_vector(samples[label], label) for label in labels]
    if not 0 < tail_quantile < 0.5:
        raise ValueError("tail_quantile必须位于0与0.5之间。")
    colors = [PALETTE["navy"], PALETTE["orange"], PALETTE["teal"], PALETTE["purple"], PALETTE["green"], PALETTE["red"]]
    fig, ax = plt.subplots(figsize=figsize)
    box = ax.boxplot(
        arrays,
        positions=np.arange(len(labels)),
        widths=0.50,
        patch_artist=True,
        showmeans=True,
        showfliers=True,
        whis=(5, 95),
        medianprops={"color": PALETTE["ink"], "linewidth": 1.6},
        meanprops={"marker": "D", "markerfacecolor": "white", "markeredgecolor": PALETTE["ink"], "markersize": 6},
        whiskerprops={"color": PALETTE["ink"], "linewidth": 1.0},
        capprops={"color": PALETTE["ink"], "linewidth": 1.0},
        flierprops={"marker": "o", "markersize": 2.8, "markerfacecolor": PALETTE["gray"], "markeredgecolor": "none", "alpha": 0.35},
    )
    for patch, color, hatch in zip(box["boxes"], colors, ["", "//", "", "..", "", "\\\\"]):
        patch.set_facecolor(color)
        patch.set_edgecolor(PALETTE["ink"])
        patch.set_linewidth(0.7)
        patch.set_alpha(0.78)
        patch.set_hatch(hatch)

    rng = np.random.default_rng(random_seed)
    all_values = np.concatenate(arrays)
    span = max(float(np.nanmax(all_values) - np.nanmin(all_values)), 1.0)
    for idx, values in enumerate(arrays):
        if show_points:
            jitter = rng.uniform(-0.12, 0.12, size=values.size)
            ax.scatter(np.full(values.size, idx) + jitter, values, s=10, color=PALETTE["ink"], alpha=0.12, linewidths=0, zorder=2)
        p_tail = float(np.quantile(values, tail_quantile))
        mean = float(np.mean(values))
        ax.scatter(idx, p_tail, marker="^", s=42, color=PALETTE["red"], edgecolors="white", linewidths=0.55, zorder=5)
        ax.text(
            idx + 0.17,
            mean,
            f"均值{mean:.2f}\n{int(tail_quantile * 100)}%分位{p_tail:.2f}",
            fontsize=max(9, font_size - 5),
            ha="left",
            va="center",
            color=PALETTE["ink"],
            bbox={"facecolor": "white", "edgecolor": PALETTE["grid"], "linewidth": 0.55, "alpha": 0.92, "pad": 1.2},
        )
    ax.set_xticks(np.arange(len(labels)), labels)
    ax.set_ylabel(ylabel)
    ax.set_ylim(float(np.nanmin(all_values) - span * 0.10), float(np.nanmax(all_values) + span * 0.14))
    _finish_axes(ax, open_spines=True)
    ax.scatter([], [], marker="D", s=36, facecolors="white", edgecolors=PALETTE["ink"], label="均值")
    ax.scatter([], [], marker="^", s=42, color=PALETTE["red"], label=f"{int(tail_quantile * 100)}%分位")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.04), ncols=2, frameon=False)
    fig.tight_layout()
    return fig, ax


def ecdf_risk_comparison(
    samples: Mapping[str, Sequence[float]],
    *,
    xlabel: str,
    tail_probability: float = 0.10,
    quantile: float = 0.05,
    colors: Mapping[str, str] | None = None,
    figsize: tuple[float, float] = (8.3, 4.9),
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制样本外结果的经验累积分布和下侧风险区域。

    当ECDF曲线接近重合时，此图不能单独作为优劣证据，必须配合
    paired_difference_distribution、配对散点或数值置信区间。
    """

    apply_paper_style(font_size)
    if not 0 < quantile <= tail_probability < 0.5:
        raise ValueError("应满足0<quantile≤tail_probability<0.5。")
    labels = list(samples)
    if not 2 <= len(labels) <= 5:
        raise ValueError("ECDF比较适用于2—5个方案。")
    arrays = {label: _finite_vector(values, label) for label, values in samples.items()}
    default_colors = [PALETTE["navy"], PALETTE["orange"], PALETTE["teal"], PALETTE["purple"], PALETTE["red"]]
    fig, ax = plt.subplots(figsize=figsize)
    quantiles: dict[str, float] = {}
    for idx, label in enumerate(labels):
        x_values, y_values = _ecdf(arrays[label])
        color = (colors or {}).get(label, default_colors[idx])
        ax.step(x_values, y_values, where="post", color=color, lw=1.9, label=label, zorder=3)
        q_value = float(np.quantile(arrays[label], quantile))
        quantiles[label] = q_value
        ax.axvline(q_value, color=color, linestyle=(0, (2, 2)), linewidth=0.95, alpha=0.85, zorder=2)
    ax.axhspan(0, tail_probability, color=PALETTE["gray"], alpha=0.08, zorder=0)
    information = [f"{int(quantile * 100)}%分位值"]
    information.extend(f"{label}：{value:.2f}" for label, value in quantiles.items())
    ax.text(
        0.025,
        0.965,
        "\n".join(information),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=max(10, font_size - 4),
        color=PALETTE["ink"],
        bbox={"facecolor": "white", "edgecolor": "#C7CDD6", "linewidth": 0.65, "alpha": 0.95, "pad": 3.0},
    )
    ax.set_xlabel(xlabel)
    ax.set_ylabel("累计概率")
    ax.set_ylim(0, 1)
    _finish_axes(ax, grid=True, open_spines=True)
    ax.legend(loc="lower right", frameon=False)
    fig.tight_layout()
    return fig, ax


def correlation_heatmap(
    matrix: Sequence[Sequence[float]],
    labels: Sequence[str],
    *,
    colorbar_label: str = "相关系数",
    require_symmetric: bool = True,
    value_range: tuple[float, float] = (-1.0, 1.0),
    figsize: tuple[float, float] = (6.6, 5.6),
    font_size: float = 13,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制带数值标注的相关矩阵或判断矩阵。

    对相关矩阵默认要求对称。若展示非对称关系，应设require_symmetric=False，
    并在正文说明行列方向和数值含义。
    """

    apply_paper_style(font_size)
    values = np.asarray(matrix, dtype=float)
    if values.ndim != 2 or values.shape[0] != values.shape[1] or values.shape[0] != len(labels):
        raise ValueError("matrix必须为与labels数量一致的方阵。")
    if require_symmetric and not np.allclose(values, values.T, equal_nan=True, atol=1e-8):
        raise ValueError("相关矩阵应对称；非对称关系请显式关闭require_symmetric。")
    low, high = value_range
    if not low < 0 < high:
        raise ValueError("相关矩阵色标应围绕零点设置正负范围。")
    if np.nanmin(values) < low - 1e-8 or np.nanmax(values) > high + 1e-8:
        raise ValueError("matrix超出设定色标范围；请核对单位或显式调整value_range。")

    fig, ax = plt.subplots(figsize=figsize)
    norm = TwoSlopeNorm(vmin=low, vcenter=0.0, vmax=high)
    image = ax.imshow(values, cmap="RdBu_r", norm=norm, interpolation="nearest", aspect="equal")
    ax.set_xticks(np.arange(len(labels)), labels, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(labels)), labels)
    for row in range(values.shape[0]):
        for column in range(values.shape[1]):
            value = values[row, column]
            if not np.isfinite(value):
                text = "NA"
                color = PALETTE["ink"]
            else:
                text = f"{value:.2f}"
                color = "white" if abs(value) >= 0.55 * max(abs(low), abs(high)) else PALETTE["ink"]
            ax.text(column, row, text, ha="center", va="center", fontsize=max(10, font_size - 2), color=color)
    colorbar = fig.colorbar(image, ax=ax, fraction=0.048, pad=0.04)
    colorbar.set_label(colorbar_label)
    colorbar.ax.tick_params(labelsize=max(10, font_size - 3))
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)
    fig.tight_layout()
    return fig, ax


def diverging_bar(
    labels: Sequence[str],
    values: Sequence[float],
    *,
    xlabel: str,
    sort_by_magnitude: bool = True,
    positive_color: str = PALETTE["orange"],
    negative_color: str = PALETTE["navy"],
    figsize: tuple[float, float] | None = None,
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制以零为中心的正负关系、影响或变化率条形图。"""

    apply_paper_style(font_size)
    names = list(labels)
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size != len(names):
        raise ValueError("labels与values必须是一一对应的一维序列。")
    order = np.argsort(np.abs(array)) if sort_by_magnitude else np.arange(array.size)
    names = [names[idx] for idx in order]
    array = array[order]
    figsize = figsize or (8.2, max(3.8, 0.55 * len(names) + 1.5))

    fig, ax = plt.subplots(figsize=figsize)
    positions = np.arange(array.size)
    colors = [positive_color if value >= 0 else negative_color for value in array]
    bars = ax.barh(positions, array, color=colors, edgecolor=PALETTE["ink"], linewidth=0.55, height=0.60, zorder=3)
    maximum = max(float(np.nanmax(np.abs(array))), 1e-10)
    ax.axvline(0, color=PALETTE["ink"], linewidth=1.0, zorder=4)
    ax.set_xlim(-maximum * 1.30, maximum * 1.30)
    for bar, value in zip(bars, array):
        ax.text(
            value + np.sign(value if value != 0 else 1) * maximum * 0.035,
            bar.get_y() + bar.get_height() / 2,
            f"{value:+.2f}",
            ha="left" if value >= 0 else "right",
            va="center",
            fontsize=max(10, font_size - 3),
            color=PALETTE["ink"],
        )
    ax.set_yticks(positions, names)
    ax.set_xlabel(xlabel)
    ax.invert_yaxis()
    ax.xaxis.grid(True, color=PALETTE["grid"], linewidth=0.75, linestyle="--", zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout()
    return fig, ax


def paired_difference_distribution(
    baseline: Sequence[float],
    candidate: Sequence[float],
    *,
    xlabel: str,
    baseline_label: str = "基线",
    candidate_label: str = "方案",
    relative: bool = False,
    bootstrap_reps: int = 3000,
    random_seed: int = 42,
    figsize: tuple[float, float] = (8.1, 3.9),
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制同一批对象上的逐样本差值分布。

    差值定义为方案减基线。它是两条结果曲线接近重合时的优先替代图，可显示
    真实的平均改变量、胜率和均值bootstrap区间，不能用来替代独立样本比较。
    """

    apply_paper_style(font_size)
    base = np.asarray(baseline, dtype=float)
    cand = np.asarray(candidate, dtype=float)
    if base.shape != cand.shape or base.ndim != 1:
        raise ValueError("baseline与candidate必须为长度一致的一维配对数据。")
    valid = np.isfinite(base) & np.isfinite(cand)
    base, cand = base[valid], cand[valid]
    if base.size < 3:
        raise ValueError("配对差分至少需要3个有效对象。")
    if relative:
        if np.any(base == 0):
            raise ValueError("基线含零值，不能计算相对差分。")
        differences = (cand - base) / np.abs(base) * 100
        difference_label = f"{candidate_label}相对{baseline_label}的变化率（%）"
    else:
        differences = cand - base
        difference_label = f"{candidate_label} - {baseline_label}"
    rng = np.random.default_rng(random_seed)
    if bootstrap_reps < 200:
        raise ValueError("bootstrap_reps至少为200。")
    sampled = rng.choice(differences, size=(bootstrap_reps, differences.size), replace=True)
    boot_means = sampled.mean(axis=1)
    ci_low, ci_high = np.quantile(boot_means, [0.025, 0.975])
    mean_value = float(np.mean(differences))
    median_value = float(np.median(differences))
    win_rate = float(np.mean(differences > 0))

    fig, ax = plt.subplots(figsize=figsize)
    violin = ax.violinplot(differences, positions=[1], vert=False, widths=0.56, showmeans=False, showmedians=False, showextrema=False)
    for body in violin["bodies"]:
        body.set_facecolor(PALETTE["blue"])
        body.set_edgecolor(PALETTE["ink"])
        body.set_alpha(0.28)
        body.set_linewidth(0.8)
    box = ax.boxplot(
        differences,
        positions=[1],
        vert=False,
        widths=0.18,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": PALETTE["ink"], "linewidth": 1.5},
        boxprops={"facecolor": "white", "edgecolor": PALETTE["ink"], "linewidth": 0.9},
        whiskerprops={"color": PALETTE["ink"], "linewidth": 0.9},
        capprops={"color": PALETTE["ink"], "linewidth": 0.9},
    )
    del box
    jitter = rng.uniform(-0.12, 0.12, size=differences.size)
    ax.scatter(differences, 1 + jitter, s=16, color=PALETTE["navy"], alpha=0.46, edgecolors="white", linewidths=0.25, zorder=4)
    ax.axvline(0, color=PALETTE["red"], linewidth=1.1, linestyle="--", zorder=2)
    span = max(float(np.max(differences) - np.min(differences)), 1e-8)
    ax.scatter(mean_value, 1, marker="D", s=48, facecolors="white", edgecolors=PALETTE["ink"], linewidths=1.0, zorder=5)
    info = "\n".join(
        [
            f"均值：{mean_value:.3f}",
            f"中位数：{median_value:.3f}",
            f"胜率：{win_rate * 100:.1f}%",
            f"均值95%CI：[{ci_low:.3f}, {ci_high:.3f}]",
        ]
    )
    ax.text(
        0.98,
        0.95,
        info,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=max(9, font_size - 5),
        color=PALETTE["ink"],
        bbox={"facecolor": "white", "edgecolor": PALETTE["grid"], "linewidth": 0.6, "alpha": 0.94, "pad": 2.5},
    )
    ax.set_yticks([])
    ax.set_ylim(0.55, 1.45)
    ax.set_xlabel(xlabel or difference_label)
    ax.xaxis.grid(True, color=PALETTE["grid"], linewidth=0.75, linestyle="--", zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    return fig, ax


def observed_predicted_scatter(
    observed: Sequence[float],
    predicted: Sequence[float],
    *,
    xlabel: str,
    ylabel: str,
    groups: Sequence[str | int] | None = None,
    group_names: Mapping[str | int, str] | None = None,
    figsize: tuple[float, float] = (6.3, 5.6),
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制观测值—预测值散点图与y=x参考线。"""

    apply_paper_style(font_size)
    y_true = np.asarray(observed, dtype=float)
    y_pred = np.asarray(predicted, dtype=float)
    if y_true.shape != y_pred.shape or y_true.ndim != 1:
        raise ValueError("observed与predicted必须为等长一维数组。")
    valid = np.isfinite(y_true) & np.isfinite(y_pred)
    y_true, y_pred = y_true[valid], y_pred[valid]
    if y_true.size < 3:
        raise ValueError("至少需要3个有效观测与预测点。")
    if groups is not None:
        group_array = np.asarray(groups)[valid]
        unique = list(dict.fromkeys(group_array.tolist()))
        if len(unique) > 6:
            raise ValueError("类别超过6个时图例会失去可读性；请聚合或拆图。")
    else:
        group_array, unique = None, []

    minimum = float(min(np.min(y_true), np.min(y_pred)))
    maximum = float(max(np.max(y_true), np.max(y_pred)))
    span = max(maximum - minimum, 1e-8)
    lower, upper = minimum - span * 0.05, maximum + span * 0.05
    rmse = float(np.sqrt(np.mean((y_pred - y_true) ** 2)))
    denom = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = 1 - float(np.sum((y_pred - y_true) ** 2)) / denom if denom > 0 else np.nan

    fig, ax = plt.subplots(figsize=figsize)
    if group_array is None:
        ax.scatter(y_true, y_pred, s=30, color=PALETTE["blue"], alpha=0.70, edgecolors="white", linewidths=0.35, zorder=3)
    else:
        palette = [PALETTE["navy"], PALETTE["orange"], PALETTE["teal"], PALETTE["purple"], PALETTE["green"], PALETTE["red"]]
        for idx, group in enumerate(unique):
            mask = group_array == group
            name = (group_names or {}).get(group, str(group))
            ax.scatter(y_true[mask], y_pred[mask], s=30, color=palette[idx], alpha=0.70, edgecolors="white", linewidths=0.35, label=name, zorder=3)
    ax.plot([lower, upper], [lower, upper], color=PALETTE["red"], linestyle="--", linewidth=1.2, label="y=x", zorder=2)
    ax.set_xlim(lower, upper)
    ax.set_ylim(lower, upper)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    _finish_axes(ax, open_spines=True)
    ax.text(
        0.03,
        0.97,
        f"n={y_true.size}\nRMSE={rmse:.3f}\nR²={r2:.3f}",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=max(10, font_size - 3),
        bbox={"facecolor": "white", "edgecolor": PALETTE["grid"], "linewidth": 0.6, "alpha": 0.94, "pad": 2.4},
    )
    if group_array is not None:
        ax.legend(loc="lower right", frameon=True, facecolor="white", edgecolor="#B9C2CE")
    fig.tight_layout()
    return fig, ax


def residual_scatter(
    fitted: Sequence[float],
    residuals: Sequence[float],
    *,
    xlabel: str = "拟合值",
    ylabel: str = "残差",
    figsize: tuple[float, float] = (7.0, 4.8),
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制拟合值—残差图，检查系统性偏差和异方差。"""

    apply_paper_style(font_size)
    x_values = np.asarray(fitted, dtype=float)
    y_values = np.asarray(residuals, dtype=float)
    if x_values.shape != y_values.shape or x_values.ndim != 1:
        raise ValueError("fitted与residuals必须为等长一维数组。")
    valid = np.isfinite(x_values) & np.isfinite(y_values)
    x_values, y_values = x_values[valid], y_values[valid]
    if x_values.size < 3:
        raise ValueError("残差图至少需要3个有效点。")
    spread = max(float(np.max(np.abs(y_values))), 1e-8)
    fig, ax = plt.subplots(figsize=figsize)
    ax.scatter(x_values, y_values, s=27, color=PALETTE["blue"], alpha=0.68, edgecolors="white", linewidths=0.35, zorder=3)
    ax.axhline(0, color=PALETTE["red"], linestyle="--", linewidth=1.15, zorder=2)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_ylim(-spread * 1.15, spread * 1.15)
    _finish_axes(ax, open_spines=True)
    fig.tight_layout()
    return fig, ax


def sensitivity_tornado(
    parameter_labels: Sequence[str],
    lower_effects: Sequence[float],
    upper_effects: Sequence[float],
    *,
    xlabel: str,
    lower_label: str = "低取值",
    upper_label: str = "高取值",
    figsize: tuple[float, float] | None = None,
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制参数低、高取值相对基准方案的敏感性龙卷风图。"""

    apply_paper_style(font_size)
    names = list(parameter_labels)
    lower = np.asarray(lower_effects, dtype=float)
    upper = np.asarray(upper_effects, dtype=float)
    if lower.shape != upper.shape or lower.ndim != 1 or lower.size != len(names):
        raise ValueError("参数名、lower_effects和upper_effects必须一一对应。")
    order = np.argsort(np.maximum(np.abs(lower), np.abs(upper)))
    names, lower, upper = [names[idx] for idx in order], lower[order], upper[order]
    figsize = figsize or (8.4, max(3.8, 0.55 * len(names) + 1.5))

    fig, ax = plt.subplots(figsize=figsize)
    positions = np.arange(len(names))
    bars_low = ax.barh(positions, lower, height=0.36, color=PALETTE["navy"], edgecolor=PALETTE["ink"], linewidth=0.5, label=lower_label, zorder=3)
    bars_high = ax.barh(positions, upper, height=0.36, color=PALETTE["orange"], edgecolor=PALETTE["ink"], linewidth=0.5, label=upper_label, zorder=3)
    del bars_low, bars_high
    maximum = max(float(np.max(np.abs(lower))), float(np.max(np.abs(upper))), 1e-10)
    ax.axvline(0, color=PALETTE["ink"], linewidth=1.0, zorder=4)
    ax.set_xlim(-maximum * 1.20, maximum * 1.20)
    ax.set_yticks(positions, names)
    ax.set_xlabel(xlabel)
    ax.xaxis.grid(True, color=PALETTE["grid"], linewidth=0.75, linestyle="--", zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(loc="lower right", frameon=False)
    fig.tight_layout()
    return fig, ax


def sensitivity_curve(
    parameter_values: Sequence[float],
    response_series: Mapping[str, Sequence[float]],
    *,
    xlabel: str,
    ylabel: str,
    baseline_parameter: float | None = None,
    colors: Mapping[str, str] | None = None,
    figsize: tuple[float, float] = (8.0, 4.8),
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制一个参数在合理区间内变化时的模型响应曲线。"""

    apply_paper_style(font_size)
    x_values = np.asarray(parameter_values, dtype=float)
    if x_values.ndim != 1 or x_values.size < 3:
        raise ValueError("parameter_values必须至少含3个有序取值。")
    if np.any(np.diff(x_values) <= 0):
        raise ValueError("parameter_values必须严格递增。")
    default_colors = [PALETTE["navy"], PALETTE["orange"], PALETTE["teal"], PALETTE["purple"]]
    fig, ax = plt.subplots(figsize=figsize)
    for idx, (label, response) in enumerate(response_series.items()):
        y_values = np.asarray(response, dtype=float)
        if y_values.shape != x_values.shape:
            raise ValueError(f"{label}与parameter_values长度不一致。")
        color = (colors or {}).get(label, default_colors[idx % len(default_colors)])
        ax.plot(x_values, y_values, marker="o", markersize=4.4, color=color, label=label, zorder=3)
    if baseline_parameter is not None:
        if baseline_parameter < x_values.min() or baseline_parameter > x_values.max():
            raise ValueError("baseline_parameter必须位于参数试验区间内。")
        ax.axvline(baseline_parameter, color=PALETTE["red"], linestyle="--", linewidth=1.1, label="基准取值", zorder=2)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    _finish_axes(ax, open_spines=True)
    ax.legend(frameon=True, facecolor="white", edgecolor="#B9C2CE")
    fig.tight_layout()
    return fig, ax


def pareto_front(
    objective_x: Sequence[float],
    objective_y: Sequence[float],
    *,
    xlabel: str,
    ylabel: str,
    maximize_x: bool,
    maximize_y: bool,
    selected_index: int | None = None,
    figsize: tuple[float, float] = (7.2, 5.3),
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes, np.ndarray]:
    """绘制二维多目标问题的非支配解集和选定折中解。"""

    apply_paper_style(font_size)
    x_values = np.asarray(objective_x, dtype=float)
    y_values = np.asarray(objective_y, dtype=float)
    if x_values.shape != y_values.shape or x_values.ndim != 1 or x_values.size < 2:
        raise ValueError("两个目标必须为等长且至少含两个候选解的一维数组。")
    if not np.all(np.isfinite(x_values)) or not np.all(np.isfinite(y_values)):
        raise ValueError("Pareto图不接受缺失或无穷目标值。")
    transformed_x = x_values if maximize_x else -x_values
    transformed_y = y_values if maximize_y else -y_values
    front = np.ones(x_values.size, dtype=bool)
    for i in range(x_values.size):
        dominates_i = (
            (transformed_x >= transformed_x[i])
            & (transformed_y >= transformed_y[i])
            & ((transformed_x > transformed_x[i]) | (transformed_y > transformed_y[i]))
        )
        if np.any(dominates_i):
            front[i] = False

    fig, ax = plt.subplots(figsize=figsize)
    ax.scatter(x_values[~front], y_values[~front], s=28, color="#B8C0CC", alpha=0.68, edgecolors="white", linewidths=0.35, label="非前沿候选解", zorder=2)
    ax.scatter(x_values[front], y_values[front], s=42, color=PALETTE["orange"], edgecolors=PALETTE["ink"], linewidths=0.45, label="Pareto前沿", zorder=4)
    sorted_front = np.where(front)[0][np.argsort(x_values[front])]
    if sorted_front.size >= 2:
        ax.plot(x_values[sorted_front], y_values[sorted_front], color=PALETTE["orange"], lw=1.2, alpha=0.75, zorder=3)
    if selected_index is not None:
        if not 0 <= selected_index < x_values.size:
            raise ValueError("selected_index超出候选解范围。")
        ax.scatter(x_values[selected_index], y_values[selected_index], marker="*", s=150, color=PALETTE["red"], edgecolors="white", linewidths=0.55, label="选定折中解", zorder=5)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    _finish_axes(ax, open_spines=True)
    ax.legend(frameon=True, facecolor="white", edgecolor="#B9C2CE")
    fig.tight_layout()
    return fig, ax, front


def lollipop_ranking(
    labels: Sequence[str],
    values: Sequence[float],
    *,
    xlabel: str,
    top_n: int | None = None,
    descending: bool = True,
    figsize: tuple[float, float] | None = None,
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制变量重要度、方案评分或排序指标的棒棒糖图。"""

    apply_paper_style(font_size)
    names = list(labels)
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size != len(names):
        raise ValueError("labels与values必须为一一对应的一维序列。")
    if top_n is not None and top_n < 1:
        raise ValueError("top_n必须为正整数或None。")
    order = np.argsort(array)
    if descending:
        order = order[::-1]
    if top_n is not None:
        order = order[:top_n]
    names, array = [names[idx] for idx in order], array[order]
    figsize = figsize or (8.2, max(3.6, 0.48 * len(names) + 1.3))

    fig, ax = plt.subplots(figsize=figsize)
    positions = np.arange(array.size)
    for position, value in zip(positions, array):
        ax.hlines(position, 0, value, color=PALETTE["grid"], lw=2.1, zorder=1)
    colors = [PALETTE["orange"] if value >= 0 else PALETTE["navy"] for value in array]
    ax.scatter(array, positions, s=54, color=colors, edgecolors=PALETTE["ink"], linewidths=0.45, zorder=3)
    maximum = max(float(np.max(np.abs(array))), 1e-10)
    for position, value in zip(positions, array):
        ax.text(value + np.sign(value if value != 0 else 1) * maximum * 0.025, position, f"{value:.3f}", ha="left" if value >= 0 else "right", va="center", fontsize=max(9, font_size - 4))
    ax.axvline(0, color=PALETTE["ink"], linewidth=0.85, zorder=2)
    ax.set_yticks(positions, names)
    ax.set_xlabel(xlabel)
    ax.invert_yaxis()
    ax.xaxis.grid(True, color=PALETTE["grid"], linewidth=0.75, linestyle="--", zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout()
    return fig, ax


def spatial_bubble(
    x: Sequence[float],
    y: Sequence[float],
    values: Sequence[float],
    *,
    xlabel: str,
    ylabel: str,
    value_label: str,
    point_labels: Sequence[str] | None = None,
    signed: bool = False,
    figsize: tuple[float, float] = (7.2, 5.6),
    font_size: float = 14,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制带大小和颜色编码的二维空间点位图。

    x、y必须是有实际空间或坐标含义的数值，不能把无序类别编号伪装为空间图。
    """

    apply_paper_style(font_size)
    x_values = np.asarray(x, dtype=float)
    y_values = np.asarray(y, dtype=float)
    value_array = np.asarray(values, dtype=float)
    if x_values.shape != y_values.shape or x_values.shape != value_array.shape or x_values.ndim != 1:
        raise ValueError("x、y和values必须为等长一维数组。")
    if point_labels is not None and len(point_labels) != x_values.size:
        raise ValueError("point_labels长度必须与点数一致。")
    magnitude = np.abs(value_array)
    maximum = max(float(np.max(magnitude)), 1e-10)
    sizes = 55 + 290 * magnitude / maximum
    if signed:
        v = max(float(np.max(np.abs(value_array))), 1e-10)
        norm = TwoSlopeNorm(vmin=-v, vcenter=0, vmax=v)
        cmap = "RdBu_r"
    else:
        norm, cmap = None, "YlOrRd"
    fig, ax = plt.subplots(figsize=figsize)
    points = ax.scatter(x_values, y_values, c=value_array, s=sizes, cmap=cmap, norm=norm, alpha=0.82, edgecolors=PALETTE["ink"], linewidths=0.45, zorder=3)
    if point_labels is not None:
        for x_value, y_value, label in zip(x_values, y_values, point_labels):
            ax.annotate(label, (x_value, y_value), xytext=(4, 4), textcoords="offset points", fontsize=max(9, font_size - 4), color=PALETTE["ink"])
    colorbar = fig.colorbar(points, ax=ax, pad=0.02)
    colorbar.set_label(value_label)
    colorbar.ax.tick_params(labelsize=max(10, font_size - 3))
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    _finish_axes(ax, open_spines=True)
    fig.tight_layout()
    return fig, ax



def _flowchart_font_family() -> str:
    """Choose an installed serif font suitable for formal paper flowcharts."""

    installed = {entry.name.casefold(): entry.name for entry in font_manager.fontManager.ttflist}
    for candidate in (
        "SimSun",
        "STSong",
        "Songti SC",
        "Noto Serif CJK SC",
        "Source Han Serif SC",
        "Times New Roman",
        "DejaVu Serif",
    ):
        match = installed.get(candidate.casefold())
        if match:
            return match
    return "serif"



def process_flowchart(
    nodes: Sequence[str],
    edges: Sequence[tuple[str, str]],
    *,
    positions: Mapping[str, tuple[float, float]] | None = None,
    node_groups: Mapping[str, str] | None = None,
    figsize: tuple[float, float] | None = None,
    font_size: float = 13,
) -> tuple[plt.Figure, plt.Axes]:
    """Draw a formal black-and-white mathematical-modeling flowchart.

    With ``positions=None``, nodes must form one consecutive chain in the order
    supplied and are placed in a three-column serpentine layout. Branches,
    cycles, and parallel paths require explicit positions. Explicit positions
    must align every edge horizontally or vertically; arrows that cross, overlap,
    or pass through another node are rejected.

    ``node_groups`` is retained for API compatibility and validation only. It no
    longer changes node colors because the paper style requires identical white
    rectangles with thin black borders.
    """

    apply_paper_style(font_size)
    labels = list(nodes)
    if not 2 <= len(labels) <= 12 or len(set(labels)) != len(labels):
        raise ValueError("流程图节点数应为2—12且节点名称唯一。")
    if any(not isinstance(label, str) or not label.strip() for label in labels):
        raise ValueError("流程图节点名称必须是非空字符串。")
    display_labels = {label: display_label(label.strip()) for label in labels}
    if node_groups is not None and not set(node_groups).issubset(display_labels):
        raise ValueError("node_groups只能包含nodes中的节点。")

    width, height = node_dimensions(display_labels)
    position_map, row_count, segments = prepare_layout(labels, edges, positions, width, height)
    if figsize is None:
        default_height = {1: 2.8, 2: 4.0, 3: 4.8, 4: 5.0}.get(row_count, 5.0)
        figsize = (10.0 if len(labels) > 3 else 9.0, default_height)

    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    for start, end, _ in segments:
        ax.add_patch(
            FancyArrowPatch(
                start,
                end,
                arrowstyle="-|>",
                mutation_scale=11,
                linewidth=1.0,
                color="#000000",
                shrinkA=0,
                shrinkB=0,
                connectionstyle="arc3,rad=0.0",
                zorder=1,
            )
        )

    font_family = _flowchart_font_family()
    for label in labels:
        x_value, y_value = position_map[label]
        ax.add_patch(
            Rectangle(
                (x_value - width / 2, y_value - height / 2),
                width,
                height,
                facecolor="white",
                edgecolor="#000000",
                linewidth=1.0,
                zorder=2,
            )
        )
        ax.text(
            x_value,
            y_value,
            display_labels[label],
            ha="center",
            va="center",
            fontsize=font_size,
            fontfamily=font_family,
            fontweight="normal",
            color="#000000",
            linespacing=1.15,
            zorder=3,
        )

    fig.tight_layout(pad=0.3)
    return fig, ax
