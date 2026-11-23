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

留存均值从 2010-01 这一批开始，按批次人数加权，格子先保留四位小数。2009-12 含更早的老客户。热力图把这批淡化，CSV 的 `excluded_from_average` 为 1，均值不用它。

`cohort_retention.csv` 里，已经观察到的月份写回购比例。该月没人回购就写 0。还没观察到的月份留空。`partial_offsets` 标出落在不完整末月的列号。

2011-12 只观察到 12 月 9 日。这些格子留在矩阵和热力图里，并标成部分月。完整月均值不用它们。第 1 个月是 20.97%，第 12 个月是 18.43%。把这个不完整月算进去的旧快照是 20.71% 和 18.07%，记在 `retention.with_partial_month`。

2010-01 这批在 2010-02 的回购率是 21.47%。页面上 9～11 月的黄色只标记这两年的位置。颜色越深，回购比例越高。

原始表有 43 个不同的国家字符串，清洗后是 41 个。原始 1,067,371 行和清洗后的国家数分开写。

原始明细缺客户号 243,007 / 1,067,371，占 22.77%。去重并删除取消单之后，这一步删除 234,437 / 1,013,932，占 23.12%，相当于原始记录的 21.96%。£3,101,456.18 是这一步之前、缺客户号行里数量乘单价的正金额。

两张工作表按全部八列完全相同的取值有 22,202 种。对每种取值取两表出现次数的较小值，配对得到 22,523 行，时间在 2010-12-01 至 2010-12-09。合并去重后剩 1,033,036 行，删除 34,335 行。两种分解都等于这个删除数：表内多余 6,865 + 5,268 + 共有取值 22,202，以及配对 22,523 + 其余重复 11,812。

金额是英镑营收。数据没有成本字段。

网页的封面、细页、图、动画目标和无障碍标签都读 `site/data.js`。更换这份汇总后，这些位置跟着变。

数据引用：Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D
