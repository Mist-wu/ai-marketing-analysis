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


ROW_COLS = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "CustomerID", "Country"]


def load() -> pd.DataFrame:
    sheets = pd.read_excel(SRC, sheet_name=None, dtype={"Invoice": str, "StockCode": str, "Description": "string"})
    return pd.concat([frame.assign(_sheet=name) for name, frame in sheets.items()],
                     ignore_index=True).rename(columns={"Customer ID": "CustomerID"})


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


def rf_segment_grid() -> list[list[str]]:
    """R×F 格子的分群。网页只读这张表，不再另写一套正则。"""
    grid = []
    for r in range(1, 6):
        row = []
        for f in range(1, 6):
            code = f"{r}{f}"
            row.append(next(key for pattern, key, _ in SEGMENTS if re.fullmatch(pattern, code)))
        grid.append(row)
    return grid


def rfm(df: pd.DataFrame, grid: list[list[str]]) -> tuple[pd.DataFrame, pd.Timestamp]:
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
    t["segment"] = np.asarray(grid)[t["R"] - 1, t["F"] - 1]
    return t, snapshot


def cohorts(df: pd.DataFrame, t: pd.DataFrame) -> pd.DataFrame:
    month = df["InvoiceDate"].dt.to_period("M")
    first = df["CustomerID"].map(t["first"].dt.to_period("M"))
    active = pd.DataFrame({"cohort": first, "offset": (month - first).apply(lambda p: p.n),
                           "CustomerID": df["CustomerID"]})
    return active.groupby(["cohort", "offset"])["CustomerID"].nunique().unstack(fill_value=0)


def duplicate_account(raw: pd.DataFrame) -> dict:
    """相同八列共用一个编号；两表出现次数的较小值是可配对行数。"""
    row_ids = raw.groupby(ROW_COLS, dropna=False, sort=False).ngroup()
    per = []
    counts = []
    for name, ids in row_ids.groupby(raw["_sheet"], sort=False):
        freq = ids.value_counts()
        per.append({"sheet": name, "rows": len(ids), "unique_rows": len(freq), "extra_rows": len(ids) - len(freq)})
        counts.append(freq)
    if len(counts) != 2:
        raise ValueError(f"跨表配对只定义在两张工作表上，当前是 {len(counts)} 张")
    shared = pd.concat(counts, axis=1, join="inner")
    shared_distinct = len(shared)
    paired_rows = int(shared.min(axis=1).sum())
    merged_rows = row_ids.nunique()
    removed = len(raw) - merged_rows
    assert sum(sheet["extra_rows"] for sheet in per) + shared_distinct == removed
    overlap = raw.loc[row_ids.isin(shared.index), "InvoiceDate"]
    return {
        "sheets": per,
        "shared_distinct": shared_distinct,
        "paired_rows": paired_rows,
        "merged_rows": merged_rows,
        "removed": removed,
        "remaining_duplicates": removed - paired_rows,
        "overlap_start": None if overlap.empty else str(overlap.min().date()),
        "overlap_end": None if overlap.empty else str(overlap.max().date()),
    }


def assemble_cohorts(counts: pd.DataFrame, last_ts: pd.Timestamp, average_from: str = "2010-01"):
    """已观察月份保留数值（含真实 0）；未观察月份不写入。末月未到月末时标为部分月。"""
    last_month = last_ts.to_period("M")
    partial = not last_ts.is_month_end
    size = counts[0]
    ret = counts.div(size, axis=0)
    rows = []
    for c in counts.index:
        max_off = int((last_month - c).n)
        rates = []
        for k in range(0, max_off + 1):
            rates.append(round(float(ret.loc[c, k]), 4) if k in ret.columns else 0.0)
        rows.append({
            "cohort": str(c),
            "size": int(size[c]),
            "retention": rates,
            "partial_offsets": [max_off] if partial else [],
            "excluded_from_average": str(c) < average_from,
        })
    return rows, {
        "average_from": average_from,
        "partial_month": str(last_month) if partial else None,
        "observed_through": str(last_ts.date()),
    }


def weighted_retention(rows: list[dict], k: int, complete_only: bool):
    picked = [row for row in rows if not row["excluded_from_average"] and k < len(row["retention"])
              and not (complete_only and k in row["partial_offsets"])]
    weight = sum(row["size"] for row in picked)
    if not weight:
        return None
    return sum(row["retention"][k] * row["size"] for row in picked) / weight


def retention_frame(rows: list[dict]) -> pd.DataFrame:
    max_k = max(len(row["retention"]) - 1 for row in rows)
    records = []
    for row in rows:
        rec = {"cohort": row["cohort"]}
        for k in range(0, max_k + 1):
            rec[str(k)] = row["retention"][k] if k < len(row["retention"]) else pd.NA
        rec["excluded_from_average"] = int(row["excluded_from_average"])
        rec["partial_offsets"] = ";".join(str(k) for k in row["partial_offsets"])
        records.append(rec)
    return pd.DataFrame(records)


def main():
    raw = load()
    duplicates = duplicate_account(raw)
    raw_rows = len(raw)
    raw_missing = int(raw["CustomerID"].isna().sum())
    raw_countries = int(raw["Country"].dropna().astype(str).nunique())
    df, steps, cancel_rows, no_cust_revenue = clean(raw.drop(columns=["_sheet"]))
    grid = rf_segment_grid()
    t, snapshot = rfm(df, grid)
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
    seg = seg.set_index("segment")
    seg = seg.loc[[key for key in seg_names if key in seg.index]].reset_index()

    # 帕累托：按消费额排序的前 20% 客户
    m_sorted = t["monetary"].sort_values(ascending=False)
    top_n = int(round(n_cust * 0.2))
    top20_share = float(m_sorted.head(top_n).sum() / total_rev)
    curve_x = np.linspace(0, 1, 51)
    cum = m_sorted.cumsum().values / total_rev
    curve = [0.0] + [float(cum[max(0, int(round(x * n_cust)) - 1)]) for x in curve_x[1:]]

    # 留存：未观察月不进入矩阵；部分末月保留数值，但完整月均值把它排除
    last_ts = df["InvoiceDate"].max()
    cohort_rows, retention_meta = assemble_cohorts(counts, last_ts)
    retention_complete = {str(k): weighted_retention(cohort_rows, k, True) for k in (1, 3, 6, 12)}
    retention_partial = {str(k): weighted_retention(cohort_rows, k, False) for k in (1, 3, 6, 12)}

    win_mask = t["segment"].isin(["cant_lose", "at_risk"])
    win = t.loc[win_mask]
    no_cust_step = next(s for s in steps if s[0].startswith("删除缺少客户编号"))
    no_cust_denominator = no_cust_step[1] + no_cust_step[2]

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
        "no_customer": {
            "raw_missing_rows": raw_missing,
            "raw_rows": raw_rows,
            "raw_share": raw_missing / raw_rows,
            "removed_rows": int(no_cust_step[2]),
            "removed_denominator": int(no_cust_denominator),
            "removed_share": no_cust_step[2] / no_cust_denominator,
            "share_of_raw": no_cust_step[2] / raw_rows,
            "positive_revenue": no_cust_revenue,
            "positive_revenue_basis": "去重并删除取消单之后，缺客户号行的数量×单价；负值按 0 计",
        },
        "countries": {
            "raw_strings": raw_countries,
            "clean": int(df["Country"].nunique()),
        },
        "duplicates": duplicates,
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
            "one_purchase_share": float((t["frequency"] == 1).mean()),
        },
        "pareto": {"top20_share": top20_share, "top_n": top_n, "curve": curve},
        "winback": {
            "segments": ["cant_lose", "at_risk"],
            "customers": int(len(win)),
            "revenue": float(win["monetary"].sum()),
            "revenue_share": float(win["monetary"].sum() / total_rev),
            "recency_median": float(win["recency"].median()),
            "recency_min": int(win["recency"].min()),
            "recency_max": int(win["recency"].max()),
        },
        "calendar_highlight": {
            "months": [9, 10, 11],
            "label": "9–11 月",
            "role": "图上的位置标记，用来看这两年的分布，不是因果结论",
        },
        "segments": seg.to_dict("records"),
        "rf_grid": [[int(((t["R"] == r) & (t["F"] == f)).sum()) for f in range(1, 6)] for r in range(1, 6)],
        "rf_segment": grid,
        "cohorts": cohort_rows,
        "retention": {
            **retention_meta,
            "complete": retention_complete,
            "with_partial_month": retention_partial,
            "weight": "average_from 及以后的批次，按批次人数加权；格子先保留四位小数",
            "truncated_note": "平均起点之前的批次含更早的老客户，热力图淡化，不进入均值",
            "partial_note": "末月未到该月最后一天。这些格子保留在矩阵里，完整月均值不使用它们",
        },
        "retention_avg": retention_complete,
        "retention_avg_with_partial_month": retention_partial,
        "monthly": [
            {"month": str(p), "revenue": float(r.revenue), "customers": int(r.customers),
             "orders": int(r.orders), "new": int(new_per_month.get(p, 0))}
            for p, r in monthly.iterrows()
        ],
        "country_revenue": [{"country": c, "revenue": float(v)} for c, v in country.head(8).items()],
    }

    t.reset_index().to_csv(OUT / "rfm_customers.csv", index=False, encoding="utf-8-sig")
    seg.to_csv(OUT / "segments.csv", index=False, encoding="utf-8-sig")
    retention_frame(cohort_rows).to_csv(OUT / "cohort_retention.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(summary["steps"]).to_csv(OUT / "cleaning_steps.csv", index=False, encoding="utf-8-sig")
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    (ROOT / "site" / "data.js").write_text(
        "window.REPORT_DATA = " + json.dumps(summary, ensure_ascii=False) + ";\n")
    print(json.dumps({k: summary[k] for k in (
        "steps", "cancel", "clean", "retention", "duplicates", "no_customer", "countries", "winback")},
                     ensure_ascii=False, indent=1, default=str))
    print("top20", top20_share)
    print(seg[["name", "customers", "customer_share", "revenue_share", "recency", "frequency", "monetary"]])


if __name__ == "__main__":
    main()
