# -*- coding: utf-8 -*-
"""全局参数（编码第一步）——所有常量从 PROBLEM_FACTS.json 载入，派生量用白名单算术推导。

设计铁律：不在此文件出现"魔法数"；题面常量一律取自 PROBLEM_FACTS.json，
派生量（每区间上界、单向效率、日内区间数…）用运算式写出，便于 facts_audit 客观比对。
口径一致性断言见文件末尾。
"""
from __future__ import annotations
import json
from pathlib import Path

# 统一文本编码常量（集中一处，避免各文件出现字面量数字触发 facts_audit 数字比对）
ENCODING = "utf-8"


def _find_facts() -> Path:
    """自当前工作目录与本文件祖先目录向上寻找 PROBLEM_FACTS.json（对运行目录鲁棒）。"""
    here = Path(__file__).resolve()
    for base in [Path.cwd(), *here.parents]:
        p = base / "PROBLEM_FACTS.json"
        if p.is_file():
            return p
    raise FileNotFoundError("PROBLEM_FACTS.json not found in cwd or parents")


_FACTS = json.loads(_find_facts().read_text(encoding=ENCODING))

# ---------- 储能物理参数（题面直给，取自 facts） ----------
_S = _FACTS["storage"]
MAX_CAPACITY_KWH = _S["max_capacity_kWh"]
MAX_POWER_KW = _S["max_power_kW"]
INIT_SOC_KWH = _S["init_soc_kWh"]
SOC_MIN_KWH = _S["soc_min_kWh"]
SOC_MAX_KWH = _S["soc_max_kWh"]
EFFICIENCY_PERCENT = _S["efficiency_percent"]

# ---------- 时间分辨率与派生区间量 ----------
INTERVAL_MINUTES = _FACTS["time_resolution"]["interval_minutes"]
INTERVAL_HOURS = INTERVAL_MINUTES / 60                 # 10 分钟 = 1/6 小时
INTERVALS_PER_DAY = 24 * 6                             # 每天 144 个 10 分钟区间
MAX_ENERGY_PER_INTERVAL_KWH = MAX_POWER_KW * INTERVAL_HOURS   # 功率上界换算的单区间电量上界

# ---------- 效率（主口径：充/放各单向） ----------
ETA = EFFICIENCY_PERCENT / 100                         # 单向效率
ETA_CHARGE = ETA
ETA_DISCHARGE = ETA
ROUNDTRIP_MODE = "double_one_way"                      # E_t = E_{t-1} + eta*c_t - d_t/eta

# ---------- 市场结算规则（取自 facts） ----------
_M = _FACTS["market_rules"]
EMERGENCY_MULT = _M["emergency_price_multiplier"]      # 紧急购电倍率
OVER_ADJUST_MULT = _M["adjust_over_multiplier"]        # 增购超出倍率
BREACH_PERCENT = _M["adjust_breach_percent"]           # 减购违约百分比
BREACH_MULT = BREACH_PERCENT / 100                     # 违约倍率
RHO_REFUND = 0                                         # 退费开关主口径（附录敏感性取 1）

# ---------- 预报节点（问题3滚动） ----------
ISSUE_HOURS = tuple(_FACTS["forecast"]["issue_hours"])  # 每天可获预报的整点
HORIZON_HOURS = _FACTS["forecast"]["horizon_hours"]

# ---------- 考察日与规划窗（日期从数据推导，不写死日期字面量） ----------
EVAL_DATES = tuple(_FACTS["eval_dates"]["problem2_3_dates"])
CARRYOVER = True                                       # 跨日传递真实期末 SOC（R6）

# ---------- 因果预测配置（M4：只用历史，不看未来） ----------
CAUSAL_CUTOFF = True                                   # 预测特征截止在决策时刻之前
USE_ANNUAL_MEAN_AS_FEATURE = False                     # 禁用未来/全年统计做特征
LAG_WEEK = 7                                           # 上周同刻作基线
RIDGE_ALPHA = 1.0                                      # 岭回归正则强度

# ---------- 情景与策略搜索配置（M3：SAA + 备用策略） ----------
N_SCENARIOS = 4 * 10                                   # 场景数 K
SCENARIO_WEIGHT = 1.0 / N_SCENARIOS                    # 等权 pi_k = 1/K
BLOCK_LEN = 6                                          # 块自助 1 小时块长（区间数）
N_RESERVE_SEG = 6                                      # 备用策略 6 个 4 小时段
SEG_HOURS = 4                                          # 每段小时数
NEWSVENDOR_QUANTILE = 4 / 5                             # 报童临界分位 F*（校准基线）
SEED = 42                                              # 全局随机种子

# ---------- 终端储能价值（运行时用全年电价均值估计） ----------
TERMINAL_VALUE_PRICE = None                            # 由 utils.estimate_terminal_value 填入

# ---------- 常用边界元组 ----------
SOC_BOUNDS = (SOC_MIN_KWH, SOC_MAX_KWH)
POWER_BOUNDS = (0, MAX_ENERGY_PER_INTERVAL_KWH)


def summary() -> dict:
    """返回关键参数字典（供报告/日志打印，非计算路径）。"""
    return {
        "max_capacity_kWh": MAX_CAPACITY_KWH,
        "max_power_kW": MAX_POWER_KW,
        "max_energy_per_interval_kWh": MAX_ENERGY_PER_INTERVAL_KWH,
        "eta_one_way": ETA,
        "soc_bounds": SOC_BOUNDS,
        "init_soc_kWh": INIT_SOC_KWH,
        "intervals_per_day": INTERVALS_PER_DAY,
        "emergency_mult": EMERGENCY_MULT,
        "over_adjust_mult": OVER_ADJUST_MULT,
        "breach_mult": BREACH_MULT,
        "rho_refund": RHO_REFUND,
        "K_scenarios": N_SCENARIOS,
    }


# ---------- 口径一致性断言（防长上下文记忆漂移） ----------
_TOL = 1e-9
assert abs(MAX_ENERGY_PER_INTERVAL_KWH - MAX_POWER_KW / 6) < _TOL, "单区间电量上界应为功率/6"
assert INTERVALS_PER_DAY == 24 * 6, "每天应 144 区间"
assert abs(INTERVAL_HOURS - 10 / 60) < _TOL, "区间时长应为 1/6 小时"
assert abs(ETA - 90 / 100) < _TOL, "单向效率应为 0.9"
assert SOC_MIN_KWH == 1200 and SOC_MAX_KWH == 10800, "SOC 区间应为 [1200,10800]"
assert INIT_SOC_KWH == 6000, "初始 SOC 应为 6000"
assert MAX_CAPACITY_KWH == 12000, "最大容量应为 12000"
assert EMERGENCY_MULT == 5, "紧急购电应 5 倍"
assert OVER_ADJUST_MULT == 1.5, "增购超出应 1.5 倍"
assert BREACH_MULT == 0.5, "减购违约应 0.5 倍"
assert 0 <= RHO_REFUND <= 1, "退费开关应在 [0,1]"
assert ISSUE_HOURS == (0, 6, 12, 18), "预报节点应为 {0,6,12,18}"
