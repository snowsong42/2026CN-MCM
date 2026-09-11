# -*- coding: utf-8 -*-
"""问题四修订版四张证据图：结构、套利、信息价值与分支费用对比。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                str(Path(__file__).resolve().parents[1] / "code")]

from _figcommon import *
from utils import load_annual


annual = load_annual()
real = np.asarray(annual["price_volatile"], dtype=float)
skeleton = np.asarray(annual["price"][0], dtype=float)
slot_mean = real.mean(axis=0)
q10, q90 = np.quantile(real, [0.10, 0.90], axis=0)
h = HOURS

results_dir = Path(__file__).resolve().parent
with (results_dir / "problem_2_results.json").open(encoding="utf-8") as f:
    q2_result = json.load(f)
with (results_dir / "problem_3_results.json").open(encoding="utf-8") as f:
    q3_result = json.load(f)
with (results_dir / "problem_4_results.json").open(encoding="utf-8") as f:
    q4_result = json.load(f)


# 图 17：价格结构与骨架预测
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.8, 3.25))
ax1.fill_between(h, q10, q90, color=PALETTE[0], alpha=0.18, label="真实价10%—90%带")
ax1.plot(h, skeleton, color=COLORS["highlight"], lw=1.55, label="附件1骨架")
ax1.plot(h, slot_mean, color=PALETTE[0], lw=1.1, ls="--", label="附件4同时段均值")
hour_axis(ax1)
ax1.set_xlabel("时刻 (h)")
ax1.set_ylabel("电价 (元/kWh)")
ax1.text(0.03, 0.94, "相关系数 1.0000", transform=ax1.transAxes,
         ha="left", va="top", fontsize=8.5)
auto_legend(ax1)
panel(ax1, "(a)")

date = "2025-09-23"
idx = list(annual["dates"]).index(date)
ax2.step(h, real[idx], where="mid", color=PALETTE[3], lw=1.1, label="当日真实价")
ax2.step(h, skeleton, where="mid", color=COLORS["highlight"], lw=1.4,
         ls="--", label="骨架预测价")
hour_axis(ax2)
ax2.set_xlabel("时刻 (h)")
ax2.set_ylabel("电价 (元/kWh)")
ax2.text(0.03, 0.94, "MAE 0.09632 元/kWh", transform=ax2.transAxes,
         ha="left", va="top", fontsize=8.5)
auto_legend(ax2)
panel(ax2, "(b)")
finish(fig, "fig_q4_price_prediction")


# 图 18：峰谷价差与单位储能理论套利收益
spread = np.ptp(real, axis=1)
eta = 0.9
unit_profit = eta ** 2 * real.max(axis=1) - real.min(axis=1)
coef = np.polyfit(spread, unit_profit, 1)
x_line = np.linspace(spread.min(), spread.max(), 120)
corr = float(np.corrcoef(spread, unit_profit)[0, 1])

fig, ax = plt.subplots(figsize=(6.1, 3.8))
ax.scatter(spread, unit_profit, s=13, alpha=0.48, color=PALETTE[0],
           edgecolors="none", label="每日观测")
ax.plot(x_line, np.polyval(coef, x_line), color=COLORS["highlight"], lw=1.6,
        label="线性趋势")
ax.set_xlabel("日峰谷价差 (元/kWh)")
ax.set_ylabel("单位充电量理论套利收益 (元/kWh)")
ax.text(0.03, 0.94, f"相关系数 {corr:.4f}", transform=ax.transAxes,
        ha="left", va="top", fontsize=9)
auto_legend(ax)
finish(fig, "fig_q4_spread_arbitrage")


# 图 19：完美价格信息价值
voi_names = ["0:00先知真价", "仅用骨架预测"]
voi = q4_result["price_information_value"]
voi_cost = np.array([voi["oracle_total_cost_yuan"],
                     voi["skeleton_total_cost_yuan"]]) / 1e6
fig, ax = plt.subplots(figsize=(5.4, 3.7))
bars = ax.bar(np.arange(2), voi_cost, width=0.56,
              color=[PALETTE[0], COLORS["highlight"]], edgecolor="white")
ax.set_xticks(np.arange(2))
ax.set_xticklabels(voi_names)
ax.set_ylabel("全年总费用 (百万元)")
ax.set_ylim(0, 16.3)
for bar, val in zip(bars, voi_cost):
    ax.annotate(f"{val:.4f}", (bar.get_x() + bar.get_width() / 2, val),
                xytext=(0, 4), textcoords="offset points", ha="center",
                va="bottom", fontweight="bold")
ax.text(0.5, 0.84, f"完美信息价值仅 {voi['value_pct']:.4f}%",
        transform=ax.transAxes, ha="center", va="top", fontsize=9.2,
        color="#222222", bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.90})
finish(fig, "fig_q4_information_value")


# 图 20：固定/波动电价下两种信息结构的费用分解
labels = ["问题二\n固定价", "4-2\n波动价", "问题三\n固定价", "4-3\n波动价"]
plan = np.array([q2_result["plan_cost_yuan"],
                 q4_result["result_4_2"]["plan_cost_yuan"],
                 q3_result["base_commit_cost_yuan"],
                 q4_result["result_4_3"]["base_commit_cost_yuan"]]) / 1e6
adjust = np.array([0.0, 0.0,
                   q3_result["over_adjust_cost_yuan"] + q3_result["breach_cost_yuan"],
                   q4_result["result_4_3"]["over_adjust_cost_yuan"]
                   + q4_result["result_4_3"]["breach_cost_yuan"]]) / 1e6
emergency = np.array([q2_result["emergency_cost_yuan"],
                      q4_result["result_4_2"]["emergency_cost_yuan"],
                      q3_result["emergency_cost_yuan"],
                      q4_result["result_4_3"]["emergency_cost_yuan"]]) / 1e6
total = plan + adjust + emergency
x = np.arange(4)

fig, ax = plt.subplots(figsize=(6.4, 4.0))
ax.bar(x, plan, width=0.62, color=PALETTE[0], edgecolor="white", label="计划购电费")
ax.bar(x, adjust, bottom=plan, width=0.62, color=PALETTE[5], edgecolor="white",
       label="调整偏差费")
ax.bar(x, emergency, bottom=plan + adjust, width=0.62,
       color=COLORS["highlight"], edgecolor="white", label="紧急购电费")
for xi, val in zip(x, total):
    ax.annotate(f"{val:.2f}", (xi, val), xytext=(0, 4),
                textcoords="offset points", ha="center", va="bottom",
                fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylabel("全年费用 (百万元)")
ax.set_ylim(0, 17.0)
ax.axvline(1.5, color=COLORS["grid"], lw=0.8, ls=":")
auto_legend(ax)
finish(fig, "fig_q4_scenario_compare")
