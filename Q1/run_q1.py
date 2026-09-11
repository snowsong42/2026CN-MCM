# -*- coding: utf-8 -*-
"""问题一（Q1）运行入口：典型日确定性 LP 调度 + 显式互斥 MILP 交叉校验。

本目录是 MHAgent 工作区中与问题一相关的代码与资源的**独立拷贝**，可脱离工作区单独运行。

用法（工作目录任意，脚本自行处理路径）：
    D:\\project\\pythonProject\\2026CN-MCM\\.venv\\Scripts\\python.exe run_q1.py

数据与结果去向：
    输入 user_data/附件1..4.xlsx（本目录内的拷贝）
    结果写入本目录 figures/problem_1_results.json（与工作区完全独立）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIG_OUT = HERE / "figures"                           # 结果落本目录（与工作区相互独立）
FIG_OUT.mkdir(exist_ok=True)

sys.path.insert(0, str(HERE / "code"))               # params / utils / problem1
sys.path.insert(0, str(HERE))                        # _utils 包
os.environ["FIG_SEED_NAME"] = "workspace"   # 固定绘图配色种子（不受运行目录影响）
os.environ["FIG_LOCAL"] = str(FIG_OUT)               # 让 _figcommon 也存到本地

import problem1                                       # noqa: E402
import utils as u                                     # noqa: E402


def main():
    # 结果统一回写到工作区 figures/，与 fill_excel / constraint_audit / 绘图脚本共用
    _orig_save = u.save_json

    def save_json(obj, name, *a, **k):
        p = Path(name)
        FIG_OUT.mkdir(parents=True, exist_ok=True)
        # 本目录 code 里的结果 json 统一改写到本地 figures/（含绝对路径情形）
        if p.name.startswith(("problem_", "all_results", "fig_data", "data_check",
                              "constraint_audit", "cross_problem_check")):
            return _orig_save(obj, str(FIG_OUT / p.name), *a, **k)
        if not p.is_absolute() and str(p).startswith("figures/"):
            return _orig_save(obj, str(FIG_OUT / p.name), *a, **k)
        return _orig_save(obj, name, *a, **k)

    u.save_json = save_json

    res = problem1.run()
    print("=" * 62)
    print("问题一（典型日确定性 LP + 互斥 MILP 校验）复现结果")
    print("=" * 62)
    print(f"  全天最优购电费      {res['total_cost_yuan']:>14,.2f} 元")
    print(f"  无储能基线购电费    {res['baseline_cost_yuan']:>14,.2f} 元")
    print(f"  节省                {res['savings_yuan']:>14,.2f} 元（{res['savings_pct']}%）")
    print(f"  全天购电量          {res['purchase_kWh']:>14,.2f} kWh")
    print(f"  充电量 / 放电量     {res['charge_kWh']:>10,.2f} / {res['discharge_kWh']:,.2f} kWh")
    print(f"  弃电量 / 紧急购电   {res['curtail_kWh']:>10,.2f} / {res['emergency_kWh']:,.2f} kWh")
    print(f"  SOC 区间            [{res['soc_min']:,.2f}, {res['soc_max']:,.2f}] kWh"
          f"（E0={res['E_start']:,.0f}, E144={res['E_end']:,.0f}）")
    print(f"  LP 与 MILP 目标值   {res['milp_objective_yuan']:>14,.2f} 元"
          f"（相对差 {res['cost_lp_vs_milp_rel_gap']}，{res['milp_status']}）")
    print(f"  同时充放区间数      {res['simul_charge_discharge_intervals']}")
    print("-" * 62)
    print(f"  结果已写入 {FIG_OUT / 'problem_1_results.json'}")


if __name__ == "__main__":
    main()
