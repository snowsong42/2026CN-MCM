# -*- coding: utf-8 -*-
"""图：问题一低充高放套利验证（SOC 与电价双轴叠加）。

左轴 SOC(kWh)：储电量轨迹；右轴 元/kWh：分时电价阶梯。
充电区间(绿)与放电区间(红)以背景色带标出，直观显示"谷充峰放"。
数据来源：figures/problem_1_results.json 的 series。
"""
import sys, os
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
from _figcommon import *

s = results(1)["series"]
h = HOURS
E = np.array(s["E"]); c = np.array(s["c"]); dch = np.array(s["d"])
price = np.array(s["price"])

fig, ax = plt.subplots(figsize=(6.4, 3.9))
charging = c > 1e-6
discharging = dch > 1e-6
ax.fill_between(h, 0, 1, where=charging, transform=ax.get_xaxis_transform(),
                color=COLORS["accent"], alpha=0.13, step="mid", label="充电时段")
ax.fill_between(h, 0, 1, where=discharging, transform=ax.get_xaxis_transform(),
                color=COLORS["down"], alpha=0.13, step="mid", label="放电时段")
ax.plot(h, E, color=PALETTE[0], lw=1.7, label="储电量 SOC")
ax.set_xlabel("时刻 (h)")
ax.set_ylabel("SOC (kWh)")
hour_axis(ax)
ax.set_ylim(0, 11600)

axp = ax.twinx()
axp.step(h, price, where="mid", color=COLORS["highlight"], lw=1.2, label="电价")
axp.set_ylabel("电价 (元/kWh)")
axp.set_ylim(0, price.max() * 1.3)

lines = ax.get_lines() + axp.get_lines()
labels = [ln.get_label() for ln in lines]
# 背景色带的图例句柄
from matplotlib.patches import Patch
handles = [Patch(facecolor=COLORS["accent"], alpha=0.13),
           Patch(facecolor=COLORS["down"], alpha=0.13)] + lines
labels = ["充电时段", "放电时段"] + labels
ax.legend(handles, labels, frameon=False, loc="upper left", ncol=2)

finish(fig, "fig_q1_arbitrage")
