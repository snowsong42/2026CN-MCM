# -*- coding: utf-8 -*-
"""图：问题一购电费对比（无储能基线 vs 有储能最优，按电价档堆叠）。

两根堆叠柱：无储能(直接满足净负荷) / 有储能(LP 计划购电)，
各按 谷/平/峰 三档电价分层堆叠购电费(元)，顶标总费与节省率。
数据来源：figures/problem_1_results.json（series 逐区间 + 费用汇总）。
"""
import sys, os
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
from _figcommon import *

r = results(1)
s = r["series"]
price = np.array(s["price"]); load = np.array(s["load"]); pv = np.array(s["pv"])
q = np.array(s["q"])
dt = INTERVAL_HOURS

buy_base = np.maximum(load - pv, 0.0) * dt          # 无储能：直接买净负荷
cost_base = price * buy_base
cost_opt = price * q                                # 有储能：计划购电（LP）

# 电价三档（谷/平/峰）按分位切
lo_t, hi_t = np.percentile(price, [33, 66])
tier = np.where(price <= lo_t, 0, np.where(price <= hi_t, 1, 2))
tier_names = ["谷段", "平段", "峰段"]
tier_cols = [COLORS["accent"], PALETTE[1], COLORS["down"]]

base_stack = [cost_base[tier == k].sum() for k in range(3)]
opt_stack = [cost_opt[tier == k].sum() for k in range(3)]

fig, ax = plt.subplots(figsize=(6.0, 4.0))
x = [0, 1]
xt = ["无储能基线", "有储能最优"]
bottoms = np.zeros(2)
for k in range(3):
    vals = np.array([base_stack[k], opt_stack[k]])
    ax.bar(x, vals, bottom=bottoms, width=0.56, color=tier_cols[k],
           edgecolor="white", linewidth=0.5, label=tier_names[k])
    bottoms += vals

tot_base, tot_opt = sum(base_stack), sum(opt_stack)
ax.annotate(f"{tot_base:.0f}", xy=(0, tot_base), xytext=(0, 3),
            textcoords="offset points", ha="center", fontweight="bold")
ax.annotate(f"{tot_opt:.0f}", xy=(1, tot_opt), xytext=(0, 3),
            textcoords="offset points", ha="center", fontweight="bold")
save_pct = r["savings_pct"]
ax.annotate(f"节省 {save_pct:.1f}%", xy=(1, tot_opt), xytext=(0, 20),
            textcoords="offset points", ha="center", color=PALETTE[0],
            fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(xt)
ax.set_ylabel("购电费 (元)")
ax.set_ylim(0, tot_base * 1.16)
auto_legend(ax)

finish(fig, "fig_q1_cost_baseline")
