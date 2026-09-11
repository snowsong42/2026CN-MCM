# -*- coding: utf-8 -*-
"""问题一：单区间 (c_t, d_t) 切片上的「经典线性规划几何」三联面板。

为什么是这张图：问题一的 LP 有 720 个变量，画不出教科书那张二维图。但 144 条供需平衡是
等式，可以把 q_t/e_t/w_t 当松弛消掉——剩下所有不等式结构都集中在单个区间的 (c_t, d_t)
平面上。取定区间 t 与来料 SOC E_(t-1)，就得到一张严格二维、且不丢约束信息的切片。

目标等值线【不是】本区间现金流 p_t(c_t-d_t)（那会把最优角指反，见图 (b) 的金色点划线），
而是把 (c_t, d_t) 固定、重解其余时域得到的价值函数 μ(c_t, d_t)。本脚本在网格上逐个
重解 LP 得到 μ，因此画出的等值线与求解结果必然自洽。

产出：fig_q1_lp_geometry.{png,pdf,svg}
运行：<venv>\\Scripts\\python.exe Q1\\figures\\gen_fig_q1_lp_geometry.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Patch, Polygon as MplPolygon
from scipy.optimize import linprog

F = Path(__file__).resolve().parent          # Q1/figures
W = F.parent                                 # Q1
sys.path.insert(0, str(W / "code"))
import params as p                            # noqa: E402
import utils as u                             # noqa: E402

# ── 与工作区"论文修订图"一致的硬编码配色（不经过 plot_utils，故不受配色种子影响）──
BLUE, TEAL, RED, GOLD = "#3C5488", "#00A087", "#E64B35", "#E3B45A"
INK, GREY = "#263442", "#7C8896"

plt.rcParams.update({"font.family": "Microsoft YaHei", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.unicode_minus": False, "svg.fonttype": "path",
                     "pdf.fonttype": 42})

CAP, ETA, (LO, HI), DT = p.MAX_ENERGY_PER_INTERVAL_KWH, p.ETA, p.SOC_BOUNDS, p.INTERVAL_HOURS
N, EMG, E0 = p.INTERVALS_PER_DAY, p.EMERGENCY_MULT, p.INIT_SOC_KWH
DX, DY = N, 2 * N                            # c_t / d_t 在决策向量里的下标偏移


# ────────────────────────────── LP 与切片几何 ──────────────────────────────
def _build(price, load, pv, e0):
    """复刻 utils.solve_daily_lp 的 closure 口径，返回矩阵供反复重解。"""
    Z, I, L = np.zeros((N, N)), np.eye(N), np.tril(np.ones((N, N)))
    cost = np.concatenate([price, np.zeros(N), np.zeros(N), EMG * price, np.zeros(N)])
    A_eq = np.vstack([np.hstack([I, -I, I, I, -I]),
                      np.concatenate([np.zeros(N), ETA * np.ones(N), -np.ones(N) / ETA,
                                      np.zeros(N), np.zeros(N)])])
    b_eq = np.append((load - pv) * DT, 0.0)
    delta = np.hstack([Z, ETA * L, -L / ETA, Z, Z])
    A_ub = np.vstack([delta, -delta])
    b_ub = np.concatenate([np.full(N, HI - e0), np.full(N, e0 - LO)])
    bnds = ([(0, None)] * N + [(0, CAP)] * N + [(0, CAP)] * N
            + [(0, None)] * N + [(0, None)] * N)
    return cost, A_ub, b_ub, A_eq, b_eq, bnds


def solve_lp(price, load, pv, e0, fix=None):
    cost, A_ub, b_ub, A_eq, b_eq, bnds = _build(price, load, pv, e0)
    if fix:
        bnds = list(bnds)
        for idx, val in fix.items():
            bnds[idx] = (float(val), float(val))
    return linprog(cost, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                   bounds=bnds, method="highs")


def polygon(ep):
    """给定来料 SOC，返回有序顶点、两条 SOC 线函数与截距（cm/dm < CAP 表示该线切进正方形）。"""
    lo = lambda cc: max(0.0, ETA * (ep + ETA * cc - HI))     # SOC 上界： d ≥ lo(c)
    hi = lambda cc: min(CAP, ETA * (ep + ETA * cc - LO))     # SOC 下界： d ≤ hi(c)
    cm = min(CAP, max(0.0, (HI - ep) / ETA))
    dm = min(CAP, max(0.0, ETA * (ep - LO)))
    raw = [(0.0, 0.0), (cm, 0.0), (CAP, 0.0), (0.0, dm), (0.0, CAP), (CAP, CAP),
           (CAP, lo(CAP)), (CAP, hi(CAP))]
    pts = [q for q in raw if _ok(q, lo, hi)]
    a = np.array(pts)
    ctr = a.mean(0)
    pts = [tuple(a[i]) for i in np.argsort(np.arctan2(a[:, 1] - ctr[1], a[:, 0] - ctr[0]))]
    return pts, lo, hi, cm, dm


def _ok(pt, lo, hi):
    cc, dd = pt
    if not (-1e-9 <= cc <= CAP + 1e-9 and -1e-9 <= dd <= CAP + 1e-9):
        return False
    return lo(cc) - 1e-7 <= dd <= hi(cc) + 1e-7


# ────────────────────────────── 数据与基准解 ──────────────────────────────
td = u.load_typical_day()
PRICE, LOAD, PV = td["price"], td["load"], td["pv_forecast"]
res0 = solve_lp(PRICE, LOAD, PV, E0)
x0 = res0.x
c_opt, d_opt = x0[DX:DX + N], x0[DY:DY + N]
E = E0 + np.cumsum(ETA * c_opt - d_opt / ETA)
OBJ0 = float(res0.fun)
print(f"基准解：{OBJ0:,.6f} 元，同时充放区间 {int(np.sum((c_opt > 1e-9) & (d_opt > 1e-9)))} 个")

# ── 选三个代表性区间 ──
t_mid = 0                                                  # 来料 SOC 居中 → 整个正方形
t_full = int(np.argmax(E[:-1])) + 1                        # SOC 顶点 → 上界线过原点
_low = [t for t in range(1, N) if E[t - 1] < 2200 and c_opt[t] > 1e-9]
t_low = _low[0] if _low else int(np.argmin(E[:N - 1]))
TAGS = [("(a)", t_low, "近空：SOC 下界线切进可行域"),
        ("(b)", t_mid, "居中：可行域就是整个正方形"),
        ("(c)", t_full, "满荷：SOC 上界线过原点")]
for tag, t, why in TAGS:
    ep = float(E[t - 1]) if t > 0 else float(E0)
    _, _, _, cm, dm = polygon(ep)
    print(f"  {tag} t={t:>3} ({t/6:5.2f} h) p={PRICE[t]:.4f}  E_(t-1)={ep:>9,.2f}  "
          f"cm={cm:>8,.2f} dm={dm:>8,.2f}  最优=({c_opt[t]:>8,.2f},{d_opt[t]:>8,.2f})  {why}")

# ────────────────────────────── 画图 ──────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(14.6, 6.4))
fig.subplots_adjust(left=0.052, right=0.988, top=0.815, bottom=0.245, wspace=0.19)
AXMAX = 900.0

for ax, (tag, t, why) in zip(axes, TAGS):
    ep = float(E[t - 1]) if t > 0 else float(E0)
    pts, lo, hi, cm, dm = polygon(ep)
    cc = np.array([0.0, AXMAX])

    # ① LP 松弛可行域
    ax.add_patch(MplPolygon(pts, closed=True, facecolor="#E9EDF2",
                            edgecolor=INK, lw=1.0, zorder=1))
    # ② 两条 SOC 线（斜率 η²=0.81）—— 只有真正切进正方形的才画，避免与坐标轴重合造成误读
    if cm < CAP - 1e-9:
        ax.plot(cc, [lo(v) for v in cc], color=GREY, lw=1.4, ls="--", zorder=2)
        ax.text(172, 66, "SOC 上界（斜率 $\\eta^2$）", fontsize=8.2, color=GREY,
                ha="left", va="bottom", zorder=2)
    if dm < CAP - 1e-9:
        ax.plot(cc, [hi(v) for v in cc], color=GREY, lw=1.4, ls=":", zorder=2)
        ax.text(24, 592, "SOC 下界（斜率 $\\eta^2$）", fontsize=8.2, color=GREY,
                ha="left", va="bottom", zorder=2)
    # ③ 物理互斥集 c·d = 0
    ax.plot([0, CAP], [0, 0], color=BLUE, lw=2.8, solid_capstyle="butt", zorder=3)
    ax.plot([0, 0], [0, CAP], color=BLUE, lw=2.8, solid_capstyle="butt", zorder=3)
    # ④ 支配方向（位置在三个面板中都落在可行域内，且不压标题）
    ax.add_patch(FancyArrowPatch((600, 556), (438, 394), arrowstyle="-|>",
                                 mutation_scale=13, lw=1.5, color=RED, zorder=5))
    ax.text(614, 566, "同时减 $\\delta$：费用不变\n储能多得 $0.2111\\delta$\n→ 该方向被支配",
            fontsize=8.0, color=RED, va="bottom", ha="left", linespacing=1.4, zorder=5)

    # ⑤ 价值函数等值线（网格上逐个重解 LP）
    grid = np.linspace(0, AXMAX, 13)
    CC, DD = np.meshgrid(grid, grid)
    ZZ = np.full_like(CC, np.nan)
    for i in range(CC.shape[0]):
        for j in range(CC.shape[1]):
            cv, dv = CC[i, j], DD[i, j]
            if cv > CAP + 1e-9 or dv > CAP + 1e-9 or dv < lo(cv) - 1e-7 or dv > hi(cv) + 1e-7:
                continue
            r = solve_lp(PRICE, LOAD, PV, E0, fix={DX + t: cv, DY + t: dv})
            if r.status == 0:
                ZZ[i, j] = r.fun
    if np.isfinite(ZZ).sum() >= 6:
        zmin, zmax = np.nanmin(ZZ), np.nanmax(ZZ)
        zspan = zmax - zmin
        if zspan > 1e-6:
            lv = np.linspace(zmin + zspan * 0.15, zmin + zspan * 0.90, 4)
            cs = ax.contour(CC, DD, np.ma.masked_invalid(ZZ), levels=lv,
                            colors=TEAL, linewidths=0.9, zorder=4)
            ax.clabel(cs, fmt=lambda v: f"+{v - zmin:.1f}", fontsize=6.8, inline=True,
                      inline_spacing=3, rightside_up=True)
        ax.text(0.985, 0.972, f"目标变幅 {zspan:.1f} 元（占全天 {100 * zspan / OBJ0:.3f}%）",
                transform=ax.transAxes, fontsize=7.8, color=TEAL, ha="right", va="top",
                zorder=6)

    # ⑥ 最优点、紧约束、是否顶点解
    co, do = float(c_opt[t]), float(d_opt[t])
    tight = []
    if abs(co - CAP) < 1e-9:
        tight.append("$c_t\\leq 833.33$")
    elif co < 1e-9:
        tight.append("$c_t\\geq 0$")
    if abs(do - CAP) < 1e-9:
        tight.append("$d_t\\leq 833.33$")
    elif do < 1e-9:
        tight.append("$d_t\\geq 0$")
    if cm < CAP - 1e-9 and abs(do - lo(co)) < 1e-6:
        tight.append("SOC 上界")
    if dm < CAP - 1e-9 and abs(hi(co) - do) < 1e-6:
        tight.append("SOC 下界")
    at_vertex = any(abs(co - a) < 1e-6 and abs(do - b) < 1e-6 for a, b in pts)
    kind = "顶点解（教科书情形）" if at_vertex else "落在可行域边界上（非顶点）"
    ax.plot([co], [do], marker="o", ms=8, mfc=RED, mec="white", mew=1.4, zorder=7)
    ax.annotate(f"最优 ({co:,.2f}, {do:,.2f})\n{kind}\n紧约束：{'、'.join(tight) if tight else '无'}",
                xy=(co, do), xytext=(co + 80 if co < 430 else co - 80, do + 235),
                fontsize=8.2, color=INK, linespacing=1.45, zorder=8,
                ha="left" if co < 430 else "right",
                arrowprops=dict(arrowstyle="-", color=GREY, lw=0.8, shrinkA=2, shrinkB=6))

    # ⑦ (b) 面板画出"若误用本区间现金流"的斜率 1 等值线，示其指向反角
    if tag == "(b)":
        ax.plot([0, 700], [120, 820], color=GOLD, lw=1.5, ls="-.", zorder=4)
        ax.add_patch(FancyArrowPatch((352, 472), (96, 728), arrowstyle="-|>",
                                     mutation_scale=13, lw=1.5, color=GOLD, zorder=5))
        ax.text(112, 700, "错误方向", fontsize=8.2, color=GOLD, ha="left", va="bottom",
                zorder=5)

    ax.set_xlim(-25, AXMAX)
    ax.set_ylim(-25, AXMAX)
    ax.set_aspect("equal")
    ax.set_xticks([0, 200, 400, 600, 800])
    ax.set_yticks([0, 200, 400, 600, 800])
    ax.set_xlabel("充电量 $c_t$（kWh）")
    ax.set_ylabel("放电量 $d_t$（kWh）")
    ax.grid(alpha=0.10, lw=0.6)
    ax.set_title(f"{tag}  $E_{{t-1}}$ = {ep:,.0f} kWh（{t/6:.2f} h，$p_t$ = {PRICE[t]:.4f} 元/kWh）\n{why}",
                 loc="left", fontsize=10.5, fontweight="bold", linespacing=1.55, pad=9)

proxy = [Patch(facecolor="#E9EDF2", edgecolor=INK, lw=1.0),
         Line2D([], [], color=GREY, lw=1.4, ls="--"),
         Line2D([], [], color=GREY, lw=1.4, ls=":"),
         Line2D([], [], color=BLUE, lw=2.8),
         Line2D([], [], color=TEAL, lw=1.2),
         Line2D([], [], color=GOLD, lw=1.5, ls="-."),
         Line2D([], [], color=RED, lw=1.5, marker="o", ms=7, mfc=RED, mec="white")]
labels = ["LP 松弛可行域（$q_t,e_t,w_t$ 已由平衡等式消去）",
          "SOC 上界 $d_t\\geq\\eta(E_{t-1}+\\eta c_t-10800)$，斜率 $\\eta^2=0.81$",
          "SOC 下界 $d_t\\leq\\eta(E_{t-1}+\\eta c_t-1200)$，斜率 $\\eta^2=0.81$",
          "物理互斥集 $c_td_t=0$（LP 未含此约束）",
          "价值函数等值线（$+\\Delta$ 元）",
          "误用 $p_t(c_t-d_t)$ 的等值线（斜率 1，会把最优指向 $(0,833)$）",
          "区间最优调度点"]
fig.legend(proxy, labels, frameon=False, ncol=4, loc="lower center",
           bbox_to_anchor=(0.5, 0.005), fontsize=8.6, handlelength=1.9,
           columnspacing=1.5, labelspacing=0.6)
fig.suptitle("问题一：单区间 $(c_t,d_t)$ 切片上的线性规划几何"
             "（等值线由「固定 $c_t,d_t$ 重解其余时域」的真实价值函数给出）",
             x=0.052, ha="left", fontsize=12, fontweight="bold", y=0.978)

for ext in ("png", "pdf", "svg"):
    fig.savefig(F / f"fig_q1_lp_geometry.{ext}", dpi=170, facecolor="white",
                bbox_inches="tight")
plt.close(fig)
print(f"已写出 {F / 'fig_q1_lp_geometry.png'}")
