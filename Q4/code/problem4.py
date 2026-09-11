# -*- coding: utf-8 -*-
"""问题4：预测价决策、真实波动价结算。

每天 0:00 及日内滚动节点只能看到附件1给出的 144 点分时骨架价；附件4当天真实
波动价绝不进入优化器，仅在计划执行完毕后用于费用结算。另设“先知真价”对照组，
只用于估计价格信息价值，不作为正式 4-2/4-3 策略。
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import utils as u
import params as p
import problem2 as q2
import problem3 as q3


def _price_data(data, price_matrix):
    """返回独立的浅拷贝，并显式替换决策阶段可见的电价矩阵。"""
    d = dict(data)
    d["price"] = np.asarray(price_matrix, dtype=float)
    return d


def analyze_price_structure(data, plan_days):
    """事后统计价格结构；统计结果不回流到任何日的优化决策。"""
    skeleton = np.asarray(data["price"][0], dtype=float)
    actual = np.asarray(data["price_volatile"], dtype=float)
    slot_mean = np.mean(actual, axis=0)
    ratio_residual = actual / skeleton - 1.0
    daily_spread = np.max(actual, axis=1) - np.min(actual, axis=1)
    eval_actual = actual[plan_days.start:plan_days.stop]
    return {
        "model": "actual_price = skeleton_price * (1 + relative_residual)",
        "slot_mean_vs_skeleton_corr": round(float(np.corrcoef(slot_mean, skeleton)[0, 1]), 8),
        "relative_residual_mean": round(float(np.mean(ratio_residual)), 8),
        "relative_residual_std": round(float(np.std(ratio_residual)), 8),
        "daily_peak_valley_spread_mean_yuan_per_kWh": round(float(np.mean(daily_spread)), 8),
        "price_below_0_2_share_pct": round(float(100 * np.mean(actual < 0.2)), 8),
        "forecast_mae_yuan_per_kWh": round(float(np.mean(np.abs(eval_actual - skeleton))), 8),
        "forecast_max_abs_error_yuan_per_kWh": round(float(np.max(np.abs(eval_actual - skeleton))), 8),
        "forecast_eval_days": len(plan_days),
    }


def run_4_2(data, model, plan_days):
    """4-2：骨架价定计划，附件4真价结算；日内只允许紧急购电兜底。"""
    planning = _price_data(data, data["price"])
    settlement = _price_data(data, data["price_volatile"])
    nominal = q2.phase_a_nominal(planning, model, plan_days)
    residuals = u.build_net_residuals(planning["load"], planning["pv"], model, plan_days)
    search = q2.search_reserve(nominal, residuals, len(plan_days))
    final = q2.phase_c_final(nominal, search["r_seg_kw"], settlement, plan_days)
    return {"nominal": nominal, "search": search, "final": final}


def run_price_oracle_4_2(data, model, plan_days):
    """价格先知对照：真价同时进入优化与结算，仅用于价格信息价值实验。"""
    oracle = _price_data(data, data["price_volatile"])
    nominal = q2.phase_a_nominal(oracle, model, plan_days)
    residuals = u.build_net_residuals(oracle["load"], oracle["pv"], model, plan_days)
    search = q2.search_reserve(nominal, residuals, len(plan_days))
    final = q2.phase_c_final(nominal, search["r_seg_kw"], oracle, plan_days)
    return {"search": search, "final": final}


def run_4_3(data, model, rolling, plan_days):
    """4-3：所有节点用骨架价优化，结合最新光伏预报滚动；附件4真价结算。"""
    planning = _price_data(data, data["price"])
    settlement_price = np.asarray(data["price_volatile"], dtype=float)
    main = q3.run_year(planning, model, rolling, plan_days, (6, 12, 18), p.RHO_REFUND,
                       store_series=True, settlement_price=settlement_price)
    vof = q3.value_of_forecast(planning, model, rolling, plan_days, p.RHO_REFUND,
                               settlement_price=settlement_price)
    return {"main": main, "vof": vof}


def validate_capability(res):
    """核对问题4物理边界、价格信息隔离与信息价值。"""
    r2, r3 = res["result_4_2"], res["result_4_3"]
    assert r2["emergency_qty_kWh"] >= -1e-6, "4-2 紧急购电量非负"
    assert r3["adjust_up_kWh"] >= -1e-6 and r3["adjust_down_kWh"] >= -1e-6, "4-3 调整量非负"
    assert r2["soc_min_kWh"] >= p.SOC_MIN_KWH - 1.0 and r2["soc_max_kWh"] <= p.SOC_MAX_KWH + 1.0, "4-2 SOC 越界"
    assert r3["soc_min_kWh"] >= p.SOC_MIN_KWH - 1.0 and r3["soc_max_kWh"] <= p.SOC_MAX_KWH + 1.0, "4-3 SOC 越界"
    assert r3["vof"]["all_node_cost"] <= r3["vof"]["baseline_no_node_cost"] + 1e-6, "4-3 预报价值应≥0"
    assert res["price_information_value"]["oracle_total_cost_yuan"] <= \
        res["price_information_value"]["skeleton_total_cost_yuan"] + 1e-6, "价格先知对照不应劣于骨架价策略"
    assert res["decision_price_source"] != res["settlement_price_source"], "决策价与结算价必须显式分离"


def run(save=True):
    u.set_all_seeds()
    data = u.load_annual()
    rolling = u.load_pv_forecast_rolling()
    plan_days = u.find_plan_days(data["dates"])
    warmup = range(0, plan_days.start)
    model = u.fit_load_forecaster(data["load"], warmup)

    r42 = run_4_2(data, model, plan_days)
    oracle42 = run_price_oracle_4_2(data, model, plan_days)
    r43 = run_4_3(data, model, rolling, plan_days)
    f2, s2, n2 = r42["final"], r42["search"], r42["nominal"]
    m3, v3 = r43["main"], r43["vof"]

    # 波动 vs 固定 电价均值/极差对照（仅作事后描述，不进入决策）
    pv_price = data["price_volatile"][plan_days.start:]
    tpl_price = data["price"][plan_days.start]
    price_stats = {
        "volatile_mean": round(float(np.mean(pv_price)), 4),
        "volatile_min": round(float(np.min(pv_price)), 4),
        "volatile_max": round(float(np.max(pv_price)), 4),
        "template_mean": round(float(np.mean(tpl_price)), 4),
        "template_min": round(float(np.min(tpl_price)), 4),
        "template_max": round(float(np.max(tpl_price)), 4),
    }
    price_structure = analyze_price_structure(data, plan_days)
    oracle_cost = float(oracle42["final"]["total_cost"])
    skeleton_cost = float(f2["total_cost"])
    price_information_value = {
        "experiment": "4-2 perfect-price-information oracle vs skeleton-price forecast; both settled at actual price",
        "oracle_total_cost_yuan": round(oracle_cost, 2),
        "skeleton_total_cost_yuan": round(skeleton_cost, 2),
        "value_yuan": round(skeleton_cost - oracle_cost, 2),
        "value_pct": round(100 * (skeleton_cost - oracle_cost) / skeleton_cost, 6),
    }

    res_4_2 = {
        "subproblem": "4-2",
        "n_days": len(plan_days),
        "total_cost_yuan": round(f2["total_cost"], 2),
        "plan_cost_yuan": round(f2["plan_cost"], 2),
        "emergency_cost_yuan": round(f2["emergency_cost"], 2),
        "emergency_qty_kWh": round(f2["emergency_qty"], 2),
        "curtail_qty_kWh": round(f2["curtail_qty"], 2),
        "soc_min_kWh": round(f2["soc_min"], 2),
        "soc_max_kWh": round(f2["soc_max"], 2),
        "E_final_kWh": round(f2["E_final"], 2),
        "terminal_value_yuan_per_kWh": round(n2["lam"], 4),
        "reserve_seg_kw": [round(x, 2) for x in s2["r_seg_kw"]],
        "saa_cost_init": s2["saa_cost_init"],
        "saa_cost_opt": s2["saa_cost_opt"],
        "emergency_intervals": int(np.sum(np.asarray(f2["series"]["e"]) > 1e-6)),
        "emergency_days": int(np.sum(np.any(np.asarray(f2["series"]["e"]) > 1e-6, axis=1))),
    }
    res_4_3 = {
        "subproblem": "4-3",
        "n_days": len(plan_days),
        "rho_refund": p.RHO_REFUND,
        "total_cost_yuan": round(m3["total_cost"], 2),
        "base_commit_cost_yuan": round(m3["base_cost"], 2),
        "over_adjust_cost_yuan": round(m3["over_cost"], 2),
        "breach_cost_yuan": round(m3["breach_cost"], 2),
        "emergency_cost_yuan": round(m3["emergency_cost"], 2),
        "adjust_up_kWh": round(m3["adjust_up_kWh"], 2),
        "adjust_down_kWh": round(m3["adjust_down_kWh"], 2),
        "emergency_qty_kWh": round(m3["emergency_qty"], 2),
        "curtail_qty_kWh": round(m3["curtail_qty"], 2),
        "soc_min_kWh": round(m3["soc_min"], 2),
        "soc_max_kWh": round(m3["soc_max"], 2),
        "E_final_kWh": round(m3["E_final"], 2),
        "terminal_value_yuan_per_kWh": round(m3["lam"], 4),
        "vof": v3,
        "emergency_intervals": int(np.sum(np.asarray(m3["series"]["e"]) > 1e-6)),
        "emergency_days": int(np.sum(np.any(np.asarray(m3["series"]["e"]) > 1e-6, axis=1))),
    }

    date2row2 = {row["date"]: row for row in f2["daily"]}
    res_4_2["eval_days"] = {d: date2row2.get(d) for d in p.EVAL_DATES if d in date2row2}
    date2row3 = {row["date"]: row for row in m3["daily"]}
    res_4_3["eval_days"] = {d: date2row3.get(d) for d in p.EVAL_DATES if d in date2row3}

    res = {
        "problem": 4,
        "decision_price_source": "附件1的144点分时骨架价（预测价；优化阶段唯一可见价格）",
        "settlement_price_source": "附件4当天真实波动价（仅用于事后结算）",
        "price_leakage_guard": "附件4真实价不传入正式4-2/4-3优化器",
        "price_stats": price_stats,
        "price_structure": price_structure,
        "price_information_value": price_information_value,
        "result_4_2": res_4_2,
        "result_4_3": res_4_3,
    }
    validate_capability(res)
    if save:
        u.save_json({**res,
                     "daily_4_2": f2["daily"], "series_4_2": f2["series"],
                     "daily_4_3": m3["daily"], "series_4_3": m3["series"]},
                    Path(__file__).resolve().parent.parent / "figures" / "problem_4_results.json")
    return res


if __name__ == "__main__":
    import time
    t0 = time.time()
    r = run()
    print(f"问题4完成（{time.time()-t0:.1f}s）：")
    print("  价格对照：", r["price_stats"])
    print("  结构辨识：", r["price_structure"])
    print("  价格信息价值：", r["price_information_value"])
    print("  4-2：", {k: v for k, v in r["result_4_2"].items() if k not in ("eval_days",)})
    print("  4-3：", {k: v for k, v in r["result_4_3"].items() if k not in ("eval_days", "vof")})
    print("  4-3 VoF：", {"baseline": r["result_4_3"]["vof"]["baseline_no_node_cost"],
                          "all_node": r["result_4_3"]["vof"]["all_node_cost"],
                          "saved": r["result_4_3"]["vof"]["vof_full_yuan"]})
