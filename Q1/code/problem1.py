# -*- coding: utf-8 -*-
"""问题1：典型日确定性 LP 调度 + 显式互斥 MILP 交叉校验。

M1：scipy.optimize.linprog(method='highs') 求全局最优（全时域联合优化，非逐点启发式）。
M2：PuLP + PULP_CBC_CMD，引入 0-1 变量 z_t 与 big-M(=每区间电量上界 833.33) 显式禁止
    同区间同时充放，验证 LP 最优与 MILP 最优一致（cost_LP ≈ cost_MILP，rel_gap ≤ 0.02）。
"""
from __future__ import annotations
import numpy as np
import pulp
import utils as u
import params as p


def solve_milp_mutex(price, load, pv, E0, terminal_soc):
    """显式互斥 MILP：z_t=1 允许充电、z_t=0 允许放电，big-M 关断另一侧。"""
    n = len(price)
    dt = p.INTERVAL_HOURS
    cap = p.MAX_ENERGY_PER_INTERVAL_KWH        # big-M = 833.33 kWh/区间
    eta = p.ETA
    lo, hi = p.SOC_BOUNDS
    net_e = (load - pv) * dt

    prob = pulp.LpProblem("Q1_mutex", pulp.LpMinimize)
    q = [pulp.LpVariable(f"q{t}", lowBound=0) for t in range(n)]
    c = [pulp.LpVariable(f"c{t}", lowBound=0, upBound=cap) for t in range(n)]
    d = [pulp.LpVariable(f"d{t}", lowBound=0, upBound=cap) for t in range(n)]
    e = [pulp.LpVariable(f"e{t}", lowBound=0) for t in range(n)]
    w = [pulp.LpVariable(f"w{t}", lowBound=0) for t in range(n)]
    z = [pulp.LpVariable(f"z{t}", cat=pulp.LpBinary) for t in range(n)]
    E = [pulp.LpVariable(f"E{t}", lowBound=lo, upBound=hi) for t in range(n)]

    prob += pulp.lpSum(price[t] * q[t] + p.EMERGENCY_MULT * price[t] * e[t] for t in range(n))
    for t in range(n):
        prob += q[t] + e[t] + d[t] - c[t] - w[t] == net_e[t]     # 供需平衡
        prob += c[t] <= cap * z[t]                                # big-M 互斥：充电侧
        prob += d[t] <= cap * (1 - z[t])                          # big-M 互斥：放电侧
        prev = E0 if t == 0 else E[t - 1]
        prob += E[t] == prev + eta * c[t] - d[t] / eta            # 状态方程
    prob += E[n - 1] == terminal_soc                              # 期末闭合
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    status = pulp.LpStatus[prob.status]
    cval = np.array([v.value() for v in c])
    dval = np.array([v.value() for v in d])
    return {"status": status, "objective": float(pulp.value(prob.objective)),
            "c": cval, "d": dval,
            "simul_cd": int(np.sum((cval > 1e-6) & (dval > 1e-6)))}


def validate_constraints(sol, price, load, pv, E0):
    """硬约束体检（越界即 raise）：供需平衡/SOC/功率/闭合/无同充放。"""
    dt = p.INTERVAL_HOURS
    eta = p.ETA
    lo, hi = p.SOC_BOUNDS
    cap = p.MAX_ENERGY_PER_INTERVAL_KWH
    q, c, d, e, w, E = sol["q"], sol["c"], sol["d"], sol["e"], sol["w"], sol["E"]
    bal = q + e + d - c - w - (load - pv) * dt
    assert np.max(np.abs(bal)) < 1e-4, f"供需平衡违反 max={np.max(np.abs(bal)):.2e}"
    assert E.min() >= lo - 1e-6 and E.max() <= hi + 1e-6, "SOC 越界"
    assert c.max() <= cap + 1e-6 and d.max() <= cap + 1e-6, "功率上界越界"
    assert c.min() >= -1e-6 and d.min() >= -1e-6 and q.min() >= -1e-6, "非负性违反"
    assert abs(E[-1] - E0) < 1e-3, f"期末未闭合 E_end={E[-1]:.3f}"
    assert np.sum((c > 1e-6) & (d > 1e-6)) == 0, "存在同区间同时充放"
    recon = E0 + np.cumsum(eta * c - d / eta)
    assert np.max(np.abs(recon - E)) < 1e-4, "状态方程重构不符"


def validate_capability(res):
    """能力项落地校验（P1-C1 全局最优、P1-C3 无同时充放；不达标即 raise）。"""
    assert res["cost_lp_vs_milp_rel_gap"] <= 0.02, "P1-C1：LP 与 MILP 最优不一致"
    assert res["simul_charge_discharge_intervals"] == 0, "P1-C3：存在同时充放"
    assert res["curtail_kWh"] >= -1e-6, "弃光量非负"
    assert res["emergency_kWh"] < 1e-6, "问题1供给应满足负载，无需紧急购电"


def run():
    u.set_all_seeds()
    td = u.load_typical_day()
    price, load, pv = td["price"], td["load"], td["pv_forecast"]
    E0 = p.INIT_SOC_KWH

    lp = u.solve_daily_lp(price, load, pv, E0, terminal_mode="closure", terminal_soc=E0)
    validate_constraints(lp, price, load, pv, E0)
    milp = solve_milp_mutex(price, load, pv, E0, E0)

    dt = p.INTERVAL_HOURS
    baseline = float(np.sum(price * np.maximum(load - pv, 0.0) * dt))
    denom = max(abs(lp["total_cost"]), 1e-9)
    rel_gap = abs(lp["total_cost"] - milp["objective"]) / denom

    res = {
        "problem": 1,
        "total_cost_yuan": round(lp["total_cost"], 2),
        "plan_cost_yuan": round(lp["plan_cost"], 2),
        "emergency_cost_yuan": round(lp["emergency_cost"], 2),
        "purchase_kWh": round(float(np.sum(lp["q"])), 2),
        "charge_kWh": round(float(np.sum(lp["c"])), 2),
        "discharge_kWh": round(float(np.sum(lp["d"])), 2),
        "curtail_kWh": round(float(np.sum(lp["w"])), 2),
        "emergency_kWh": round(float(np.sum(lp["e"])), 4),
        "E_start": round(E0, 2), "E_end": round(lp["E_end"], 2),
        "soc_min": round(float(lp["E"].min()), 2), "soc_max": round(float(lp["E"].max()), 2),
        "baseline_cost_yuan": round(baseline, 2),
        "savings_yuan": round(baseline - lp["total_cost"], 2),
        "savings_pct": round(100 * (baseline - lp["total_cost"]) / baseline, 2),
        "milp_objective_yuan": round(milp["objective"], 2),
        "milp_status": milp["status"],
        "cost_lp_vs_milp_rel_gap": round(rel_gap, 6),
        "simul_charge_discharge_intervals": milp["simul_cd"],
    }
    validate_capability(res)
    # 逐区间序列（供作图与 Excel 填写）
    series = {"q": lp["q"].tolist(), "c": lp["c"].tolist(), "d": lp["d"].tolist(),
              "e": lp["e"].tolist(), "w": lp["w"].tolist(), "E": lp["E"].tolist(),
              "price": price.tolist(), "load": load.tolist(), "pv": pv.tolist()}
    u.save_json({**res, "series": series}, "figures/problem_1_results.json")
    return res


if __name__ == "__main__":
    r = run()
    print("问题1完成：", {k: v for k, v in r.items() if k != "series"})
