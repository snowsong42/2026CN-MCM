# -*- coding: utf-8 -*-
"""问题二运行入口：全年日前随机优化（SAA 情景 + 因果反馈）+ 6 段备用策略搜索。

独立运行（不依赖工作区）：
    D:\\project\\pythonProject\\2026CN-MCM\\.venv\\Scripts\\python.exe run_q2.py

依赖：code/params.py、code/utils.py、code/problem2.py（均为本地拷贝）
输入：user_data/附件1..4.xlsx        输出：figures/problem_2_results.json
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
os.environ["FIG_LOCAL"] = str(FIG)          # 让 _figcommon 也把图存到本地

import problem2                                                        # noqa: E402
import utils as u                                                      # noqa: E402

_orig = u.save_json


def _save_json(obj, name, *a, **k):
    """把结果 json 重定向到本目录的 figures/（含绝对路径情形）。"""
    p = Path(str(name))
    if p.name.startswith(("problem_", "all_results", "fig_data", "data_check",
                          "constraint_audit", "cross_problem_check")):
        return _orig(obj, str(FIG / p.name), *a, **k)
    if not p.is_absolute() and str(p).startswith("figures/"):
        return _orig(obj, str(FIG / p.name), *a, **k)
    return _orig(obj, name, *a, **k)


u.save_json = _save_json


def main():
    res = problem2.run()
    print("=" * 64)
    print("问题二（SAA 情景随机优化 + 因果反馈）复现结果")
    print("=" * 64)
    print(f"  规划天数            {res['n_days']:>14d} 天（{res['eval_start']} 起）")
    print(f"  全年总费用          {res['total_cost_yuan']:>14,.2f} 元")
    print(f"  计划购电费          {res['plan_cost_yuan']:>14,.2f} 元")
    print(f"  紧急购电费          {res['emergency_cost_yuan']:>14,.2f} 元")
    print(f"  紧急购电量 / 弃光量 {res['emergency_qty_kWh']:>12,.2f} / {res['curtail_qty_kWh']:,.2f} kWh")
    print(f"  SOC 区间            [{res['soc_min_kWh']:,.2f}, {res['soc_max_kWh']:,.2f}] kWh"
          f"（期末 {res['E_final_kWh']:,.2f}）")
    print(f"  负载预测 MAE        {res['load_forecast_mae_kW']:>14,.2f} kW")
    print(f"  场景数 K / 权重     {res['K_scenarios']} / {res['scenario_weight']}")
    print(f"  备用搜索期望费用    {res['saa_cost_init']:,.2f} → {res['saa_cost_opt']:,.2f} 元")
    print("-" * 64)
    print(f"  结果已写入 {FIG / 'problem_2_results.json'}")


if __name__ == "__main__":
    main()
