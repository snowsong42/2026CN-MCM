"""Reproduce the requested paper revision figures from original XLSX and saved results.

Replaces designs in fig_roadmap.html, fig_pipeline.html, tikz_feasible_q1.tex,
gen_fig_typical_day_profile.py and gen_fig_q1_arbitrage.py. Heatmaps extend
gen_fig_data_overview.py using original dated observations, not cached aggregates.
Run: python workspace/figures/gen_revision_figures.py
"""
from pathlib import Path
import sys, json, hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.colors import LinearSegmentedColormap

F = Path(__file__).resolve().parent
W = F.parent
sys.path.insert(0, str(W / 'code'))
import params as p
plt.rcParams.update({'font.family': 'Microsoft YaHei', 'font.size': 12,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'svg.fonttype': 'path', 'pdf.fonttype': 42,
                     'axes.unicode_minus': False, 'axes.titleweight': 'bold'})
BLUE, TEAL, RED, GOLD = '#3C5488', '#00A087', '#E64B35', '#E3B45A'
INK = '#263442'

def save(fig, name):
    for ext in ['svg', 'pdf', 'png']:
        fig.savefig(F / f'{name}.{ext}', dpi=170, facecolor='white')
    plt.close(fig)

from _simple_revision import diagrams, typical, feasible

def main():
    raw=pd.read_excel(W/'user_data/附件1.xlsx',sheet_name='Sheet1')
    s={k:np.asarray(v,float) for k,v in json.loads((F/'problem_1_results.json').read_text(encoding='utf-8'))['series'].items()}
    for key,col in [('load','小区负载'),('pv','光伏发电预测功率'),('price','电价')]:
        np.testing.assert_allclose(s[key],raw[col].to_numpy(float),atol=1e-8)
    result=pd.read_excel(W/'result1.xlsx',sheet_name=0)
    err=float(np.max(np.abs(result.iloc[:144,1].to_numpy(float)-s['q'])))
    assert err <= 5.01e-5
    segments=np.array([s[k].reshape(6,24).sum(1) for k in ['q','c','d']]).T
    charge_table=pd.read_excel(W/'result1.xlsx',sheet_name=1)
    np.testing.assert_allclose(segments[:,1:],charge_table.iloc[:6,1:3].to_numpy(float),atol=5.01e-5,rtol=0)
    audit={'q1_result1_max_rounding_difference_kWh':err,
           'q1_4hour_rows':segments.tolist(), 'sources':{}, 'annual':{}}
    h=np.arange(144)/6
    typical(s,save,BLUE,TEAL,RED)
    if "--requested-only" in sys.argv:
        feasible(s,p,save,BLUE)
        diagrams(save)
        return
    fig,axs=plt.subplots(3,1,figsize=(16,9),sharex=True)
    fig.subplots_adjust(left=.09,right=.89,top=.92,bottom=.09,hspace=.18)
    axs[0].bar(h,s['q'],width=1/6,align='edge',color=BLUE,label='计划购电')
    axs[0].set(ylabel='购电量（kWh）',ylim=(0,1800));axs[0].legend(frameon=False,loc='upper right')
    axs[0].set_title('问题一：购电、储能充放电与电价的对应关系',loc='left',pad=14)
    axs[1].bar(h,s['c'],width=1/6,align='edge',color=TEAL,label='充电')
    axs[1].bar(h,-s['d'],width=1/6,align='edge',color=RED,label='放电（向下）')
    axs[1].axhline(0,color=INK,lw=.7);axs[1].set(ylabel='母线侧电量（kWh）',ylim=(-850,1200));axs[1].legend(frameon=False,ncol=2,loc='upper right')
    axs[2].plot(np.arange(145)/6,np.r_[p.INIT_SOC_KWH,s['E']],color=BLUE,lw=2,label='储电量')
    axs[2].set(ylabel='储电量（kWh）',ylim=(0,12000),xlabel='时刻（h）',xlim=(0,24),xticks=np.arange(0,25,2))
    ap=axs[2].twinx();ap.stairs(s['price'],np.arange(145)/6,color=GOLD,lw=1.7,label='电价',baseline=None);ap.set(ylabel='电价（元/kWh）',ylim=(0,1.6))
    axs[2].legend(frameon=False,loc='upper left');ap.legend(frameon=False,loc='upper right')
    for ax in axs:ax.grid(axis='y',alpha=.12)
    save(fig,'fig_q1_arbitrage')
    dailyframes=[]
    for key,sh,name in [('load','小区负载','负载'),('pv','光伏发电实际功率','光伏')]:
        df=pd.read_excel(W/'user_data/附件2.xlsx',sheet_name=sh)
        dates=pd.to_datetime(df.iloc[:,0]);x=df.iloc[:,1:].to_numpy(float)
        assert x.shape==(365,144) and np.isfinite(x).all() and dates.is_unique
        assert (dates.diff().iloc[1:]==pd.Timedelta(days=1)).all()
        daily=pd.DataFrame({'date':dates,'month':dates.dt.month,'weekday':dates.dt.dayofweek,'energy_kWh':x.sum(1)*p.INTERVAL_HOURS})
        daily.to_csv(F/f'revision_{key}_daily.csv',index=False,encoding='utf-8-sig')
        grp=daily.groupby(['month','weekday']).energy_kWh.agg(['mean','count','std'])
        grp.to_csv(F/f'revision_{key}_month_weekday.csv',encoding='utf-8-sig')
        mat=grp['mean'].unstack().to_numpy(); counts=grp['count'].unstack().to_numpy()
        assert counts.sum()==365
        color=BLUE if key=='load' else TEAL
        cmap=LinearSegmentedColormap.from_list(key,['#F5F8FA',color])
        fig,ax=plt.subplots(figsize=(16,9));fig.subplots_adjust(left=.09,right=.87,top=.9,bottom=.11)
        mesh=ax.pcolormesh(np.arange(8),np.arange(13),mat,cmap=cmap,edgecolors='white',linewidth=.9,rasterized=False)
        ax.invert_yaxis();ax.set(xticks=np.arange(7)+.5,xticklabels=['周一','周二','周三','周四','周五','周六','周日'],yticks=np.arange(12)+.5,yticklabels=[f'{m}月' for m in range(1,13)],ylabel='月份',xlabel='星期')
        ax.set_title(f'2025 年{name}：月份与星期分组的平均日电量',loc='left',pad=20)
        for i in range(12):
            for j in range(7):
                ax.text(j+.5,i+.5,f'{mat[i,j]:,.0f}',ha='center',va='center',fontsize=11,color='white' if (mat[i,j]-mat.min())/(mat.max()-mat.min())>.57 else INK)
        cb=fig.colorbar(mesh,ax=ax,pad=.025,fraction=.035,label=f'平均日{name}（kWh）')
        cb.solids.set_rasterized(False)
        fig.text(.09,.027,'数据：附件 2；10 分钟平均功率 × 1/6 小时后按日累加；每格为该月该星期的 4—5 天均值。',fontsize=11,color='#64717B')
        save(fig,f'fig_q2_{key}_heatmap')
        work=daily.weekday<5
        audit['annual'][key]={'total_kWh':float(daily.energy_kWh.sum()),'mean_kW':float(x.mean()),'min_kW':float(x.min()),'max_kW':float(x.max()),'weekday_daily_kWh':float(daily.loc[work,'energy_kWh'].mean()),'weekend_daily_kWh':float(daily.loc[~work,'energy_kWh'].mean()),'daily_lag7_correlation':float(daily.energy_kWh.autocorr(7)), 'month_weekday_sample_count_range':[int(counts.min()),int(counts.max())]}
    feasible(s,p,save,BLUE)
    diagrams(save)
    for file in [W/'user_data/附件1.xlsx',W/'user_data/附件2.xlsx',W/'result1.xlsx',F/'problem_1_results.json',F/'problem_3_results.json']:
        audit['sources'][str(file.relative_to(W))]=hashlib.sha256(file.read_bytes()).hexdigest()
    (F/'revision_data_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(audit,ensure_ascii=True,indent=2))

if __name__=='__main__':main()
