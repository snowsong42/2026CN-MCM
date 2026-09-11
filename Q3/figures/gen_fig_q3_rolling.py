# -*- coding: utf-8 -*-
"""图：问题三滚动调整过程（节点 0/6/12/18 计划曲线逐次更新）。

以秋分(9-23)为代表日，真实重跑该日 SMPC，快照每个预报节点重解后的承诺购电曲线：
0:00 日前基准 → 6:00/12:00/18:00 依附件3新预报滚动更新剩余时域。
真实起始 SOC 取自 problem_3 落盘序列前一日期末（跨日传递）。竖线标节点时刻。
数据来源：figures/problem_3_results.json（起始 SOC）+ code/ 真实重解。
"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), ROOT,
                os.path.join(ROOT, "code")]
from _figcommon import *
import utils as u
import params as p
import problem3 as q3

DAY = "2025-09-23"

u.set_all_seeds()
data = u.load_annual()
rolling = u.load_pv_forecast_rolling()
plan_days = u.find_plan_days(data["dates"])
model = u.fit_load_forecaster(data["load"], range(0, plan_days.start))
dates = [str(x) for x in data["dates"]]
di = dates.index(DAY)

# 跨日起始 SOC：落盘序列中前一规划日的期末 SOC
r3 = results(3)
ddates = [d["date"] for d in r3["daily"]]
prev_idx = ddates.index(DAY) - 1
E0 = r3["series"]["E"][prev_idx][-1] if prev_idx >= 0 else p.INIT_SOC_KWH

lam = u.estimate_terminal_value(data["price"])
load_fc0 = u.forecast_load(data["load"], di, model)
pv_fc0 = u.forecast_pv(data["pv"], di)
price = data["price"][di]
load_act, pv_act = data["load"][di], data["pv"][di]

# 节点0：日前基准计划
lp0 = u.solve_daily_lp(price, load_fc0, pv_fc0, E0,
                       terminal_mode="value", terminal_value=lam)
q0 = lp0["q"].copy()
snapshots = [("0:00 日前基准", q0.copy())]

# 节点 6/12/18：真实重解，逐次快照承诺曲线
q_com = q0.copy(); Ecur = E0; pos = 0
node_hours = []
for h in p.ISSUE_HOURS:
    if h == 0:
        continue
    node = h * (60 // p.INTERVAL_MINUTES)
    seg = q3._execute_slice(q_com, load_act, pv_act, price, Ecur, pos, node)
    Ecur = seg["E_end"]; pos = node
    pv_fc = q3.node_pv_forecast(rolling, DAY, h, data["pv"], di)
    q_com[node:] = q3.solve_resolve_lp(price, load_fc0, pv_fc, Ecur, q0, node, lam, p.RHO_REFUND)
    snapshots.append((f"{h}:00 重解", q_com.copy()))
    node_hours.append(h)

h_axis = HOURS
fig, ax = plt.subplots(figsize=(6.4, 3.9))
cols = [COLORS["neutral"], PALETTE[1], PALETTE[0], PALETTE[3]]
lws = [1.0, 1.2, 1.4, 1.7]
for (lab, curve), col, lw in zip(snapshots, cols, lws):
    ax.step(h_axis, curve, where="mid", color=col, lw=lw, label=lab)
for h in node_hours:
    ax.axvline(h, color=COLORS["ref_line"], lw=0.8, ls=":")
ax.set_xlabel("时刻 (h)")
ax.set_ylabel("承诺购电量 (kWh)")
hour_axis(ax)
auto_legend(ax)

finish(fig, "fig_q3_rolling")
