# -*- coding: utf-8 -*-
"""图：问题二全年紧急购电分布（2 面板）。

(a) 月度紧急购电量(kWh) 柱状。
(b) 月度紧急费占当月总费比例(%) 折线（右）与全年计划/紧急费构成环形（内嵌）。
数据来源：figures/problem_2_results.json 的 daily（逐日紧急量/费）与汇总。
"""
import sys, os
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
from _figcommon import *
import collections

r = results(2)
daily = r["daily"]
mq = collections.defaultdict(float)     # 月紧急量
mc = collections.defaultdict(float)     # 月紧急费
mt = collections.defaultdict(float)     # 月总费
for d in daily:
    m = int(d["date"][5:7])
    mq[m] += d["emergency_qty"]
    mc[m] += d["emergency_cost"]
    mt[m] += d["plan_cost"] + d["emergency_cost"]
months = sorted(mq.keys())
qty = [mq[m] / 1000 for m in months]        # → 千 kWh
frac = [100 * mc[m] / mt[m] if mt[m] else 0 for m in months]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.6, 3.2))

# (a) 月度紧急量
b = ax1.bar(months, qty, color=COLORS["down"], edgecolor="white",
            linewidth=0.4, width=0.68)
ax1.set_xlabel("月份")
ax1.set_ylabel("紧急购电量 (千 kWh)")
ax1.set_xticks(months)
ax1.set_ylim(0, max(qty) * 1.16)
panel(ax1, "(a)")

# (b) 月度紧急费占比 折线
ax2.plot(months, frac, color=PALETTE[0], lw=1.6, marker="o", ms=3.5,
         label="紧急费占比")
ax2.set_xlabel("月份")
ax2.set_ylabel("紧急费占当月总费 (%)")
ax2.set_xticks(months)
ax2.set_ylim(0, max(frac) * 1.25)
year_frac = 100 * r["emergency_cost_yuan"] / r["total_cost_yuan"]
ax2.axhline(year_frac, color=COLORS["ref_line"], lw=1.0, ls="--")
ax2.annotate(f"全年 {year_frac:.1f}%", xy=(months[0], year_frac),
             xytext=(2, 3), textcoords="offset points", color=COLORS["text"])
panel(ax2, "(b)")

finish(fig, "fig_q2_emergency_year")
