# -*- coding: utf-8 -*-
"""图：问题二净负荷场景带（历史残差校准 P10–P90）。

以秋分(9-23)为代表日：净负荷点预测(实线) + 历史残差逐区间 P10–P90 校准带 +
当日真实净负荷(散点)。带宽来自规划窗全体残差分位，纯历史因果校准。
数据来源：figures/fig_data.json 的 scenario_band（真实预测/实测差分位）。
"""
import sys, os
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
from _figcommon import *

DAY = "2025-09-23"
sb = figdata()["scenario_band"][DAY]
h = HOURS
fc = np.array(sb["net_fc"]); true = np.array(sb["net_true"])
lo = np.array(sb["band_lo"]); hi = np.array(sb["band_hi"])

fig, ax = plt.subplots(figsize=(6.4, 3.9))
uncertainty_band(ax, h, lo, hi, color=PALETTE[0], alpha=0.18,
                 label="P10–P90 校准带")
ax.plot(h, fc, color=PALETTE[0], lw=1.6, label="净负荷点预测")
ax.plot(h, true, color=COLORS["down"], lw=0, marker="o", ms=2.4,
        alpha=0.75, label="当日真实净负荷")
ax.axhline(0, color=COLORS["ref_line"], lw=0.8, ls="--")
ax.set_xlabel("时刻 (h)")
ax.set_ylabel("净负荷 (kW)")
hour_axis(ax)
auto_legend(ax)

# 覆盖率（真实落入带内比例）作短锚点数值
cover = float(np.mean((true >= lo) & (true <= hi))) * 100
ax.annotate(f"带内覆盖 {cover:.0f}%", xy=(0.02, 0.04),
            xycoords="axes fraction", color=COLORS["text"])

finish(fig, "fig_q2_scenario_band")
