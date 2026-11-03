"""UCI Online Retail II：数据清洗、RFM 客户分群与按首购月份的留存分析。

用法：python scripts/analyze.py [data/online_retail_II.xlsx]
输出：results/*.csv 与 site/data.js（网页读取的汇总数据）。
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "online_retail_II.xlsx"
OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)

# 非商品行：邮费、手工调整、银行手续费、平台费、样品、测试等
NON_PRODUCT = {"POST", "DOT", "M", "C2", "D", "S", "B", "BANK CHARGES", "AMAZONFEE",
               "ADJUST", "ADJUST2", "CRUK", "PADS", "TEST001", "TEST002", "SP1002"}

# 购买次数分档：1 / 2 / 3–4 / 5–8 / 9 次及以上
F_BINS = [0, 1, 2, 4, 8, np.inf]

# R、F 两位评分 → 分群（按顺序匹配）
SEGMENTS = [
    (r"5[4-5]", "champions", "冠军客户"),
    (r"[3-4][4-5]", "loyal", "忠诚客户"),
    (r"[4-5][2-3]", "potential", "潜力客户"),
    (r"51", "new", "新客户"),
    (r"41", "promising", "有望培养"),
    (r"33", "attention", "需要关注"),
    (r"3[1-2]", "sleepy", "即将沉睡"),
    (r"[1-2]5", "cant_lose", "不能失去"),
    (r"[1-2][3-4]", "at_risk", "流失风险"),
    (r"[1-2][1-2]", "hibernating", "已休眠"),
]


def load() -> pd.DataFrame:
    sheets = pd.read_excel(SRC, sheet_name=None, dtype={"Invoice": str, "StockCode": str})
    df = pd.concat(sheets.values(), ignore_index=True)
    df["Description"] = df["Description"].astype("string")
    return df.rename(columns={"Customer ID": "CustomerID"})


def clean(raw: pd.DataFrame):
    steps = [("原始记录（两个工作表合并）", len(raw), None)]
    df = raw.drop_duplicates()
    steps.append(("删除完全重复行", len(df), len(raw) - len(df)))

    cancel = df["Invoice"].str.startswith("C")
    cancel_rows = df[cancel]
    df = df[~cancel]
    steps.append(("删除取消单（发票号以 C 开头）", len(df), int(cancel.sum())))

    no_cust = df["CustomerID"].isna()
    no_cust_revenue = float((df.loc[no_cust, "Quantity"] * df.loc[no_cust, "Price"]).clip(lower=0).sum())
    df = df[~no_cust]
    steps.append(("删除缺少客户编号的记录", len(df), int(no_cust.sum())))

    non_product = df["StockCode"].str.upper().isin(NON_PRODUCT)
    df = df[~non_product]
    steps.append(("删除邮费、手续费等非商品行", len(df), int(non_product.sum())))

    bad = (df["Quantity"] <= 0) | (df["Price"] <= 0)
    df = df[~bad]
    steps.append(("删除数量或单价非正的记录", len(df), int(bad.sum())))

    df = df.copy()
    df["CustomerID"] = df["CustomerID"].astype(int)
    df["Revenue"] = df["Quantity"] * df["Price"]
    return df, steps, cancel_rows, no_cust_revenue


def rfm(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Timestamp]:
    snapshot = df["InvoiceDate"].max().normalize() + pd.Timedelta(days=1)
    g = df.groupby("CustomerID")
    t = pd.DataFrame({
        "recency": (snapshot - g["InvoiceDate"].max()).dt.days,
        "frequency": g["Invoice"].nunique(),
        "monetary": g["Revenue"].sum(),
        "first": g["InvoiceDate"].min(),
    })
    # R、M 按五分位；频次并列太多（27% 只买过 1 次），改用接近五分位的固定区间，
    # 保证购买次数相同的客户得分相同
    t["R"] = pd.qcut(t["recency"], 5, labels=[5, 4, 3, 2, 1]).astype(int)
    t["F"] = pd.cut(t["frequency"], F_BINS, labels=[1, 2, 3, 4, 5]).astype(int)
    t["M"] = pd.qcut(t["monetary"], 5, labels=[1, 2, 3, 4, 5]).astype(int)
    rf = t["R"].astype(str) + t["F"].astype(str)
    t["segment"] = None
    for pattern, key, _ in SEGMENTS:
        hit = t["segment"].isna() & rf.str.fullmatch(pattern)
        t.loc[hit, "segment"] = key
    assert t["segment"].notna().all()
    return t, snapshot


def cohorts(df: pd.DataFrame, t: pd.DataFrame) -> pd.DataFrame:
    month = df["InvoiceDate"].dt.to_period("M")
    first = df["CustomerID"].map(t["first"].dt.to_period("M"))
    active = pd.DataFrame({"cohort": first, "offset": (month - first).apply(lambda p: p.n),
                           "CustomerID": df["CustomerID"]}).drop_duplicates()
    counts = active.groupby(["cohort", "offset"])["CustomerID"].nunique().unstack(fill_value=0)
    return counts


def main():
    raw = load()
    df, steps, cancel_rows, no_cust_revenue = clean(raw)
    t, snapshot = rfm(df)
    counts = cohorts(df, t)

    total_rev = float(df["Revenue"].sum())
    n_cust = len(t)
    seg_names = {k: zh for _, k, zh in SEGMENTS}
    seg = (t.groupby("segment")
             .agg(customers=("R", "size"), revenue=("monetary", "sum"),
                  recency=("recency", "median"), frequency=("frequency", "median"),
                  monetary=("monetary", "median"))
             .reset_index())
    seg["name"] = seg["segment"].map(seg_names)
    seg["customer_share"] = seg["customers"] / n_cust
    seg["revenue_share"] = seg["revenue"] / total_rev
    order = [k for _, k, _ in SEGMENTS]
    seg = seg.set_index("segment").loc[[k for k in order if k in set(seg["segment"])]].reset_index()

    # 帕累托：按消费额排序的前 20% 客户
    m_sorted = t["monetary"].sort_values(ascending=False)
    top20_share = float(m_sorted.head(int(round(n_cust * 0.2))).sum() / total_rev)
    curve_x = np.linspace(0, 1, 51)
    cum = m_sorted.cumsum().values / total_rev
    curve = [0.0] + [float(cum[max(0, int(round(x * n_cust)) - 1)]) for x in curve_x[1:]]

    # 留存率矩阵
    size = counts[0]
    ret = counts.div(size, axis=0)
    last_month = df["InvoiceDate"].max().to_period("M")
    cohort_rows = []
    for c in counts.index:
        max_off = (last_month - c).n
        cohort_rows.append({
            "cohort": str(c), "size": int(size[c]),
            "retention": [round(float(ret.loc[c, k]), 4) for k in range(0, max_off + 1)],
        })

    def avg_ret(k, start="2010-01"):
        rows = [r for r in cohort_rows if r["cohort"] >= start and len(r["retention"]) > k]
        w = sum(r["size"] for r in rows)
        return sum(r["retention"][k] * r["size"] for r in rows) / w if w else None

    monthly = (df.groupby(df["InvoiceDate"].dt.to_period("M"))
                 .agg(revenue=("Revenue", "sum"), customers=("CustomerID", "nunique"),
                      orders=("Invoice", "nunique")))
    new_per_month = t["first"].dt.to_period("M").value_counts().sort_index()

    country = df.groupby("Country")["Revenue"].sum().sort_values(ascending=False)
    cust_country = df.groupby("CustomerID")["Country"].agg(lambda s: s.mode().iat[0])

    summary = {
        "source": {
            "name": "Online Retail II", "publisher": "UCI Machine Learning Repository",
            "url": "https://archive.ics.uci.edu/dataset/502/online+retail+ii",
            "doi": "10.24432/C5CG6D", "license": "CC BY 4.0",
            "start": str(raw["InvoiceDate"].min().date()), "end": str(raw["InvoiceDate"].max().date()),
        },
        "steps": [{"label": a, "rows": int(b), "removed": None if c is None else int(c)} for a, b, c in steps],
        "cancel": {
            "invoices": int(cancel_rows["Invoice"].nunique()),
            "rows": len(cancel_rows),
            "invoice_share": cancel_rows["Invoice"].nunique() / raw["Invoice"].nunique(),
        },
        "no_customer_revenue": no_cust_revenue,
        "clean": {
            "rows": len(df), "customers": n_cust, "invoices": int(df["Invoice"].nunique()),
            "products": int(df["StockCode"].nunique()), "countries": int(df["Country"].nunique()),
            "revenue": total_rev, "snapshot": str(snapshot.date()),
            "repeat_share": float((t["frequency"] > 1).mean()),
            "median_frequency": float(t["frequency"].median()),
            "median_monetary": float(t["monetary"].median()),
            "mean_monetary": float(t["monetary"].mean()),
            "uk_revenue_share": float(country.get("United Kingdom", 0) / total_rev),
            "uk_customer_share": float((cust_country == "United Kingdom").mean()),
        },
        "pareto": {"top20_share": top20_share, "curve": curve},
        "segments": [
            {k: (v.item() if hasattr(v, "item") else v) for k, v in r.items()}
            for r in seg.to_dict("records")
        ],
        "rf_grid": [[int(((t["R"] == r) & (t["F"] == f)).sum()) for f in range(1, 6)] for r in range(1, 6)],
        "cohorts": cohort_rows,
        "retention_avg": {k: avg_ret(k) for k in (1, 3, 6, 12)},
        "monthly": [
            {"month": str(p), "revenue": float(r.revenue), "customers": int(r.customers),
             "orders": int(r.orders), "new": int(new_per_month.get(p, 0))}
            for p, r in monthly.iterrows()
        ],
        "countries": [{"country": c, "revenue": float(v)} for c, v in country.head(8).items()],
    }

    t.reset_index().to_csv(OUT / "rfm_customers.csv", index=False, encoding="utf-8-sig")
    seg.to_csv(OUT / "segments.csv", index=False, encoding="utf-8-sig")
    ret.round(4).to_csv(OUT / "cohort_retention.csv", encoding="utf-8-sig")
    pd.DataFrame(summary["steps"]).to_csv(OUT / "cleaning_steps.csv", index=False, encoding="utf-8-sig")
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    (ROOT / "site" / "data.js").write_text(
        "window.REPORT_DATA = " + json.dumps(summary, ensure_ascii=False) + ";\n")
    print(json.dumps({k: summary[k] for k in ("steps", "cancel", "clean", "retention_avg")},
                     ensure_ascii=False, indent=1, default=str))
    print("top20", top20_share)
    print(seg[["name", "customers", "customer_share", "revenue_share", "recency", "frequency", "monetary"]])


if __name__ == "__main__":
    main()
