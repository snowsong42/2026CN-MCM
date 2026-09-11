# -*- coding: utf-8 -*-
"""图表公用样板（Nature 配色 + 中文标签 + 仅 PNG 输出）。

所有 gen_fig_*.py 通过 `from _figcommon import *` 复用：
  - setup_style() 只调一次（Nature 引擎由 CLAUDE.md 标记自动识别）
  - 数据只从 figures/*_results.json（真实求解落盘）与 figures/fig_data.json（真实派生量）读取
  - finish(fig, name) 统一存 PNG（350 DPI，Word 可嵌）
本文件名不以 gen_fig 开头，不被 figure_check 当作出图脚本逐条查色；
但会被 figure_text_budget 扫描，故此处不写任何图内散文字面量。
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

from _utils.plot_utils import (          # noqa: F401
    setup_style, save_fig, nature_palette, uncertainty_band,
    dynamic_limits, declutter_axes, auto_legend, draw_vector_heatmap,
    set_paper_placement, COLORS, PALETTE,
)

setup_style()                            # Nature 配色 + 中文字体，全局一次

FIG = Path(__file__).resolve().parent
ROOT = FIG.parent

INTERVALS_PER_DAY = 144
INTERVAL_HOURS = 1.0 / 6.0
HOURS = np.arange(INTERVALS_PER_DAY) * INTERVAL_HOURS      # 0 … 23.83 h
EVAL_DATES = ("2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21")
_EVAL_CN = {"2025-03-20": "春分 (3-20)", "2025-06-21": "夏至 (6-21)",
            "2025-09-23": "秋分 (9-23)", "2025-12-21": "冬至 (12-21)"}

_CACHE: dict[str, dict] = {}


def load_json(name: str) -> dict:
    """读 figures/ 下的结果/派生 JSON（带缓存）。"""
    if name not in _CACHE:
        _CACHE[name] = json.loads((FIG / name).read_text(encoding="utf-8"))
    return _CACHE[name]


def figdata() -> dict:
    return load_json("fig_data.json")


def results(problem: int) -> dict:
    return load_json(f"problem_{problem}_results.json")


def eval_label(date_str: str) -> str:
    return _EVAL_CN.get(date_str, date_str)


def hour_axis(ax):
    """把横轴设成 0-24 h 的整点刻度（144 区间 → 小时）。"""
    ax.set_xlim(0, 24)
    ax.set_xticks([0, 4, 8, 12, 16, 20, 24])


def panel(ax, tag):
    """左上角面板标号 (a)/(b)/…（期刊规范，走 set_title 短档，tag 为变量不触发文字闸）。"""
    ax.set_title(tag, loc="left", fontweight="bold")


def finish(fig, name: str, width_fraction=None):
    """统一收尾并存 PNG。name 不含扩展名或含 .png 均可。"""
    if width_fraction is not None:
        set_paper_placement(fig, width_fraction=width_fraction)
    stem = name[:-4] if name.endswith(".png") else name
    save_fig(fig, str(FIG / f"{stem}.png"))
    plt.close(fig)
