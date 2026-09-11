# -*- coding: utf-8 -*-
"""图：问题三预报价值实验（2³=8 种节点组合，棒棒糖排序）。

横向棒棒糖：每种 {6,12,18} 节点启用组合的全年总费(百万元)，按总费排序；
茎自「全关基线」画到该组合总费，长度=预报节省额；点色随启用节点数深浅。
基线(无日内节点)竖虚线为参照。数据来源：figures/problem_3_results.json 的 vof.combos。
"""
import sys, os
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
from _figcommon import *

v = results(3)["vof"]
K = 1e6
base = v["baseline_no_node_cost"] / K
combos = sorted(v["combos"], key=lambda c: c["total_cost"])   # 低费在前

def label(nodes):
    return "全关" if not nodes else "+".join(f"{h}:00" for h in nodes)

labels = [label(c["nodes"]) for c in combos]
totals = [c["total_cost"] / K for c in combos]
nns = [c["n_nodes"] for c in combos]
save = [c["vof_savings_yuan"] / K for c in combos]
# 节点数 → 颜色深浅（0 中性，1/2/3 蓝渐深）
col_by_n = {0: COLORS["neutral"], 1: PALETTE[5], 2: PALETTE[1], 3: PALETTE[0]}
cols = [col_by_n[n] for n in nns]

y = np.arange(len(combos))
fig, ax = plt.subplots(figsize=(6.4, 4.0))
ax.hlines(y, totals, base, color=COLORS["grid"], lw=1.4, zorder=1)
ax.scatter(totals, y, c=cols, s=46, zorder=3, edgecolor="white", linewidth=0.6)
ax.axvline(base, color=COLORS["ref_line"], lw=1.1, ls="--")
ax.annotate("全关基线", xy=(base, y[-1]), xytext=(-4, 6),
            textcoords="offset points", ha="right", color=COLORS["text"])

for yi, t, sv in zip(y, totals, save):
    if sv > 1e-6:
        ax.annotate(f"省 {sv:.2f}", xy=(t, yi), xytext=(-6, 0),
                    textcoords="offset points", ha="right", va="center",
                    color=PALETTE[0])
ax.set_yticks(y)
ax.set_yticklabels(labels)
ax.set_xlabel("全年总费 (百万元)")
ax.set_ylabel("启用预报节点组合")
ax.set_xlim(min(totals) - 0.35, base + 0.15)

# 节点数图例（自建句柄）
from matplotlib.lines import Line2D
leg = [Line2D([0], [0], marker="o", ls="", mfc=col_by_n[n], mec="white",
              ms=7, label=f"{n} 个节点") for n in (0, 1, 2, 3)]
ax.legend(handles=leg, frameon=False, loc="lower left", title="启用节点数")

finish(fig, "fig_q3_forecast_value")
