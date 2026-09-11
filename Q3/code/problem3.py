# -*- coding: utf-8 -*-
"""问题3：多阶段滚动 SMPC，在预报节点 {0,6,12,18} 重解剩余时域；日内调整按非对称结算。

M6：滚动重解(re-solve/re-optimize)——节点 h∈{0,6,12,18} 用该刻及更早发布的附件3光伏预报
    更新剩余时域计划（certainty-equivalent rolling MPC）。
M7：调整结算(13) C_t = p_t[q^0 + 1.5*a_t + (0.5-rho)*b_t + 5*e_t]，a=增购超出、b=减购违约，
    退费开关 rho 主口径=0（附录敏感性 rho=1）。1.5 增购、0.5 违约倍率来自题面。
M8：预报价值(VoF) 实验——2**3=8 种节点启用组合，量化滚动预报的信息价值。
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import linprog
import utils as u
import params as p

NODE_INTERVALS = tuple(h * (60 // p.INTERVAL_MINUTES) for h in p.ISSUE_HOURS)  # {0,36,72,108}


def node_pv_forecast(rolling, date, issue_h, pv_mat, day_idx):
    """构造节点 h 视角的当日 144 区间光伏预报：未来段用附件3该发布时刻预报插值，
    过去段用近7日同刻均值兜底（重解只用未来段，过去段不影响）。缺预报则整日退回7日均值。"""
    base = u.forecast_pv(pv_mat, day_idx)                 # 近7日同刻均值兜底
    key = (date, issue_h)
    if key not in rolling:
        return base
    hourly = rolling[key]                                 # 未来 24 整点(h+1..h+24)
    n = p.INTERVALS_PER_DAY
    x_new = (np.arange(1, n + 1)) * p.INTERVAL_HOURS      # 各区间末端小时
    x_src = issue_h + np.arange(1, len(hourly) + 1)       # h+1..h+24
    fc = np.interp(x_new, x_src, hourly, left=hourly[0], right=hourly[-1])
    fc = np.maximum(fc, 0.0)
    node = issue_h * (60 // p.INTERVAL_MINUTES)
    out = base.copy()
    out[node:] = fc[node:]
    return out


def solve_resolve_lp(price, load_fc, pv_fc, E0, q0_ref, start, terminal_value, rho):
    """重解剩余时域 [start,144)：q_t = q0_ref_t + a_t - b_t，按(13)结算调整。
    决策 x=[q,a,b,c,d,e,w] 各长度 m=144-start。目标含 1.5p*a+(0.5-rho)p*b+5p*e - λ*E_end。"""
    n = p.INTERVALS_PER_DAY
    m = n - start
    dt = p.INTERVAL_HOURS
    cap = p.MAX_ENERGY_PER_INTERVAL_KWH
    eta = p.ETA
    lo, hi = p.SOC_BOUNDS
    pr = price[start:]
    net_e = (load_fc[start:] - pv_fc[start:]) * dt
    qref = q0_ref[start:]
    I = np.eye(m); Z = np.zeros((m, m)); Ltri = np.tril(np.ones((m, m)))

    # 目标系数（q 本身不计价，计划费 p*q0_ref 为常数；调整/紧急计价 + 终端价值）
    cq = np.zeros(m)
    ca = p.OVER_ADJUST_MULT * pr
    cb = (p.BREACH_MULT - rho) * pr
    cc = -terminal_value * eta * np.ones(m)
    cd = terminal_value / eta * np.ones(m)
    ce = p.EMERGENCY_MULT * pr
    cw = np.zeros(m)
    cost = np.concatenate([cq, ca, cb, cc, cd, ce, cw])

    # 等式1：q - a + b = qref（调整拆分）; 等式2：q - c + d + e - w = net_e（供需平衡）
    A_eq = np.vstack([
        np.hstack([I, -I, I, Z, Z, Z, Z]),
        np.hstack([I, Z, Z, -I, I, I, -I]),
    ])
    b_eq = np.concatenate([qref, net_e])

    # SOC 累计上下界
    delta = np.hstack([Z, Z, Z, eta * Ltri, -Ltri / eta, Z, Z])
    A_ub = np.vstack([delta, -delta])
    b_ub = np.concatenate([np.full(m, hi - E0), np.full(m, E0 - lo)])

    bounds = ([(0, None)] * m + [(0, None)] * m + [(0, None)] * m
              + [(0, cap)] * m + [(0, cap)] * m + [(0, None)] * m + [(0, None)] * m)
    res = linprog(cost, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if not res.success:
        raise RuntimeError(f"resolve LP infeasible @start={start}: {res.message}")
    x = res.x
    q = x[:m]
    return q
def _execute_slice(q_com, load, pv, price, E0, lo_idx, hi_idx):
    """在实际数据上对区间 [lo_idx,hi_idx) 执行因果反馈控制（电网购电 q 固定为已承诺值，
    电池按真实净负荷反应，越限转紧急购电/弃光），返回期末 SOC 与逐区间 e,c,d,w。"""
    cap = p.MAX_ENERGY_PER_INTERVAL_KWH
    eta = p.ETA
    lo, hi = p.SOC_BOUNDS
    dt = p.INTERVAL_HOURS
    Eprev = E0
    e = np.zeros(hi_idx - lo_idx); c = np.zeros_like(e)
    d = np.zeros_like(e); w = np.zeros_like(e); Etr = np.zeros_like(e)
    for j, t in enumerate(range(lo_idx, hi_idx)):
        avail = q_com[t] + pv[t] * dt
        net = load[t] * dt - avail
        if net > 0:
            dmax = min(cap, max((Eprev - lo) * eta, 0.0))
            d[j] = min(net, dmax)
            short = net - d[j]
            if short > 1e-9:
                e[j] = short
            Eprev = Eprev - d[j] / eta
        else:
            surplus = -net
            cmax = min(cap, max((hi - Eprev) / eta, 0.0))
            c[j] = min(surplus, cmax)
            w[j] = surplus - c[j]
            Eprev = Eprev + eta * c[j]
        Etr[j] = Eprev
    return {"E_end": Eprev, "e": e, "c": c, "d": d, "w": w, "E": Etr}


def simulate_day_smpc(rolling, date, load_fc0, pv_mat, day_idx, load_act, pv_act, price,
                      E0, lam, rho, active_nodes, settlement_price=None):
    """单日滚动 SMPC：节点0日前解得基准承诺 q0；在 active_nodes(∈{6,12,18}) 处用该刻附件3
    预报重解剩余时域并更新承诺 q_com；全程对真实数据反应式执行电池/紧急购电。
    price 只用于节点优化；settlement_price 只用于事后结算。未单独给结算价时二者相同，
    因而问题三原口径完全不变。结算按(13)：C=Σ p_settle*(q0 + 1.5a +
    (0.5-ρ)b + 5e)，a=max(q_com-q0,0)、b=max(q0-q_com,0)。"""
    n = p.INTERVALS_PER_DAY
    pv_fc0 = u.forecast_pv(pv_mat, day_idx)
    lp0 = u.solve_daily_lp(price, load_fc0, pv_fc0, E0,
                           terminal_mode="value", terminal_value=lam)
    q0 = lp0["q"].copy()
    q_com = q0.copy()

    ex = {"e": np.zeros(n), "c": np.zeros(n), "d": np.zeros(n), "w": np.zeros(n), "E": np.zeros(n)}
    Ecur = E0
    pos = 0
    for h in p.ISSUE_HOURS:
        if h == 0:
            continue
        node = h * (60 // p.INTERVAL_MINUTES)
        if h in active_nodes:
            seg = _execute_slice(q_com, load_act, pv_act, price, Ecur, pos, node)
            for kk in ("e", "c", "d", "w", "E"):
                ex[kk][pos:node] = seg[kk]
            Ecur = seg["E_end"]
            pos = node
            pv_fc = node_pv_forecast(rolling, date, h, pv_mat, day_idx)
            q_new = solve_resolve_lp(price, load_fc0, pv_fc, Ecur, q0, node, lam, rho)
            q_com[node:] = q_new
    seg = _execute_slice(q_com, load_act, pv_act, price, Ecur, pos, n)
    for kk in ("e", "c", "d", "w", "E"):
        ex[kk][pos:n] = seg[kk]
    E_end = seg["E_end"]

    settle = price if settlement_price is None else np.asarray(settlement_price, dtype=float)
    if settle.shape != price.shape:
        raise ValueError("settlement_price 与 price 必须具有相同的 144 点形状")
    a = np.maximum(q_com - q0, 0.0)
    b = np.maximum(q0 - q_com, 0.0)
    e = ex["e"]
    base_cost = float(np.sum(settle * q0))
    over_cost = float(np.sum(p.OVER_ADJUST_MULT * settle * a))
    breach_cost = float(np.sum((p.BREACH_MULT - rho) * settle * b))
    emg_cost = float(np.sum(p.EMERGENCY_MULT * settle * e))
    total = base_cost + over_cost + breach_cost + emg_cost
    return {"q0": q0, "q_com": q_com, "a": a, "b": b, "e": e, "c": ex["c"],
            "d": ex["d"], "w": ex["w"], "E": ex["E"], "E_end": E_end,
            "base_cost": base_cost, "over_cost": over_cost, "breach_cost": breach_cost,
            "emergency_cost": emg_cost, "total_cost": total,
            "adjust_up_kWh": float(np.sum(a)), "adjust_down_kWh": float(np.sum(b)),
            "emergency_qty": float(np.sum(e)), "curtail_qty": float(np.sum(ex["w"]))}
def run_year(data, model, rolling, plan_days, active_nodes, rho, store_series=False,
             settlement_price=None):
    """全年滚动 SMPC：跨日传递真实期末 SOC，聚合费用与偏差量。

    data['price'] 是决策时可见的预测价；settlement_price 是事后结算价矩阵。
    后者省略时沿用 data['price']，以保持问题三及既有调用的行为不变。
    """
    load, pv, price, dates = data["load"], data["pv"], data["price"], data["dates"]
    lam = u.estimate_terminal_value(price)
    settle_mat = price if settlement_price is None else np.asarray(settlement_price, dtype=float)
    if settle_mat.shape != price.shape:
        raise ValueError("settlement_price 与 data['price'] 必须具有相同形状")
    E0 = p.INIT_SOC_KWH
    agg = {"base_cost": 0.0, "over_cost": 0.0, "breach_cost": 0.0, "emergency_cost": 0.0,
           "total_cost": 0.0, "adjust_up_kWh": 0.0, "adjust_down_kWh": 0.0,
           "emergency_qty": 0.0, "curtail_qty": 0.0}
    soc_min, soc_max = np.inf, -np.inf
    daily, series = [], {"q0": [], "q_com": [], "a": [], "b": [],
                         "c": [], "d": [], "e": [], "E": []}
    for d in plan_days:
        load_fc0 = u.forecast_load(load, d, model)
        r = simulate_day_smpc(rolling, dates[d], load_fc0, pv, d, load[d], pv[d],
                              price[d], E0, lam, rho, active_nodes,
                              settlement_price=settle_mat[d])
        for k in agg:
            agg[k] += r[k]
        soc_min = min(soc_min, r["E"].min()); soc_max = max(soc_max, r["E"].max())
        daily.append({"date": dates[d], "total_cost": round(r["total_cost"], 2),
                      "over_cost": round(r["over_cost"], 2), "breach_cost": round(r["breach_cost"], 2),
                      "emergency_cost": round(r["emergency_cost"], 2),
                      "adjust_up_kWh": round(r["adjust_up_kWh"], 2),
                      "adjust_down_kWh": round(r["adjust_down_kWh"], 2),
                      "emergency_qty": round(r["emergency_qty"], 2), "E_end": round(r["E_end"], 2)})
        if store_series:
            for kk in ("q0", "q_com", "a", "b", "c", "d", "e", "E"):
                series[kk].append(r[kk].tolist())
        E0 = r["E_end"]
    out = {**{k: agg[k] for k in agg}, "soc_min": soc_min, "soc_max": soc_max,
           "E_final": E0, "daily": daily, "lam": lam}
    if store_series:
        out["series"] = series
    return out


def value_of_forecast(data, model, rolling, plan_days, rho, settlement_price=None):
    """VoF 实验：2**3=8 种 {6,12,18} 节点启用组合，量化滚动预报信息价值（相对全关基线）。"""
    combos = []
    for mask in range(8):
        nodes = tuple(h for i, h in enumerate((6, 12, 18)) if (mask >> i) & 1)
        yr = run_year(data, model, rolling, plan_days, nodes, rho, store_series=False,
                      settlement_price=settlement_price)
        combos.append({"nodes": list(nodes), "n_nodes": len(nodes),
                       "total_cost": round(yr["total_cost"], 2),
                       "emergency_cost": round(yr["emergency_cost"], 2),
                       "emergency_qty": round(yr["emergency_qty"], 2),
                       "adjust_up_kWh": round(yr["adjust_up_kWh"], 2),
                       "adjust_down_kWh": round(yr["adjust_down_kWh"], 2)})
    base = next(c for c in combos if c["n_nodes"] == 0)["total_cost"]
    full = next(c for c in combos if c["n_nodes"] == 3)["total_cost"]
    for c in combos:
        c["vof_savings_yuan"] = round(base - c["total_cost"], 2)
    return {"combos": combos, "baseline_no_node_cost": round(base, 2),
            "all_node_cost": round(full, 2), "vof_full_yuan": round(base - full, 2)}


def validate_capability(res):
    """能力项落地校验（P3：滚动重解降本、结算(13)量纲、SOC 界；不达标即 raise）。"""
    assert res["emergency_qty_kWh"] >= -1e-6, "紧急购电量非负"
    assert res["adjust_up_kWh"] >= -1e-6 and res["adjust_down_kWh"] >= -1e-6, "调整量非负"
    assert res["soc_min_kWh"] >= p.SOC_MIN_KWH - 1.0, "SOC 下界越界"
    assert res["soc_max_kWh"] <= p.SOC_MAX_KWH + 1.0, "SOC 上界越界"
    assert res["vof"]["all_node_cost"] <= res["vof"]["baseline_no_node_cost"] + 1e-6, \
        "P3-C2：全节点滚动未改善或持平于无节点基线（预报价值应≥0）"


def run(save=True):
    u.set_all_seeds()
    data = u.load_annual()
    rolling = u.load_pv_forecast_rolling()
    plan_days = u.find_plan_days(data["dates"])
    warmup = range(0, plan_days.start)
    model = u.fit_load_forecaster(data["load"], warmup)
    rho = p.RHO_REFUND

    main = run_year(data, model, rolling, plan_days, (6, 12, 18), rho, store_series=True)
    vof = value_of_forecast(data, model, rolling, plan_days, rho)

    res = {
        "problem": 3,
        "n_days": len(plan_days),
        "eval_start": data["dates"][plan_days.start],
        "rho_refund": rho,
        "issue_hours": list(p.ISSUE_HOURS),
        "total_cost_yuan": round(main["total_cost"], 2),
        "base_commit_cost_yuan": round(main["base_cost"], 2),
        "over_adjust_cost_yuan": round(main["over_cost"], 2),
        "breach_cost_yuan": round(main["breach_cost"], 2),
        "emergency_cost_yuan": round(main["emergency_cost"], 2),
        "adjust_up_kWh": round(main["adjust_up_kWh"], 2),
        "adjust_down_kWh": round(main["adjust_down_kWh"], 2),
        "emergency_qty_kWh": round(main["emergency_qty"], 2),
        "curtail_qty_kWh": round(main["curtail_qty"], 2),
        "soc_min_kWh": round(main["soc_min"], 2),
        "soc_max_kWh": round(main["soc_max"], 2),
        "E_final_kWh": round(main["E_final"], 2),
        "terminal_value_yuan_per_kWh": round(main["lam"], 4),
        "vof": vof,
    }
    date2row = {row["date"]: row for row in main["daily"]}
    res["eval_days"] = {d: date2row.get(d) for d in p.EVAL_DATES if d in date2row}
    validate_capability(res)
    if save:
        u.save_json({**res, "daily": main["daily"], "series": main["series"]},
                    "figures/problem_3_results.json")
    return res


if __name__ == "__main__":
    import time
    t0 = time.time()
    r = run()
    print(f"问题3完成（{time.time()-t0:.1f}s）：",
          {k: v for k, v in r.items() if k not in ("eval_days", "vof")})
    print("  VoF：", {"baseline": r["vof"]["baseline_no_node_cost"],
                      "all_node": r["vof"]["all_node_cost"], "saved": r["vof"]["vof_full_yuan"]})
    print("  考察日：", r["eval_days"])
