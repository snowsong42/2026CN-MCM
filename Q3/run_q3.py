# -*- coding: utf-8 -*-
"""问题三运行入口：多阶段滚动 SMPC（{0,6,12,18} 节点重解）+ 预报价值实验。

独立运行（不依赖工作区）：
    D:\\project\\pythonProject\\2026CN-MCM\\.venv\\Scripts\\python.exe run_q3.py

依赖：code/params.py、code/utils.py、code/problem3.py（本地拷贝）
输入：user_data/附件1..4.xlsx        输出：figures/problem_3_results.json
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)

sys.path.insert(0, str(HERE / "code"))
sys.path.insert(0, str(HERE))
os.environ["FIG_SEED_NAME"] = "workspace"   # 固定绘图配色种子（不受运行目录影响）
os.environ["FIG_LOCAL"] = str(FIG)

import problem3                                                        # noqa: E402
import utils as u                                                      # noqa: E402

_orig = u.save_json


def _save_json(obj, name, *a, **k):
    p = Path(str(name))
    # 本目录 code 里的结果 json（不含附件/模板）统一改写到本地 figures/
    if p.name.startswith(("problem_", "all_results", "fig_data", "data_check",
                          "constraint_audit", "cross_problem_check")):
        return _orig(obj, str(FIG / p.name), *a, **k)
    if not p.is_absolute() and str(p).startswith("figures/"):
        return _orig(obj, str(FIG / p.name), *a, **k)
    return _orig(obj, name, *a, **k)


u.save_json = _save_json


def main():
    res = problem3.run()
    print("=" * 64)
    print("问题三（多阶段滚动 SMPC + 预报价值）复现结果")
    print("=" * 64)
    print(f"  规划天数            {res['n_days']:>14d} 天（{res['eval_start']} 起）")
    print(f"  全年总费用          {res['total_cost_yuan']:>14,.2f} 元")
    print(f"  计划承诺费          {res['base_commit_cost_yuan']:>14,.2f} 元")
    print(f"  增购调整费(1.5×)    {res['over_adjust_cost_yuan']:>14,.2f} 元")
    print(f"  减购违约费(0.5−ρ)   {res['breach_cost_yuan']:>14,.2f} 元（ρ={res['rho_refund']}）")
    print(f"  紧急购电费          {res['emergency_cost_yuan']:>14,.2f} 元")
    print(f"  增购量 / 减购量     {res['adjust_up_kWh']:>12,.2f} / {res['adjust_down_kWh']:,.2f} kWh")
    print(f"  紧急购电量 / 弃光量 {res['emergency_qty_kWh']:>12,.2f} / {res['curtail_qty_kWh']:,.2f} kWh")
    print(f"  预报价值 VoF        {res['vof']['baseline_no_node_cost']:,.2f} → "
          f"{res['vof']['all_node_cost']:,.2f} 元，省 {res['vof']['vof_full_yuan']:,.2f} 元")
    print("-" * 64)
    print(f"  结果已写入 {FIG / 'problem_3_results.json'}")


if __name__ == "__main__":
    main()
