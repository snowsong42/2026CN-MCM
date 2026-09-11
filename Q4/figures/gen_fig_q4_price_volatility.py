# -*- coding: utf-8 -*-
"""图：问题四波动电价形态与调度响应（2 面板）。

(a) 附件4 四考察日波动电价 vs 附件1 固定模板叠加，示峰谷时刻逐日漂移。
(b) 同一考察日(秋分) 固定电价(问题二) vs 波动电价(问题4-2) 下净充放(c−d)时序差异，
    叠当日波动电价，显示最优充放时机随价格形态重排。
数据来源：figures/fig_data.json price_curves + problem_2/4 series。
"""
import sys, os
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
from _figcommon import *

pc = figdata()["price_curves"]
h = HOURS
tpl = np.array(pc["template"])

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.7, 3.3))

# (a) 波动电价四考察日 vs 固定模板
cols = [PALETTE[0], PALETTE[1], PALETTE[5], PALETTE[3]]
for ed, col in zip(EVAL_DATES, cols):
    ax1.plot(h, pc["volatile"][ed], color=col, lw=1.1, alpha=0.9,
             label=eval_label(ed).split(" ")[0])
ax1.step(h, tpl, where="mid", color=COLORS["highlight"], lw=1.5, ls="--",
         label="固定模板")
hour_axis(ax1)
ax1.set_xlabel("时刻 (h)")
ax1.set_ylabel("电价 (元/kWh)")
auto_legend(ax1)
panel(ax1, "(a)")

# (b) 固定 vs 波动 下净充放时序（秋分）
DAY = "2025-09-23"
r2 = results(2); r4 = results(4)
d2 = [d["date"] for d in r2["daily"]].index(DAY)
cd_fixed = np.array(r2["series"]["c"][d2]) - np.array(r2["series"]["d"][d2])
d4 = [d["date"] for d in r4["daily_4_2"]].index(DAY)
cd_vol = np.array(r4["series_4_2"]["c"][d4]) - np.array(r4["series_4_2"]["d"][d4])

ax2.plot(h, cd_fixed, color=PALETTE[0], lw=1.4, label="固定电价")
ax2.plot(h, cd_vol, color=COLORS["down"], lw=1.4, label="波动电价")
ax2.axhline(0, color=COLORS["ref_line"], lw=0.7)
hour_axis(ax2)
ax2.set_xlabel("时刻 (h)")
ax2.set_ylabel("净充放 c−d (kWh)")

axp = ax2.twinx()
axp.step(h, pc["volatile"][DAY], where="mid", color=COLORS["neutral"],
         lw=1.0, alpha=0.7)
axp.set_ylabel("波动电价 (元/kWh)")
axp.set_ylim(0, np.max(pc["volatile"][DAY]) * 1.3)
auto_legend(ax2)
panel(ax2, "(b)")

finish(fig, "fig_q4_price_volatility")
