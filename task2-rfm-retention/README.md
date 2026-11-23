# 第二题：谁在撑起营收？RFM 客户分群与复购分析

用 UCI Online Retail II（英国一家线上礼品零售商 2009-12 至 2011-12 的约 107 万条交易）做三件事：

1. 数据清洗：去重复行、取消单、无客户编号记录和非商品行，每一步记录删除数；
2. RFM 打分与 10 个客户群，统计各群人数与营收贡献；
3. 按首购月份分批的留存热力图，可切换“距首购月数 / 日历月份”两种横轴。

网页 `site/index.html` 同时是报告和演示稿：按 `P` 进入演示模式，方向键翻页；在留存那一页多按一次方向键会切换到日历月视图。

## 重算

```bash
uv venv && uv pip install pandas numpy openpyxl
mkdir -p data && curl -L -o data/online_retail_ii.zip "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip" && unzip -o data/online_retail_ii.zip -d data
.venv/bin/python scripts/analyze.py
```

脚本输出 `results/` 下的汇总 CSV、`summary.json`，以及网页读取的 `site/data.js`。原始数据不入库。

## 本地预览与部署

```bash
python3 -m http.server 8766 --directory site
npx wrangler pages deploy site --project-name x6c --branch main
```

## 口径

观测截止 2011-12-09。快照日是次日 2011-12-10。

R、M 按五分位打分。F 用固定区间：1 次、2 次、3～4 次、5～8 次、9 次及以上。购买次数相同的客户落在同一档。

留存均值从 2010-01 首购批次开始，按批次人数加权，先将每格回购比例保留四位小数。2009-12 含更早的老客户，在热力图中淡化，CSV 的 `excluded_from_average` 为 1。

`cohort_retention.csv` 中，已观察且无人回购的月份写 0，未观察的月份留空。`partial_offsets` 标出落在 2011-12 的列，这个月只观察到 9 日。矩阵保留这些格子，`retention.complete` 排除它们，`retention.with_partial_month` 供对照。日历视图的黄色只标记 9～11 月的位置，深浅表示回购比例。

两张工作表按八列完全相同的取值配对，每种取两表出现次数的较小值。原始国家数按不同字符串统计。缺客户号比例分别以原始总行数和去重、删取消单后的行数为分母，未归户正金额使用后一口径。英镑金额是营收，数据没有成本字段。

数据引用：Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D
