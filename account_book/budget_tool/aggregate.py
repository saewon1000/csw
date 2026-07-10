"""거래 내역 기반 집계 로직.

VBA 가계부의 월별 시트 / 손익계산서 / 재무상태표를 거래 원본 데이터로부터
동적으로 계산한다.
"""
from __future__ import annotations

import pandas as pd

# 타입 정규화: 뱅크샐러드는 수입/지출/이체 사용
INCOME = "수입"
EXPENSE = "지출"
TRANSFER = "이체"


def filter_year(df: pd.DataFrame, year: int) -> pd.DataFrame:
    if df.empty:
        return df
    return df[df["year"] == year].copy()


def monthly_table(df: pd.DataFrame, year: int, month: int, ttype: str) -> pd.DataFrame:
    """특정 연/월/타입의 거래를 분류·내용·금액으로 반환 (월별 시트의 표)."""
    if df.empty:
        return pd.DataFrame(columns=["분류", "내용", "금액"])
    sub = df[(df["year"] == year) & (df["month"] == month) & (df["type"] == ttype)]
    out = sub[["category", "content", "amount"]].rename(
        columns={"category": "분류", "content": "내용", "amount": "금액"}
    )
    return out.reset_index(drop=True)


def category_summary(df: pd.DataFrame, year: int, month: int, ttype: str) -> pd.DataFrame:
    """월/타입별 카테고리 합계 (내림차순)."""
    if df.empty:
        return pd.DataFrame(columns=["분류", "금액"])
    sub = df[(df["year"] == year) & (df["month"] == month) & (df["type"] == ttype)]
    if sub.empty:
        return pd.DataFrame(columns=["분류", "금액"])
    g = (
        sub.groupby("category")["amount"]
        .sum()
        .abs()
        .sort_values(ascending=False)
        .reset_index()
    )
    g.columns = ["분류", "금액"]
    return g


def monthly_totals(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """월(1~12)별 수입/지출/이체/순이익 합계."""
    rows = []
    ydf = filter_year(df, year)
    for m in range(1, 13):
        mdf = ydf[ydf["month"] == m]
        income = mdf[mdf["type"] == INCOME]["amount"].sum()
        expense = mdf[mdf["type"] == EXPENSE]["amount"].sum()
        transfer = mdf[mdf["type"] == TRANSFER]["amount"].sum()
        rows.append(
            {
                "월": m,
                "수입": income,
                "지출": abs(expense),
                "이체": transfer,
                "순이익": income + expense,  # 지출은 음수이므로 더함
            }
        )
    return pd.DataFrame(rows)


def income_statement(df: pd.DataFrame, year: int, month: int) -> dict:
    """손익계산서: 이번 달 카테고리별 지출 vs 평균, 상위 지출, 수입/지출 요약."""
    ydf = filter_year(df, year)
    exp = ydf[ydf["type"] == EXPENSE].copy()
    exp["amount"] = exp["amount"].abs()

    # 데이터가 있는 월 수 (평균 산출용)
    active_months = sorted(exp[exp["amount"] > 0]["month"].unique().tolist())
    n_months = max(len(active_months), 1)

    # 카테고리별: 이번 달, 평균
    this_month = (
        exp[exp["month"] == month].groupby("category")["amount"].sum()
    )
    total_by_cat = exp.groupby("category")["amount"].sum()
    avg_by_cat = total_by_cat / n_months

    cats = sorted(set(this_month.index) | set(avg_by_cat.index))
    rows = []
    for c in cats:
        tm = float(this_month.get(c, 0))
        av = float(avg_by_cat.get(c, 0))
        rows.append(
            {
                "분류": c,
                "이번달": tm,
                "평균": av,
                "차이": tm - av,
                "평균대비": (tm / av - 1) if av else None,
            }
        )
    cat_df = pd.DataFrame(rows).sort_values("이번달", ascending=False).reset_index(drop=True)

    inc = ydf[(ydf["type"] == INCOME) & (ydf["month"] == month)]
    income_total = inc["amount"].sum()
    expense_total = this_month.sum()

    return {
        "categories": cat_df,
        "income_total": float(income_total),
        "expense_total": float(expense_total),
        "net": float(income_total - expense_total),
        "n_months": n_months,
    }


def user_totals(df: pd.DataFrame, year: int, month: int | None = None) -> pd.DataFrame:
    """사용자별 수입/지출/순이익 총계 (+ 합계 행). month 지정 시 해당 월만."""
    d = filter_year(df, year)
    if not d.empty and month is not None:
        d = d[d["month"] == month]
    rows = []
    users = sorted(d["user"].unique().tolist()) if not d.empty else []
    for u in users:
        ud = d[d["user"] == u]
        inc = ud[ud["type"] == INCOME]["amount"].sum()
        exp = ud[ud["type"] == EXPENSE]["amount"].sum()
        rows.append({"사용자": u, "수입": inc, "지출": abs(exp), "순이익": inc + exp})
    out = pd.DataFrame(rows, columns=["사용자", "수입", "지출", "순이익"])
    if not out.empty:
        total = {
            "사용자": "합계",
            "수입": out["수입"].sum(),
            "지출": out["지출"].sum(),
            "순이익": out["순이익"].sum(),
        }
        out = pd.concat([out, pd.DataFrame([total])], ignore_index=True)
    return out


def monthly_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    """연-월(YYYY-MM) 단위 수입/지출/순이익 시계열 (여러 해 통합)."""
    if df.empty:
        return pd.DataFrame(columns=["연월", "수입", "지출", "순이익"])
    g = df.copy()
    g["연월"] = pd.to_datetime(g["date"]).dt.to_period("M").astype(str)
    inc = g[g["type"] == INCOME].groupby("연월")["amount"].sum()
    exp = g[g["type"] == EXPENSE].groupby("연월")["amount"].sum().abs()
    out = pd.DataFrame({"수입": inc, "지출": exp}).fillna(0)
    out = out.reindex(sorted(out.index)).reset_index()
    out.columns = ["연월", "수입", "지출"]
    out["순이익"] = out["수입"] - out["지출"]
    return out


def financial_state(assets: pd.DataFrame, liabilities: pd.DataFrame) -> dict:
    """자산/부채 그룹별 합계 및 순자산."""
    if assets.empty:
        by_group = pd.DataFrame(columns=["group", "amount"])
        by_item = pd.DataFrame(columns=["group", "item", "amount"])
        total_asset = 0.0
    else:
        by_group = assets.groupby("group")["amount"].sum().reset_index()
        by_item = assets.groupby(["group", "item"])["amount"].sum().reset_index()
        total_asset = float(assets["amount"].sum())
    total_liab = float(liabilities["amount"].sum()) if not liabilities.empty else 0.0
    return {
        "by_group": by_group,
        "by_item": by_item,
        "total_asset": total_asset,
        "total_liability": total_liab,
        "net_worth": total_asset - total_liab,
    }
