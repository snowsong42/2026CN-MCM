# -*- coding: utf-8 -*-
"""图：问题一最优调度时序（典型日 144 区间）。

上：计划购电量 q、充电 c、放电 d（区间电量 kWh，充放异号显示）叠电价阴影。
下：SOC 轨迹 E，标 [1200,10800] 上下界。
数据来源：figures/problem_1_results.json 的 series（确定性 LP 最优解）。
"""
import sys, os
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
from _figcommon import *

s = results(1)["series"]
h = HOURS
q = np.array(s["q"]); c = np.array(s["c"]); dch = np.array(s["d"])
E = np.array(s["E"]); price = np.array(s["price"])

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.4, 5.0), sharex=True,
                               gridspec_kw={"height_ratios": [1.35, 1]})

# 电价阴影（高价时段淡红背景，作套利判据参考）
hi = price >= np.percentile(price, 66)
ax1.fill_between(h, 0, 1, where=hi, transform=ax1.get_xaxis_transform(),
                 color=COLORS["down"], alpha=0.07, step="mid")
ax1.plot(h, q, color=PALETTE[0], lw=1.5, label="计划购电")
ax1.plot(h, c, color=COLORS["accent"], lw=1.3, label="充电")
ax1.plot(h, -dch, color=COLORS["down"], lw=1.3, label="放电 (负向)")
ax1.axhline(0, color=COLORS["ref_line"], lw=0.8)
ax1.set_ylabel("区间电量 (kWh)")
auto_legend(ax1)
panel(ax1, "(a)")

# SOC 轨迹
ax2.plot(h, E, color=PALETTE[3], lw=1.6, label="储电量 SOC")
ax2.axhline(1200, color=COLORS["ref_line"], lw=1.0, ls="--")
ax2.axhline(10800, color=COLORS["ref_line"], lw=1.0, ls="--")
ax2.set_yticks([1200, 4000, 6000, 8000, 10800])
ax2.set_ylabel("SOC (kWh)")
ax2.set_xlabel("时刻 (h)")
hour_axis(ax2)
ax2.set_ylim(0, 11600)
auto_legend(ax2)
panel(ax2, "(b)")

finish(fig, "fig_q1_dispatch")
