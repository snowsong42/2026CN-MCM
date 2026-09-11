# -*- coding: utf-8 -*-
"""图：问题三调整费用构成（2 面板，ρ=0 主口径 vs ρ=1 退费敏感性）。

(a) 日内调整结算分量发散柱：增购超额费(1.5×，正) / 减购结算(ρ=0 违约罚正、
    ρ=1 退费转负)，直观显示退费开关如何翻转减购激励。
(b) 全年总费四分量堆叠(基础/增购/减购/紧急) ρ=0 vs ρ=1，顶标总费。
数据来源：figures/problem_3_results.json(ρ=0) + figures/fig_data.json rho1(ρ=1 真实重跑)。
"""
import sys, os
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
from _figcommon import *

r3 = results(3)
r1 = figdata()["rho1"]
K = 1e6   # → 百万元

over = [r3["over_adjust_cost_yuan"] / K, r1["over_cost"] / K]
breach = [r3["breach_cost_yuan"] / K, r1["breach_cost"] / K]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.6, 3.3))

# (a) 调整结算分量 发散柱
x = np.array([0, 1]); w = 0.34
b1 = ax1.bar(x - w / 2, over, w, color=PALETTE[0], edgecolor="white",
             linewidth=0.4, label="增购超额费")
b2 = ax1.bar(x + w / 2, breach, w, color=COLORS["down"], edgecolor="white",
             linewidth=0.4, label="减购结算")
ax1.axhline(0, color=COLORS["ref_line"], lw=0.9)
ax1.bar_label(b1, fmt="%.2f", padding=2)
ax1.bar_label(b2, fmt="%.2f", padding=2)
ax1.set_xticks(x)
ax1.set_xticklabels(["ρ=0", "ρ=1"])
ax1.set_ylabel("结算费 (百万元)")
auto_legend(ax1)
panel(ax1, "(a)")

# (b) 总费四分量堆叠
comps = [
    ("基础承诺", [r3["base_commit_cost_yuan"] / K, r1["base_cost"] / K], PALETTE[0]),
    ("增购超额", [r3["over_adjust_cost_yuan"] / K, r1["over_cost"] / K], PALETTE[1]),
    ("减购结算", [r3["breach_cost_yuan"] / K, r1["breach_cost"] / K], COLORS["highlight"]),
    ("紧急购电", [r3["emergency_cost_yuan"] / K, r1["emergency_cost"] / K], COLORS["down"]),
]
xb = np.array([0, 1])
bottoms = np.zeros(2)
for name, vals, col in comps:
    vals = np.array(vals)
    ax2.bar(xb, vals, bottom=bottoms, width=0.5, color=col,
            edgecolor="white", linewidth=0.5, label=name)
    bottoms += vals
tot = [r3["total_cost_yuan"] / K, r1["total_cost"] / K]
for xi, t in zip(xb, tot):
    ax2.annotate(f"{t:.2f}", xy=(xi, t), xytext=(0, 3),
                 textcoords="offset points", ha="center", fontweight="bold")
ax2.set_xticks(xb)
ax2.set_xticklabels(["ρ=0", "ρ=1"])
ax2.set_ylabel("全年总费 (百万元)")
ax2.set_ylim(0, max(tot) * 1.16)
auto_legend(ax2)
panel(ax2, "(b)")

finish(fig, "fig_q3_adjust_cost")
