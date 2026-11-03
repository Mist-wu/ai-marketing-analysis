"""从已核验汇总结果导出手册要求的五张PNG。运行：python render_figures.py"""
from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager, dates as mdates

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'figures'; OUT.mkdir(exist_ok=True)
font=next((p for p in [Path('/System/Library/Fonts/PingFang.ttc'),Path('/System/Library/Fonts/STHeiti Light.ttc')] if p.exists()),None)
if font:
    font_manager.fontManager.addfont(str(font))
    plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams.update({'font.size':12,'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False,'figure.dpi':120,'savefig.dpi':180})
blue='#2864A5'; gold='#A76521'; gray='#59636F'
s=json.loads((ROOT/'results/summary.json').read_text())
def read(n): return pd.read_csv(ROOT/'results'/f'{n}.csv')
def fig(title,y):
    f,a=plt.subplots(figsize=(11,6),layout='constrained')
    a.set_title(title,loc='left',pad=20,fontweight='bold');a.set_ylabel(y)
    a.grid(axis='y',color='#E6E9EE',zorder=0);a.set_axisbelow(True)
    return f,a
def save(f,n):
    f.savefig(OUT/n,facecolor='white');plt.close(f)
d=read('amount_distribution');f,a=fig('订单金额分布：均值高于中位数','订单数（单）')
a.bar(d.lower,d.orders,width=98,align='edge',color=blue)
a.axvline(s['mean_amount'],color=gold,linewidth=1.8,label=f"均值 {s['mean_amount']:.2f} 元")
a.axvline(s['median_amount'],color=gray,linestyle='--',linewidth=1.8,label=f"中位数 {s['median_amount']:.2f} 元")
a.set(xlabel='订单金额（元；组距100元）',xlim=(0,1400));a.legend(frameon=False)
save(f,'01_订单金额分布.png')
d=read('category_counts');f,a=fig('护肤占订单量48.23%，为第一大品类','')
a.barh(d.category,d.orders,color=blue);a.invert_yaxis();a.set_xlabel('订单数（单）');a.grid(False);a.grid(axis='x',color='#E6E9EE');a.set_xlim(0,d.orders.max()*1.32)
for i,r in d.iterrows(): a.text(r.orders+500,i,f'{r.orders:,}  ({r.share:.2%})',va='center')
save(f,'02_商品品类频数.png')
d=read('quantity_counts');f,a=fig('每单商品数量：1至5件分布接近均匀','订单数（单）')
a.bar(d.quantity,d.orders,color=blue,width=.65);a.set(xlabel='每单商品数量（件）',xticks=d.quantity,ylim=(0,d.orders.max()*1.2))
for _,r in d.iterrows():a.text(r.quantity,r.orders+200,f'{int(r.orders):,}\n{r.share:.2%}',ha='center',va='bottom',fontsize=11)
save(f,'03_每单商品数量.png')
d=read('customer_frequency');f,a=fig('客户购买频次：单次客户4,554人，占30.36%','客户数（人）')
a.bar(d.frequency,d.customers,color=[gold if n==1 else blue for n in d.frequency],width=.85)
a.set(xlabel='2023-01-01至2024-12-30购买次数（次）',xticks=[1,5,10,15,20,25,30,32],xlim=(.3,32.7))
a.text(.98,.92,f"人均 {s['mean_frequency']:.2f} 单；中位数 {s['median_frequency']:.0f} 单\n分母：15,000位有订单记录的客户",transform=a.transAxes,ha='right',va='top')
save(f,'04_客户购买频次.png')
d=read('daily_orders');d.date=pd.to_datetime(d.date);f,a=fig('每日订单量：阶段变化与记录空档并存','订单数（单）')
a.plot(d.date,d.orders,color=blue,alpha=.45,lw=.8,label='每日订单量')
a.plot(d.date,d.avg7,color=gold,lw=2,label='7日移动平均')
a.axvspan(pd.Timestamp('2023-05-31'),pd.Timestamp('2023-06-30'),color=gray,alpha=.12)
a.annotate('2023-12-29：331单',xy=(pd.Timestamp('2023-12-29'),331),xytext=(pd.Timestamp('2024-04-01'),350),arrowprops={'arrowstyle':'-','color':gray},fontsize=10)
a.set(ylim=(0,380),xlim=(d.date.min(),d.date.max()),xlabel='日期；无记录日期按文件记录计数补零，不代表已确认实际零交易')
ticks=list(pd.date_range('2023-01-01','2024-12-01',freq='4MS'))+[d.date.max()]
a.set_xticks(ticks);a.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'));a.tick_params(axis='x',labelsize=10);a.legend(frameon=False,loc='upper left')
save(f,'05_每日订单量.png')
print('Generated 5 PNG charts in',OUT)
