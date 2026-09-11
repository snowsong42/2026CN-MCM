# -*- coding: utf-8 -*-
"""图：问题二 4 考察日调度时序（2×2）。

每子图：计划购电 q0(0:00 定) + 紧急购电 e(日内兜底) + 净充放(c−d)，叠零线。
考察日=春分/夏至/秋分/冬至。数据来源：figures/problem_2_results.json 的 series。
"""
import sys, os
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
from _figcommon import *

r = results(2)
daily_dates = [d["date"] for d in r["daily"]]
s = r["series"]
h = HOURS
tags = ["(a)", "(b)", "(c)", "(d)"]

fig, axes = plt.subplots(2, 2, figsize=(6.6, 5.0), sharex=True)
for ax, ed, tag in zip(axes.ravel(), EVAL_DATES, tags):
    i = daily_dates.index(ed)
    q0 = np.array(s["q0"][i]); e = np.array(s["e"][i])
    net_cd = np.array(s["c"][i]) - np.array(s["d"][i])
    ax.plot(h, q0, color=PALETTE[0], lw=1.3, label="计划购电")
    ax.plot(h, net_cd, color=COLORS["highlight"], lw=1.0, label="净充放 (c−d)")
    ax.fill_between(h, 0, e, color=COLORS["down"], alpha=0.5, step="mid",
                    label="紧急购电")
    ax.axhline(0, color=COLORS["ref_line"], lw=0.7)
    hour_axis(ax)
    ax.set_title(f"{tag} {eval_label(ed)}", loc="left", fontweight="bold")

for ax in axes[:, 0]:
    ax.set_ylabel("区间电量 (kWh)")
for ax in axes[1, :]:
    ax.set_xlabel("时刻 (h)")

h0, l0 = axes[0, 0].get_legend_handles_labels()
fig.legend(h0, l0, frameon=False, loc="lower center", ncol=3,
           bbox_to_anchor=(0.5, -0.02))
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig._mh_manual_layout = True
finish(fig, "fig_q2_dispatch")
