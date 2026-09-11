# -*- coding: utf-8 -*-
"""问题2：因果预测 + 情景随机优化(SAA) + 因果反馈控制，全年 334 天跨日连续运行。

M3：块自助生成 K 个等权场景(pi_k = 1/K)，在场景上搜索备用策略 r_t(6 段 4 小时)，
    最小化期望费用（计划购电 + 期望紧急购电）。备用策略跨场景共用，不逐场景开天眼。
M4：负载=上周同刻+Ridge 校正；光伏=近7日同刻均值（见 utils，纯因果无泄漏）。
M5：供电缺口紧急购电 e_t，按交易时刻电价 5 倍结算。

三段式（解耦以保证 334 天 × 策略搜索可算）：
  A 名义：逐日 LP(备用=0) + 真实回放 → 基准计划 q0_base、名义跨日 SOC。
  B 调参：残差块自助场景上，Nelder-Mead 搜 6 段备用，最小化 SAA 期望费用（报童分位初始化）。
  C 终评：带最优备用逐日真实回放，跨日传递真实期末 SOC，产出全年结果。
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import minimize
import utils as u
import params as p


def seg_broadcast(seg_vals: np.ndarray) -> np.ndarray:
    """把 6 段 4 小时备用值广播到 144 区间。"""
    per_seg = p.INTERVALS_PER_DAY // p.N_RESERVE_SEG
    return np.repeat(seg_vals, per_seg)


def newsvendor_reserve(residuals: np.ndarray) -> np.ndarray:
    """报童分位初始化：每 4 小时段取正残差(欠预测)的 F* 分位作备用(kW)。"""
    per_seg = p.INTERVALS_PER_DAY // p.N_RESERVE_SEG
    r = np.zeros(p.N_RESERVE_SEG)
    for s in range(p.N_RESERVE_SEG):
        block = residuals[:, s * per_seg:(s + 1) * per_seg].ravel()
        r[s] = max(np.quantile(block, p.NEWSVENDOR_QUANTILE), 0.0)
    return r


def phase_a_nominal(data, model, plan_days):
    """名义段：逐日 LP(备用=0)+真实回放，跨日传递真实期末 SOC。"""
    load, pv, price = data["load"], data["pv"], data["price"]
    lam = u.estimate_terminal_value(price)
    q0_base, base_net, E0_list, day_price, day_load, day_pv = [], [], [], [], [], []
    E0 = p.INIT_SOC_KWH
    for d in plan_days:
        load_fc = u.forecast_load(load, d, model)
        pv_fc = u.forecast_pv(pv, d)
        lp = u.solve_daily_lp(price[d], load_fc, pv_fc, E0,
                              terminal_mode="value", terminal_value=lam)
        q0_base.append(lp["q"])
        base_net.append(load_fc - pv_fc)
        E0_list.append(E0)
        day_price.append(price[d]); day_load.append(load[d]); day_pv.append(pv[d])
        rep = u.replay_day(lp["q"], load[d], pv[d], E0, price[d])   # 真实回放取期末 SOC
        E0 = rep["E_end"]
    return {"q0_base": np.array(q0_base), "base_net": np.array(base_net),
            "E0": np.array(E0_list), "price": np.array(day_price),
            "load": np.array(day_load), "pv": np.array(day_pv), "lam": lam}
def expected_cost_saa(seg_vals, nominal, scen_by_day, rng_days):
    """SAA 期望费用：对抽样日，将备用加进计划后在 K 个等权场景上回放取均值。
    pi_k = 1/K，等权聚合。返回标量期望总费用。"""
    dt = p.INTERVAL_HOURS
    r_kw = seg_broadcast(np.maximum(seg_vals, 0.0))
    r_e = r_kw * dt
    pi_k = 1.0 / p.N_SCENARIOS
    total = 0.0
    for d in rng_days:
        q0 = nominal["q0_base"][d] + r_e
        costs = u.replay_scenarios(q0, scen_by_day[d], nominal["base_net"][d],
                                   nominal["pv"][d], nominal["E0"][d], nominal["price"][d])
        total += pi_k * float(np.sum(costs))       # 等权求和 = K*mean
    return total / len(rng_days)


def search_reserve(nominal, residuals, plan_len):
    """在残差块自助场景上搜 6 段备用；报童分位初始化 + Nelder-Mead 精调。"""
    rng = np.random.default_rng(p.SEED)
    # 为每个抽样日预生成 K 场景（净负荷扰动）
    sample_days = np.linspace(0, plan_len - 1, min(plan_len, 40)).astype(int)
    sample_days = np.unique(sample_days)
    scen_by_day = {int(d): u.block_bootstrap_scenarios(residuals, p.N_SCENARIOS, rng)
                   for d in sample_days}
    r0 = newsvendor_reserve(residuals)
    obj = lambda s: expected_cost_saa(s, nominal, scen_by_day, sample_days)
    res = minimize(obj, r0, method="Nelder-Mead",
                   options={"maxiter": 300, "xatol": 1.0, "fatol": 1.0})
    r_opt = np.maximum(res.x, 0.0)
    return {"r_seg_kw": r_opt.tolist(), "r_init_kw": r0.tolist(),
            "saa_cost_init": round(obj(r0), 2), "saa_cost_opt": round(obj(r_opt), 2),
            "n_sample_days": int(len(sample_days))}


def phase_c_final(nominal, r_seg, data, plan_days):
    """终评：带最优备用逐日真实回放，跨日传递真实期末 SOC。"""
    dt = p.INTERVAL_HOURS
    r_e = seg_broadcast(np.maximum(np.array(r_seg), 0.0)) * dt
    load, pv, price = data["load"], data["pv"], data["price"]
    E0 = p.INIT_SOC_KWH
    tot_plan = tot_emg = tot_e = tot_w = 0.0
    soc_min, soc_max = np.inf, -np.inf
    daily = []
    q0_all, c_all, d_all, e_all, E_all = [], [], [], [], []
    for i, d in enumerate(plan_days):
        q0 = nominal["q0_base"][i] + r_e
        rep = u.replay_day(q0, load[d], pv[d], E0, price[d])
        tot_plan += rep["plan_cost"]; tot_emg += rep["emergency_cost"]
        tot_e += rep["emergency_qty"]; tot_w += float(np.sum(rep["w"]))
        soc_min = min(soc_min, rep["E"].min()); soc_max = max(soc_max, rep["E"].max())
        daily.append({"date": data["dates"][d], "plan_cost": round(rep["plan_cost"], 2),
                      "emergency_cost": round(rep["emergency_cost"], 2),
                      "emergency_qty": round(rep["emergency_qty"], 2),
                      "E_end": round(rep["E_end"], 2)})
        q0_all.append(q0.tolist()); c_all.append(rep["c"].tolist())
        d_all.append(rep["d"].tolist()); e_all.append(rep["e"].tolist())
        E_all.append(rep["E"].tolist())
        E0 = rep["E_end"]
    return {"total_cost": tot_plan + tot_emg, "plan_cost": tot_plan, "emergency_cost": tot_emg,
            "emergency_qty": tot_e, "curtail_qty": tot_w, "soc_min": soc_min, "soc_max": soc_max,
            "daily": daily, "E_final": E0,
            "series": {"q0": q0_all, "c": c_all, "d": d_all, "e": e_all, "E": E_all}}
def validate_capability(res):
    """P2-C2：紧急购电按 5 倍电价结算（隐含于 replay，此处核对量纲与非负）。"""
    assert res["emergency_qty_kWh"] >= -1e-6, "紧急购电量非负"
    assert res["soc_min_kWh"] >= p.SOC_MIN_KWH - 1.0, "SOC 下界越界"
    assert res["soc_max_kWh"] <= p.SOC_MAX_KWH + 1.0, "SOC 上界越界"
    assert res["saa_cost_opt"] <= res["saa_cost_init"] + 1e-6, "策略搜索未改善或持平期望费用"


def run(save=True):
    u.set_all_seeds()
    data = u.load_annual()
    plan_days = u.find_plan_days(data["dates"])
    warmup = range(0, plan_days.start)
    model = u.fit_load_forecaster(data["load"], warmup)

    nominal = phase_a_nominal(data, model, plan_days)
    residuals = u.build_net_residuals(data["load"], data["pv"], model, plan_days)
    search = search_reserve(nominal, residuals, len(plan_days))
    final = phase_c_final(nominal, search["r_seg_kw"], data, plan_days)

    # 预测精度（诊断，非泄漏）
    load_mae = float(np.mean([np.mean(np.abs(u.forecast_load(data["load"], d, model) - data["load"][d]))
                              for d in plan_days]))
    res = {
        "problem": 2,
        "n_days": len(plan_days),
        "eval_start": data["dates"][plan_days.start],
        "total_cost_yuan": round(final["total_cost"], 2),
        "plan_cost_yuan": round(final["plan_cost"], 2),
        "emergency_cost_yuan": round(final["emergency_cost"], 2),
        "emergency_qty_kWh": round(final["emergency_qty"], 2),
        "curtail_qty_kWh": round(final["curtail_qty"], 2),
        "soc_min_kWh": round(final["soc_min"], 2),
        "soc_max_kWh": round(final["soc_max"], 2),
        "E_final_kWh": round(final["E_final"], 2),
        "terminal_value_yuan_per_kWh": round(nominal["lam"], 4),
        "K_scenarios": p.N_SCENARIOS,
        "scenario_weight": round(p.SCENARIO_WEIGHT, 6),
        "reserve_seg_kw": [round(x, 2) for x in search["r_seg_kw"]],
        "saa_cost_init": search["saa_cost_init"],
        "saa_cost_opt": search["saa_cost_opt"],
        "load_forecast_mae_kW": round(load_mae, 2),
    }
    # 4 个考察日明细
    date2row = {row["date"]: row for row in final["daily"]}
    res["eval_days"] = {d: date2row.get(d) for d in p.EVAL_DATES if d in date2row}
    validate_capability(res)
    if save:
        u.save_json({**res, "daily": final["daily"], "series": final["series"]},
                    "figures/problem_2_results.json")
    return res


if __name__ == "__main__":
    import time
    t0 = time.time()
    r = run()
    print(f"问题2完成（{time.time()-t0:.1f}s）：",
          {k: v for k, v in r.items() if k not in ("eval_days",)})
    print("  考察日：", r["eval_days"])


