# -*- coding: utf-8 -*-
"""数据加载、因果预测、情景生成与因果反馈控制器 —— 各问共用工具层。

关键实现点（对应 METHOD_CLAIMS）：
  M4 因果预测：负载 = 上周同刻 ℓ_{d-7,t}（shift 7 天）+ Ridge 岭回归偏差校正（仅用历史）；
              光伏 = 近 7 日同刻均值 mean(axis=0)。特征矩阵不含当日未来实测列（无泄漏）。
  情景：对因果预测残差做块自助(block bootstrap)，K 个等权场景 pi_k = 1/K。
  因果反馈控制器：日前计划 q0 固定，日内按真实净负荷平衡电池(充/放各单向 0.9)，
                越限转紧急购电/弃光，全程 SOC 夹在运行区间内。
"""
from __future__ import annotations
import json
import random
import platform
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
import params as p


def set_all_seeds(seed: int = p.SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)


def collect_run_metadata(seed: int = p.SEED) -> dict:
    meta = {"seed": seed, "run_id": datetime.now().strftime("%Y%m%dT%H%M%S"),
            "python": platform.python_version(), "platform": platform.platform()}
    try:
        import importlib.metadata as im
        for pkg in ("numpy", "scipy", "pandas", "scikit-learn", "pulp", "openpyxl"):
            try:
                meta[pkg] = im.version(pkg)
            except Exception:
                meta[pkg] = "unknown"
    except Exception:
        pass
    return meta


def _data_dir() -> Path:
    here = Path(__file__).resolve()
    for base in [Path.cwd(), *here.parents]:
        d = base / "user_data"
        if d.is_dir():
            return d
    raise FileNotFoundError("user_data/ not found")


def save_json(obj, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding=p.ENCODING)
# ---------- 数据加载（openpyxl 引擎，显式 sheet_name，绝不依赖默认首表） ----------
def load_typical_day() -> dict:
    """附件1典型日：144 区间的电价 / 负载 / 光伏预测（问题1输入）。"""
    fp = _data_dir() / "附件1.xlsx"
    df = pd.read_excel(fp, sheet_name="Sheet1")
    price = df["电价"].to_numpy(dtype=float)
    load = df["小区负载"].to_numpy(dtype=float)
    pv = df["光伏发电预测功率"].to_numpy(dtype=float)
    assert len(price) == p.INTERVALS_PER_DAY, "附件1应 144 区间"
    return {"price": price, "load": load, "pv_forecast": pv}


def _matrix_from_daily_sheet(fp: Path, sheet: str) -> np.ndarray:
    """读日期×时间的全年矩阵，剥掉首列日期，返回 (n_days, 144) 浮点阵。"""
    df = pd.read_excel(fp, sheet_name=sheet)
    mat = df.iloc[:, 1:].to_numpy(dtype=float)
    assert mat.shape[1] == p.INTERVALS_PER_DAY, f"{sheet} 每日应 144 点，实得 {mat.shape[1]}"
    return mat


def load_annual() -> dict:
    """附件2全年负载/光伏实际 (365,144) + 两套电价：
      price          = 附件1 典型日固定模板广播到每天（问题2/3：题面"每天电价相同"）；
      price_volatile = 附件4 每天各异波动电价（问题4 专用）。含日期索引。"""
    a2 = _data_dir() / "附件2.xlsx"
    a4 = _data_dir() / "附件4.xlsx"
    load = _matrix_from_daily_sheet(a2, "小区负载")
    pv = _matrix_from_daily_sheet(a2, "光伏发电实际功率")
    price_volatile = _matrix_from_daily_sheet(a4, "Sheet1")     # 附件4：波动电价（问题4）
    dates = pd.read_excel(a2, sheet_name="小区负载").iloc[:, 0]
    dates = pd.to_datetime(dates).dt.strftime("%Y-%m-%d").to_numpy()
    n = load.shape[0]
    assert pv.shape[0] == n and price_volatile.shape[0] == n, "附件2/4 天数应一致"
    tpl = load_typical_day()["price"]                           # 附件1：典型日固定电价模板
    price_template = np.tile(tpl, (n, 1))                       # 广播每天（问题2/3 每天电价相同）
    return {"load": load, "pv": pv, "price": price_template,
            "price_volatile": price_volatile, "dates": dates, "n_days": n}


def load_pv_forecast_rolling() -> dict:
    """附件3滚动光伏预报：按发布时刻 {0,6,12,18} 组织，未来 24 整点小时。
    返回 {(date_str, issue_hour): np.array(24)}；日期在每 4 行块首，向下填充。"""
    fp = _data_dir() / "附件3.xlsx"
    df = pd.read_excel(fp, sheet_name="Sheet1")
    df.columns = [str(c) for c in df.columns]
    date_col = df.columns[0]
    df[date_col] = df[date_col].replace("", np.nan)
    df[date_col] = df[date_col].ffill()
    fc_cols = [c for c in df.columns if str(c).startswith("预报") and str(c).endswith("小时")]
    out = {}
    for _, row in df.iterrows():
        d = pd.to_datetime(str(row[date_col])).strftime("%Y-%m-%d")
        hh = str(row["预报时刻"]).split(":")[0]
        try:
            issue = int(hh)
        except ValueError:
            continue
        out[(d, issue)] = row[fc_cols].to_numpy(dtype=float)
    return out


def hourly_to_intervals(hourly24: np.ndarray) -> np.ndarray:
    """把 24 个整点小时值线性插值到 144 个 10 分钟区间（区间末端对齐）。"""
    n = p.INTERVALS_PER_DAY
    x_new = (np.arange(1, n + 1)) * p.INTERVAL_HOURS       # 各区间末端小时刻 (1/6 .. 24)
    x_src = np.arange(1, len(hourly24) + 1)                # 1..24 整点
    return np.interp(x_new, x_src, hourly24, left=hourly24[0], right=hourly24[-1])
# ---------- M4 因果预测器（负载：上周同刻 + Ridge 校正；光伏：近7日同刻均值） ----------
def _causal_features(load_mat: np.ndarray, day: int, t_idx: np.ndarray) -> np.ndarray:
    """构造第 day 天的因果特征（只用 <day 的历史）：上周同刻、昨日同刻、近7日同刻均值、
    日内位置正余弦、是否周末。绝不引用当日或未来实测。"""
    lag_week = load_mat[day - p.LAG_WEEK]                       # ℓ_{d-7,t} 上周同刻
    lag_day = load_mat[day - 1]                                # 昨日同刻
    recent = load_mat[day - p.LAG_WEEK:day].mean(axis=0)       # 近7日同刻均值 mean(axis=0)
    ang = 2 * np.pi * t_idx / p.INTERVALS_PER_DAY
    dow = (day % p.LAG_WEEK)
    weekend = np.full_like(t_idx, 1.0 if dow >= 5 else 0.0, dtype=float)
    return np.column_stack([lag_week, lag_day, recent, np.sin(ang), np.cos(ang), weekend])


def fit_load_forecaster(load_mat: np.ndarray, train_days: range) -> Ridge:
    """在历史窗（预热期）拟合岭回归偏差校正：以因果特征预测真实负载。"""
    t_idx = np.arange(p.INTERVALS_PER_DAY)
    X, y = [], []
    for d in train_days:
        if d < p.LAG_WEEK:
            continue
        X.append(_causal_features(load_mat, d, t_idx))
        y.append(load_mat[d])
    X = np.vstack(X)
    y = np.concatenate(y)
    model = Ridge(alpha=p.RIDGE_ALPHA)
    model.fit(X, y)
    return model


def forecast_load(load_mat: np.ndarray, day: int, model: Ridge) -> np.ndarray:
    """第 day 天 0:00 可得的负载点预测（Ridge 校正上周同刻基线）。"""
    t_idx = np.arange(p.INTERVALS_PER_DAY)
    return model.predict(_causal_features(load_mat, day, t_idx))


def forecast_pv(pv_mat: np.ndarray, day: int) -> np.ndarray:
    """第 day 天光伏点预测 = 近7日同刻均值（rolling 近7日 mean(axis=0)，纯因果）。"""
    return pv_mat[day - p.LAG_WEEK:day].mean(axis=0)


def estimate_terminal_value(price_mat: np.ndarray) -> float:
    """终端储能价值 λ ≈ 全年电价均值（元/kWh），用于跨日 SOC 的期末计价。"""
    return float(np.mean(price_mat))


# ---------- 情景生成：因果预测残差的块自助（block bootstrap），等权 pi_k=1/K ----------
def build_net_residuals(load_mat, pv_mat, model, plan_days: range) -> np.ndarray:
    """净负荷(=load-pv)点预测残差矩阵 (n_days, 144)，供块自助采样。"""
    res = []
    for d in plan_days:
        net_fc = forecast_load(load_mat, d, model) - forecast_pv(pv_mat, d)
        net_true = load_mat[d] - pv_mat[d]
        res.append(net_true - net_fc)
    return np.array(res)


def block_bootstrap_scenarios(residuals: np.ndarray, K: int, rng: np.random.Generator) -> np.ndarray:
    """对残差做 1 小时块自助，生成 K 个 144 长的净负荷扰动场景。返回 (K,144)。"""
    n_days, n_t = residuals.shape
    blk = p.BLOCK_LEN
    n_blocks = n_t // blk
    scen = np.zeros((K, n_t))
    for k in range(K):
        pieces = []
        for _ in range(n_blocks):
            d = rng.integers(0, n_days)
            start = rng.integers(0, n_t - blk + 1)
            pieces.append(residuals[d, start:start + blk])
        scen[k] = np.concatenate(pieces)[:n_t]
    return scen
# ---------- 因果反馈控制器（日前计划 q0 固定，日内按真实净负荷平衡电池） ----------
def replay_day(q0: np.ndarray, load: np.ndarray, pv: np.ndarray, E0: float,
               price: np.ndarray):
    """对单日执行因果反馈控制并结算（问题2口径：无日内调整，缺口转紧急购电）。

    每区间：可用电=计划购电 q0 + 光伏 pv；净需求 = load - 可用。
      净需求>0 → 优先放电(受功率/SOC约束)补足，仍不足则紧急购电 e_t（5倍价）；
      净需求<0 → 富余先充电(受功率/SOC约束)，充不下的弃光 w_t。
    状态方程（充放各单向 0.9）：E_t = E_{t-1} + eta*c_t - d_t/eta。
    返回逐区间 c,d,e,w,E 及日费用明细。
    """
    n = len(q0)
    cap = p.MAX_ENERGY_PER_INTERVAL_KWH
    eta = p.ETA
    lo, hi = p.SOC_BOUNDS
    dt = p.INTERVAL_HOURS                          # 功率(kW)→区间电量(kWh) 换算
    load_e = load * dt
    pv_e = pv * dt
    c = np.zeros(n); d = np.zeros(n); e = np.zeros(n); w = np.zeros(n); E = np.zeros(n)
    Eprev = E0
    for t in range(n):
        avail = q0[t] + pv_e[t]
        net = load_e[t] - avail
        if net > 0:                      # 缺口：放电优先，越限紧急购电
            dmax = min(cap, (Eprev - lo) * eta)         # 放电内部耗 d/eta，受 SOC 下界限
            d[t] = min(net, max(dmax, 0.0))
            short = net - d[t]
            if short > 1e-9:
                e[t] = short
            Eprev = Eprev - d[t] / eta
        else:                            # 富余：充电吸收，充不下弃光
            surplus = -net
            cmax = min(cap, (hi - Eprev) / eta)         # 充电入内部 eta*c，受 SOC 上界限
            c[t] = min(surplus, max(cmax, 0.0))
            w[t] = surplus - c[t]
            Eprev = Eprev + eta * c[t]
        E[t] = Eprev
    plan_cost = float(np.sum(q0 * price))
    emergency_cost = float(np.sum(p.EMERGENCY_MULT * price * e))
    return {"c": c, "d": d, "e": e, "w": w, "E": E, "E_end": Eprev,
            "plan_cost": plan_cost, "emergency_cost": emergency_cost,
            "total_cost": plan_cost + emergency_cost, "emergency_qty": float(np.sum(e))}


def replay_scenarios(q0: np.ndarray, net_scenarios: np.ndarray, base_net: np.ndarray,
                     pv: np.ndarray, E0: float, price: np.ndarray) -> np.ndarray:
    """向量化跨 K 场景回放，返回每场景总费用 (K,)。用于 SAA 期望费用评估。
    场景 = 基准净负荷 base_net + 扰动；load 等价 = 场景净负荷 + pv。"""
    K, n = net_scenarios.shape
    cap = p.MAX_ENERGY_PER_INTERVAL_KWH
    eta = p.ETA
    lo, hi = p.SOC_BOUNDS
    dt = p.INTERVAL_HOURS
    Eprev = np.full(K, E0)
    plan_cost = float(np.sum(q0 * price))
    emg = np.zeros(K)
    for t in range(n):
        net = (base_net[t] + net_scenarios[:, t]) * dt - q0[t]   # 相对计划的净需求(能量)
        pos = net > 0
        dmax = np.minimum(cap, np.maximum((Eprev - lo) * eta, 0.0))
        dis = np.where(pos, np.minimum(net, dmax), 0.0)
        short = np.where(pos, net - dis, 0.0)
        emg += p.EMERGENCY_MULT * price[t] * short
        cmax = np.minimum(cap, np.maximum((hi - Eprev) / eta, 0.0))
        chg = np.where(~pos, np.minimum(-net, cmax), 0.0)
        Eprev = Eprev - dis / eta + eta * chg
    return plan_cost + emg
# ---------- 共享单日确定性 LP（scipy linprog highs；M1 核心求解，全时域联合优化） ----------
def solve_daily_lp(price: np.ndarray, load: np.ndarray, pv: np.ndarray, E0: float,
                   terminal_mode: str = "value", terminal_value: float = 0.0,
                   terminal_soc: float | None = None):
    """单日 144 区间成本最小化 LP（method='highs'）。

    决策 x = [q(n), c(n), d(n), e(n), w(n)]，E_t 由累计充放推得（不单列变量）：
      状态方程 E_t = E_{t-1} + eta*c_t - d_t/eta（充放各单向效率 0.9）。
    平衡(等式)：q_t + e_t + d_t - c_t - w_t = load_t - pv_t。
    SOC(不等式)：soc_min <= E0 + cumsum(eta*c - d/eta) <= soc_max。
    终端：mode='closure' 强制 E_end=terminal_soc（问题1闭合）；'value' 记终端储能价值。
    """
    from scipy.optimize import linprog
    n = len(price)
    cap = p.MAX_ENERGY_PER_INTERVAL_KWH
    eta = p.ETA
    lo, hi = p.SOC_BOUNDS
    Z = np.zeros((n, n))
    I = np.eye(n)
    Ltri = np.tril(np.ones((n, n)))            # 下三角累计和算子

    # 目标：sum price*q + 5*price*e ; value 模式对终端 E_end 记价（奖励高、罚放电）
    cq = price.copy()
    cc = np.zeros(n); cd = np.zeros(n); ce = p.EMERGENCY_MULT * price.copy(); cw = np.zeros(n)
    if terminal_mode == "value":
        cc += -terminal_value * eta                 # E_end 含 +eta*sum(c)
        cd += terminal_value / eta                  # E_end 含 -sum(d)/eta
    cost = np.concatenate([cq, cc, cd, ce, cw])

    # 平衡等式（load/pv 功率×区间时长换算为能量）
    A_eq = np.hstack([I, -I, I, I, -I])
    b_eq = (load - pv) * p.INTERVAL_HOURS
    if terminal_mode == "closure":
        assert terminal_soc is not None
        row = np.concatenate([Z[0] * 0, eta * np.ones(n), -np.ones(n) / eta,
                              np.zeros(n), np.zeros(n)])
        A_eq = np.vstack([A_eq, row])
        b_eq = np.append(b_eq, terminal_soc - E0)

    # SOC 上下界（累计）
    delta = np.hstack([Z, eta * Ltri, -Ltri / eta, Z, Z])   # cumsum(eta*c - d/eta)
    A_ub = np.vstack([delta, -delta])
    b_ub = np.concatenate([np.full(n, hi - E0), np.full(n, E0 - lo)])

    bounds = ([(0, None)] * n + [(0, cap)] * n + [(0, cap)] * n
              + [(0, None)] * n + [(0, None)] * n)
    res = linprog(cost, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                  bounds=bounds, method="highs")
    if not res.success:
        raise RuntimeError(f"daily LP infeasible: {res.message}")
    x = res.x
    q, c, d, e, w = x[:n], x[n:2*n], x[2*n:3*n], x[3*n:4*n], x[4*n:5*n]
    E = E0 + np.cumsum(eta * c - d / eta)
    plan_cost = float(np.sum(price * q))
    emergency_cost = float(np.sum(p.EMERGENCY_MULT * price * e))
    return {"q": q, "c": c, "d": d, "e": e, "w": w, "E": E, "E_end": float(E[-1]),
            "plan_cost": plan_cost, "emergency_cost": emergency_cost,
            "total_cost": plan_cost + emergency_cost,
            "lp_objective": float(res.fun)}


def find_plan_days(dates: np.ndarray) -> range:
    """规划窗 = 2 月起至年末（1 月为预热）。按日期月份定位，不写死日期字面量。"""
    months = np.array([int(str(x)[5:7]) for x in dates])
    start = int(np.argmax(months >= 2))          # 首个 2 月及以后的日索引
    return range(start, len(dates))




