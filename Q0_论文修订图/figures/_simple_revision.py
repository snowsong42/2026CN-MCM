"""Plain paper figures; numerical inputs are supplied by gen_revision_figures.py."""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch

def diagram_base():
    fig, ax = plt.subplots(figsize=(12.8, 7.2))
    fig.subplots_adjust(0, 0, 1, 1)
    ax.set(xlim=(0, 16), ylim=(0, 9)); ax.axis('off')
    return fig, ax

def node(ax, x, y, w, h, text):
    ax.add_patch(Rectangle((x,y), w,h,facecolor='white',edgecolor='#444444',lw=1))
    ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=14,
            fontfamily='SimSun',linespacing=1.65,color='#222222')

def arrow(ax, start, end):
    ax.add_patch(FancyArrowPatch(start,end,arrowstyle='->',mutation_scale=13,lw=1,color='#444444'))

def diagrams(save):
    fig,ax=diagram_base()
    labels=['问题一：确定性单日调度','问题二：场景预测与因果反馈',
            '问题三：日内滚动优化','问题四：骨架预测与真实价结算']
    additions=['负载、光伏未知','增加日内预报与计划调整','真实电价未知']
    for i,label in enumerate(labels):
        y=7-i*1.95
        node(ax,3.8,y,8.4,.95,label)
        if i<3:
            arrow(ax,(8,y),(8,y-1))
            ax.text(8.3,y-.5,additions[i],va='center',fontsize=12,fontfamily='SimSun')
    save(fig,'fig_roadmap')
    fig,ax=diagram_base()
    for x,text in [(0.75,'数据与预测\n\n负载、光伏历史数据\n已发布预报与骨架价'),
                   (6.05,'优化与执行\n\n购电计划\n储能充放电'),
                   (11.35,'回放与结算\n\n实际供需与储电量\n费用与约束检验')]:
        node(ax,x,3.15,3.9,2.7,text)
    arrow(ax,(4.65,4.5),(6.05,4.5));arrow(ax,(9.95,4.5),(11.35,4.5))
    save(fig,'fig_pipeline')

def typical(s,save,blue,teal,red):
    fig,ax=plt.subplots(figsize=(12.8,7.2))
    fig.subplots_adjust(left=.10,right=.89,bottom=.13,top=.90)
    h=np.arange(144)/6
    load,=ax.plot(h,s['load'],color=blue,lw=1.8,label='小区负载')
    pv,=ax.plot(h,s['pv'],color=teal,lw=1.8,ls='-.',label='光伏预测功率')
    ap=ax.twinx()
    price=ap.stairs(s['price'],np.arange(145)/6,color=red,lw=1.5,ls='--',baseline=None,label='电价')
    ap.spines['right'].set_visible(True)
    ax.set(xlim=(0,24),xticks=np.arange(0,25,2),ylim=(0,9000),xlabel='时刻（h）',ylabel='功率（kW）')
    ap.set(ylim=(0,1.7),ylabel='电价（元/kWh）')
    ax.grid(axis='y',color='#DDDDDD',lw=.6)
    ax.legend(handles=[load,pv,price],loc='upper center',ncol=3,frameon=False)
    save(fig,'fig_typical_day_profile')

def feasible(s,p,save,blue):
    t=int(np.argmax(s['E'][:-1]))+1
    e=float(s['E'][t-1]);cap=p.MAX_ENERGY_PER_INTERVAL_KWH
    c=np.linspace(0,cap,250)
    lo=np.maximum(0,p.ETA*(e+p.ETA*c-p.SOC_MAX_KWH))
    hi=np.minimum(cap,p.ETA*(e+p.ETA*c-p.SOC_MIN_KWH))
    fig,ax=plt.subplots(figsize=(12.8,7.2))
    fig.subplots_adjust(left=.12,right=.95,bottom=.14,top=.91)
    ax.fill_between(c,lo,hi,color='#EEEEEE')
    ax.plot(c,lo,color='#666666',lw=1.2)
    ax.plot(c,hi,color='#666666',lw=1,ls='--')
    ax.plot([cap,cap],[lo[-1],hi[-1]],color='#666666',lw=1,ls='--')
    cm=min(cap,max(0,(p.SOC_MAX_KWH-e)/p.ETA));dm=min(cap,max(0,p.ETA*(e-p.SOC_MIN_KWH)))
    ax.plot([0,cm],[0,0],color=blue,lw=2.5)
    ax.plot([0,0],[0,dm],color=blue,lw=2.5,label='互斥可行集')
    ax.scatter([s['c'][t]],[s['d'][t]],color='#222222',s=26,zorder=5,label='实际调度点')
    ax.text(340,660,'LP 可行域',fontsize=15,fontfamily='SimSun',ha='center')
    ax.text(25,880,f'区间前储电量 {e:,.0f} kWh',fontsize=12,fontfamily='SimSun')
    ax.text(525,345,r'$E_{t-1}+0.9c_t-d_t/0.9=10800$',fontsize=12,rotation=27)
    ax.set(xlabel=r'充电量 $c_t$（kWh）',ylabel=r'放电量 $d_t$（kWh）',
           xlim=(-20,900),ylim=(-20,920),xticks=[0,200,400,600,800],yticks=[0,200,400,600,800])
    ax.legend(frameon=False,loc='lower right')
    save(fig,'tikz_feasible_q1')
