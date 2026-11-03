"""复现实训手册任务一。运行：python analyze_orders.py [orders.xlsx]
依赖：pandas numpy openpyxl matplotlib。只读取原始文件，不改写数据。
"""
from pathlib import Path
import sys, json, hashlib, shutil
from datetime import datetime, timezone
from collections import Counter
from decimal import Decimal
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'sources' / 'orders.xlsx'
OUT = ROOT / 'results'
OUT.mkdir(exist_ok=True)
df = pd.read_excel(SOURCE, sheet_name='orders')
required = ['order_id', 'customer_id', 'order_date', 'order_amount', 'product_category', 'quantity']
assert list(df.columns) == required
df['order_date'] = pd.to_datetime(df['order_date'], errors='raise').dt.normalize()
n, nc = len(df), df.customer_id.nunique()
quality = {
    '记录数': n, '客户数': nc, '字段数': len(df.columns),
    '缺失单元格': int(df.isna().sum().sum()),
    '重复订单号': int(df.order_id.duplicated().sum()),
    '整行重复': int(df.duplicated().sum()),
    '非正金额': int((df.order_amount <= 0).sum()),
    '数量非正或非整数': int(((df.quantity <= 0) | (df.quantity % 1 != 0)).sum()),
    '未识别品类': int((~df.product_category.isin(['护肤','彩妆','个护','香水'])).sum()),
}
assert all(v == 0 for k,v in quality.items() if k not in ['记录数','客户数','字段数'])
freq = df.groupby('customer_id').size()
daily = df.groupby('order_date').size().reindex(pd.date_range(df.order_date.min(), df.order_date.max()), fill_value=0)
avg7 = daily.rolling(7, min_periods=7).mean()
hist, edges = np.histogram(df.order_amount, bins=np.arange(0, 1500, 100))
amount_rows = [{'bin': f'{int(a)}–{int(b)}', 'lower': int(a), 'upper': int(b), 'orders': int(c), 'share': float(c/n)} for a,b,c in zip(edges[:-1],edges[1:],hist)]
cat = df.groupby('product_category').agg(orders=('order_id','size'),amount=('order_amount','sum')).sort_values('orders',ascending=False)
category_rows = [{'category':k,'orders':int(r.orders),'share':float(r.orders/n),'amount':round(float(r.amount),2)} for k,r in cat.iterrows()]
quantity_rows = [{'quantity':int(k),'orders':int(v),'share':float(v/n)} for k,v in df.quantity.value_counts().sort_index().items()]
frequency_rows = [{'frequency':int(k),'customers':int(v),'share':float(v/nc)} for k,v in freq.value_counts().sort_index().items()]
daily_rows = [{'date':k.strftime('%Y-%m-%d'),'orders':int(v),'avg7':None if pd.isna(avg7.loc[k]) else round(float(avg7.loc[k]),3)} for k,v in daily.items()]
month = df.groupby(df.order_date.dt.to_period('M')).size().reindex(pd.period_range(df.order_date.min(),df.order_date.max(),freq='M'),fill_value=0)
monthly_rows = [{'month':str(k),'orders':int(v)} for k,v in month.items()]
q = daily.quantile([.25,.75]); iqr=float(q.loc[.75]-q.loc[.25]); high=float(q.loc[.75]+1.5*iqr)
summary = {
 'orders':n,'customers':nc,'start':str(df.order_date.min().date()),'end':str(df.order_date.max().date()),
 'mean_amount':float(df.order_amount.mean()),'median_amount':float(df.order_amount.median()),
 'min_amount':float(df.order_amount.min()),'max_amount':float(df.order_amount.max()),
 'p95_amount':float(df.order_amount.quantile(.95)), 'total_amount':round(float(df.order_amount.sum()),2),
 'mean_quantity':float(df.quantity.mean()), 'mean_frequency':float(freq.mean()),'median_frequency':float(freq.median()),
 'single_customers':int((freq==1).sum()),'single_share':float((freq==1).mean()),
 'days':len(daily),'days_with_records':int((daily>0).sum()),'no_record_days':int((daily==0).sum()),
 'daily_mean':float(daily.mean()),'daily_median':float(daily.median()),
 'peak_date':str(daily.idxmax().date()),'peak_orders':int(daily.max()),
 'iqr_high_threshold':high,'high_outlier_days':int((daily>high).sum()),
 'y2023':int((df.order_date.dt.year==2023).sum()),'y2024_through_dec30':int((df.order_date.dt.year==2024).sum()),
 'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
 'quality':quality,'categories':category_rows,'monthly':monthly_rows,
}
# 独立复核：以 Python Counter 和 Decimal 复算，不沿用 pandas 汇总结果。
assert Counter(df.product_category) == {r['category']:r['orders'] for r in category_rows}
assert Counter(Counter(df.customer_id).values()) == {r['frequency']:r['customers'] for r in frequency_rows}
assert sum(hist) == sum(r['orders'] for r in category_rows) == sum(daily) == n
assert sum(r['customers'] for r in frequency_rows) == nc
assert sum(r['frequency']*r['customers'] for r in frequency_rows) == n
assert Decimal(str(summary['total_amount'])) == sum(Decimal(str(v)) for v in df.order_amount)
assert n == 87801 and nc == 15000
datasets={'amount_distribution':amount_rows,'category_counts':category_rows,'quantity_counts':quantity_rows,'customer_frequency':frequency_rows,'daily_orders':daily_rows,'monthly_orders':monthly_rows,'overview':[summary | {'quality':None,'categories':None,'monthly':None}], 'data_quality':[{'check':k,'value':v} for k,v in quality.items()]}
for key,rows in datasets.items():
    pd.DataFrame(rows).to_csv(OUT / f'{key}.csv',index=False,encoding='utf-8-sig')
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
base_source={
 'label':'云邮教学空间《AI与市场营销》课程配套 orders.xlsx',
 'files':['orders.xlsx / orders!A1:F87802'],
 'links':[{'label':'课程文件原件','url':'https://fileucloud.bupt.edu.cn/ucloud/document/cebe782cebfbeeee0e3d2917b11732db.xlsx'}],
 'filters':['全部订单，无抽样、无删行、无缩尾；2023-01-01 至 2024-12-30'],
 'executedAt':datetime.now(timezone.utc).isoformat(),
 'evidenceFlow':[{'title':'原始文件','detail':'在 Safari 中从课程主页下载 orders.xlsx；工作表 orders，87,801 行订单，6 个字段。SHA-256: '+summary['source_sha256']}, {'title':'复现计算','detail':'analyze_orders.py 读取原始表，检查主键和缺失值，按金额、品类、数量、客户、日期聚合；以 Counter、Decimal 独立复核总量。'}],
 'caveats':['课程实训数据，未核验真实企业经营来源。','金额为记录中的订单金额，未提供退款、支付状态或成本，不能解释为净收入或利润。','没有订单记录的日期按记录计数为0，不足以证明实际停业或零交易。']
}
definitions={
 'amount_distribution':('金额频数','按100元左闭右开区间统计订单数，最后区间含右端点；无金额截断。'),
 'category_counts':('品类订单占比','品类订单数 / 全部87,801单；以订单记录的唯一品类字段分组。'),
 'quantity_counts':('每单商品数量','按quantity的整数取值统计订单数，分母为87,801单。'),
 'customer_frequency':('两年购买频次','按customer_id计算全观察窗订单数；客户占比分母为15,000人。网页显示时聚合为1、2-3、4-6、7-10、11及以上五组，源数据保留1-32次完整频数。'),
 'daily_orders':('每日订单量','按日统计订单记录数，补齐730个日历日；7日均线仅在满7日时计算。'),
 'monthly_orders':('月订单量','按自然月统计订单记录数；2024年12月只观察至30日。'),
 'overview':('总体统计','订单金额均值和中位数按订单计算；人均订单数=87,801/15,000；单次客户比例=4,554/15,000。'),
 'data_quality':('数据质量检查','对完整原始表逐项计数，检查主键、缺失、金额、数量与品类。')
}
queries={}
for key, rows in datasets.items():
    label,definition=definitions[key]
    source=base_source | {'metricDefinitions':[{'label':label,'definition':definition,'componentIds':[key, key+'_text'],'sourceLineage':[{'files':base_source['files']}]}]}
    queries[key]={'rows':rows,'source':source,'methods':[{'language':'text','code':definition+' 具体复现代码见作业包 analyze_orders.py。'}]}
snapshot={'surface':'report','title':'美妆电商订单探索性分析','generatedAt':datetime.now(timezone.utc).isoformat(),'status':'reviewed','buildStatus':'creating','filters':[],
 'report':{'title':'美妆电商订单数据探索性分析','subtitle':'《AI与市场营销》平时作业 · 客户资产管理实训任务一','asOf':'2024-12-30'},'queries':queries}
(ROOT/'reviewed.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))
