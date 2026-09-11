# -*- coding: utf-8 -*-
"""问题四运行入口：波动电价下沿用问题二/三信息结构重解（4-2 与 4-3 两个子问题）。

独立运行（不依赖工作区）：
    D:\\project\\pythonProject\\2026CN-MCM\\.venv\\Scripts\\python.exe run_q4.py

依赖：code/params.py、code/utils.py、code/problem4.py（本地拷贝）
      code/problem2.py、code/problem3.py —— 问题四直接复用问题二/三的求解函数
输入：user_data/附件1..4.xlsx        输出：figures/problem_4_results.json
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

import problem4                                                        # noqa: E402
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
    res = problem4.run()
    a, b = res["result_4_2"], res["result_4_3"]
    print("=" * 64)
    print("问题四（波动电价下沿用问题二/三框架）复现结果")
    print("=" * 64)
    print(f"  4-2（问题二信息结构）全年总费用 {a['total_cost_yuan']:>16,.2f} 元")
    print(f"       计划购电费 {a['plan_cost_yuan']:>14,.2f} / 紧急购电费 {a['emergency_cost_yuan']:,.2f} 元")
    print(f"       紧急购电量 {a['emergency_qty_kWh']:>14,.2f} kWh")
    print(f"  4-3（问题三信息结构）全年总费用 {b['total_cost_yuan']:>16,.2f} 元")
    print(f"       计划承诺费 {b['base_commit_cost_yuan']:>14,.2f} / 增购费 {b['over_adjust_cost_yuan']:,.2f}"
          f" / 紧急费 {b['emergency_cost_yuan']:,.2f} 元")
    print(f"       预报价值 VoF 省 {b['vof']['vof_full_yuan']:>13,.2f} 元")
    ps = res["price_stats"]
    print(f"  波动电价            均值 {ps['volatile_mean']}，区间 [{ps['volatile_min']}, {ps['volatile_max']}]")
    print(f"  附件1 模板电价       均值 {ps['template_mean']}，区间 [{ps['template_min']}, {ps['template_max']}]")
    print("-" * 64)
    print(f"  结果已写入 {FIG / 'problem_4_results.json'}")


if __name__ == "__main__":
    main()
