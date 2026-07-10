"""집계/작업 데이터를 Git 친화적인 CSV/JSON로 저장·로드.

작업본(working copy) 모델:
- 뱅크샐러드에서 최초로 불러온 데이터를 data/<년도>/ 에 CSV로 저장(시드).
- 이후 웹에서 편집한 내용도 같은 CSV에 저장되어 유지된다.
- 트렌드 분석용으로 여러 해의 CSV를 합쳐서 읽는다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

TXN_COLS = ["user", "date", "type", "category", "subcategory",
            "content", "amount", "pay", "memo"]
ASSET_COLS = ["user", "group", "item", "name", "amount"]
LIAB_COLS = ["user", "item", "name", "amount"]
INV_COLS = ["user", "kind", "broker", "name", "principal", "value", "ret"]


def year_dir(year: int) -> Path:
    d = DATA_DIR / str(year)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _txn_path(year: int) -> Path:
    return DATA_DIR / str(year) / "transactions.csv"


def working_exists(year: int) -> bool:
    return _txn_path(year).exists()


# ------------------------------------------------------------------- 저장
def save_transactions(df: pd.DataFrame, year: int) -> Path:
    d = year_dir(year)
    path = d / "transactions.csv"
    out = df[[c for c in TXN_COLS if c in df.columns]].copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _save_frame(df: pd.DataFrame, cols: list, path: Path) -> None:
    out = df.reindex(columns=cols) if not df.empty else pd.DataFrame(columns=cols)
    out.to_csv(path, index=False, encoding="utf-8-sig")


def save_financial_state(assets, liabilities, investments, year: int) -> None:
    d = year_dir(year)
    _save_frame(assets, ASSET_COLS, d / "assets.csv")
    _save_frame(liabilities, LIAB_COLS, d / "liabilities.csv")
    _save_frame(investments, INV_COLS, d / "investments.csv")


def save_working(data: dict, year: int) -> None:
    """작업본 전체(거래/자산/부채/투자) 저장."""
    save_transactions(data["txns"], year)
    save_financial_state(
        data["assets"], data["liabilities"], data["investments"], year
    )


def save_summary(summary: dict, year: int) -> None:
    d = year_dir(year)
    (d / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ------------------------------------------------------------------- 로드
def _read(path: Path, cols: list) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=cols)
    return pd.read_csv(path, encoding="utf-8-sig")


def load_transactions(year: int) -> pd.DataFrame:
    df = _read(_txn_path(year), TXN_COLS)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    return df


def load_working(year: int) -> dict:
    d = DATA_DIR / str(year)
    return {
        "txns": load_transactions(year),
        "assets": _read(d / "assets.csv", ASSET_COLS),
        "liabilities": _read(d / "liabilities.csv", LIAB_COLS),
        "investments": _read(d / "investments.csv", INV_COLS),
    }


def list_saved_years() -> list[int]:
    if not DATA_DIR.exists():
        return []
    years = []
    for p in DATA_DIR.iterdir():
        if p.is_dir() and p.name.isdigit() and (p / "transactions.csv").exists():
            years.append(int(p.name))
    return sorted(years)


def load_all_transactions() -> pd.DataFrame:
    """저장된 모든 연도의 거래를 하나로 합침 (트렌드용)."""
    frames = []
    for y in list_saved_years():
        df = load_transactions(y)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame(columns=TXN_COLS + ["year", "month"])
    return pd.concat(frames, ignore_index=True)


def load_all_summaries() -> pd.DataFrame:
    """연도별 summary.json 을 모아 순자산 스냅샷 시계열로 반환."""
    rows = []
    for y in list_saved_years():
        p = DATA_DIR / str(y) / "summary.json"
        if p.exists():
            s = json.loads(p.read_text(encoding="utf-8"))
            rows.append(
                {
                    "year": y,
                    "total_asset": s.get("total_asset", 0),
                    "total_liability": s.get("total_liability", 0),
                    "net_worth": s.get("net_worth", 0),
                }
            )
    return pd.DataFrame(rows)
