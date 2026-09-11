# -*- coding: utf-8 -*-
"""数据体检：核对附件1-4读入的量纲与取值范围，对齐 LOGIC_CONTRACT.train_range。
越界即报错（数据错位/单位错误的早期拦截），产出 figures/data_check.json 供审计。
"""
from __future__ import annotations
import numpy as np
import utils as u
import params as p

# 训练/回放合理范围（来自 MODELING_REPORT LOGIC_CONTRACT_MACHINE.train_range）
RANGE = {"load_kW": (1995.7, 7978.9), "pv_kW": (0.0, 10216.2),
         "price_yuan_per_kWh": (0.0076, 1.7936)}


def _within(name, arr, lo, hi, tol=1.0):
    amin, amax = float(np.min(arr)), float(np.max(arr))
    ok = (amin >= lo - tol) and (amax <= hi + tol)
    return {"name": name, "min": round(amin, 4), "max": round(amax, 4),
            "expect_lo": lo, "expect_hi": hi, "ok": bool(ok)}


def run(save=True):
    td = u.load_typical_day()
    annual = u.load_annual()
    rolling = u.load_pv_forecast_rolling()

    checks = []
    checks.append(_within("附件1_电价", td["price"], *RANGE["price_yuan_per_kWh"]))
    checks.append(_within("附件1_负载", td["load"], *RANGE["load_kW"]))
    checks.append(_within("附件1_光伏预测", td["pv_forecast"], 0.0, RANGE["pv_kW"][1]))
    checks.append(_within("附件2_负载", annual["load"], *RANGE["load_kW"]))
    checks.append(_within("附件2_光伏实际", annual["pv"], *RANGE["pv_kW"]))
    checks.append(_within("附件4_波动电价", annual["price_volatile"], *RANGE["price_yuan_per_kWh"]))

    # 形状与维度
    shape_ok = (td["price"].shape[0] == p.INTERVALS_PER_DAY
                and annual["load"].shape[1] == p.INTERVALS_PER_DAY
                and annual["n_days"] == 365)
    # 附件3 滚动预报：发布时刻覆盖 {0,6,12,18}
    issue_set = sorted({h for (_, h) in rolling.keys()})
    forecast_ok = set(p.ISSUE_HOURS).issubset(set(issue_set))

    all_ok = all(c["ok"] for c in checks) and shape_ok and forecast_ok
    res = {"checks": checks, "shape_ok": bool(shape_ok),
           "n_days": annual["n_days"], "intervals_per_day": p.INTERVALS_PER_DAY,
           "forecast_issue_hours_found": issue_set, "forecast_ok": bool(forecast_ok),
           "all_ok": bool(all_ok),
           "seed": p.SEED, "meta": u.collect_run_metadata()}
    if not all_ok:
        bad = [c["name"] for c in checks if not c["ok"]]
        raise AssertionError(f"数据体检未通过：越界项={bad} shape_ok={shape_ok} forecast_ok={forecast_ok}")
    if save:
        u.save_json(res, "figures/data_check.json")
    return res


if __name__ == "__main__":
    r = run()
    print("数据体检完成：all_ok=", r["all_ok"], " shape_ok=", r["shape_ok"],
          " forecast_hours=", r["forecast_issue_hours_found"])
    for c in r["checks"]:
        print(f"  {c['name']}: [{c['min']}, {c['max']}] expect [{c['expect_lo']},{c['expect_hi']}] ok={c['ok']}")
