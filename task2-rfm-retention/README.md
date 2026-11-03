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

## 口径说明

- 观测日：2011-12-10（最后一笔交易的次日）。
- R、M 按五分位打分；F 按固定区间 1 / 2 / 3–4 / 5–8 / 9+ 次，避免购买次数相同的客户被分到不同档。
- 平均留存只统计 2010-01 及以后的批次：数据从 2009-12 开始，首批客户里混有更早的老客户。
- 金额为英镑营收，数据没有成本字段，不代表利润。

数据引用：Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D
