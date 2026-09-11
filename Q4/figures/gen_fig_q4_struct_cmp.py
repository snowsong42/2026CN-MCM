# -*- coding: utf-8 -*-
"""图：问题四结构对比（固定电价基准 vs 波动电价，分组柱）。

两组=信息结构二(0:00定+兜底) / 信息结构三(滚动 SMPC)；
每组两柱=固定电价基准(问题2/3) vs 波动电价重解(问题4-2/4-3)，
柱内堆叠 计划/基础承诺 与 应急+调整 分量，顶标总费(百万元)。
数据来源：figures/problem_2/3/4_results.json 全年汇总。
"""
import sys, os
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
from _figcommon import *

K = 1e6
r2, r3, r4 = results(2), results(3), results(4)
r42, r43 = r4["result_4_2"], r4["result_4_3"]

# 每根柱：基础(计划/承诺) + 附加(调整+应急)
def split2(plan, extra):
    return plan / K, extra / K

bars = [
    ("结构二·固定", *split2(r2["plan_cost_yuan"], r2["emergency_cost_yuan"]),
     r2["total_cost_yuan"] / K),
    ("结构二·波动", *split2(r42["plan_cost_yuan"], r42["emergency_cost_yuan"]),
     r42["total_cost_yuan"] / K),
    ("结构三·固定", *split2(r3["base_commit_cost_yuan"],
     r3["over_adjust_cost_yuan"] + r3["breach_cost_yuan"] + r3["emergency_cost_yuan"]),
     r3["total_cost_yuan"] / K),
    ("结构三·波动", *split2(r43["base_commit_cost_yuan"],
     r43["over_adjust_cost_yuan"] + r43["breach_cost_yuan"] + r43["emergency_cost_yuan"]),
     r43["total_cost_yuan"] / K),
]
labels = [b[0] for b in bars]
base = np.array([b[1] for b in bars])
extra = np.array([b[2] for b in bars])
tot = [b[3] for b in bars]
x = np.arange(4)
# 分组视觉：固定用蓝、波动用红，附加分量统一中性描边
base_cols = [PALETTE[0], COLORS["down"], PALETTE[0], COLORS["down"]]

fig, ax = plt.subplots(figsize=(6.2, 4.0))
ax.bar(x, base, width=0.62, color=base_cols, edgecolor="white",
       linewidth=0.5, label="计划/基础承诺费")
ax.bar(x, extra, bottom=base, width=0.62, color=COLORS["highlight"],
       edgecolor="white", linewidth=0.5, alpha=0.85, label="调整+应急费")
for xi, t in zip(x, tot):
    ax.annotate(f"{t:.2f}", xy=(xi, t), xytext=(0, 3),
                textcoords="offset points", ha="center", fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=12)
ax.set_ylabel("全年总费 (百万元)")
ax.set_ylim(0, max(tot) * 1.16)
# 组分隔竖线
ax.axvline(1.5, color=COLORS["grid"], lw=0.8, ls=":")
auto_legend(ax)

finish(fig, "fig_q4_struct_cmp")
