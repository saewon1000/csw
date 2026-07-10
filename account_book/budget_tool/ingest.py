"""지출내역 폴더 일괄 취합.

폴더의 모든 뱅크샐러드 파일을 읽어:
- 거래 내역을 사용자별로 합치고 **중복 제거**(파일 기간이 겹치므로 필수)
- 파일명에서 사용자(접두사)와 기준일(as-of, 두 번째 날짜)을 추론
- 연도별 재무 스냅샷(자산/부채/투자)은 해당 연도에 가장 근접한 파일에서 선택
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

import banksalad

# 파일명 예: 세원_2025-07-10~2026-07-10.xlsx
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})~(\d{4}-\d{2}-\d{2})")

DEDUP_KEYS = ["user", "date", "time", "type", "category", "subcategory",
              "content", "amount", "pay", "memo"]


@dataclass
class SourceFile:
    path: Path
    prefix: str
    user: str
    asof: pd.Timestamp | None


@dataclass
class Snapshot:
    user: str
    asof: pd.Timestamp | None
    assets: pd.DataFrame
    liabilities: pd.DataFrame
    investments: pd.DataFrame


@dataclass
class Ingested:
    txns: pd.DataFrame
    snapshots: list = field(default_factory=list)  # list[Snapshot]
    files: list = field(default_factory=list)      # list[SourceFile]
    warnings: list = field(default_factory=list)


def scan_files(export_dir: Path, name_map: dict) -> list[SourceFile]:
    out = []
    if not export_dir.exists():
        return out
    for p in sorted(export_dir.glob("*.xlsx")):
        if p.name.startswith("~$"):
            continue
        prefix = p.stem.split("_")[0]
        m = DATE_RE.search(p.stem)
        asof = pd.to_datetime(m.group(2)) if m else None
        out.append(
            SourceFile(path=p, prefix=prefix,
                       user=name_map.get(prefix, prefix), asof=asof)
        )
    return out


def ingest_all(export_dir: Path, name_map: dict) -> Ingested:
    files = scan_files(export_dir, name_map)
    txn_frames, snapshots, warnings = [], [], []
    for sf in files:
        try:
            d = banksalad.load_file(str(sf.path), sf.user)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"{sf.path.name}: {e}")
            continue
        if not d.transactions.empty:
            txn_frames.append(d.transactions)
        snapshots.append(
            Snapshot(user=sf.user, asof=sf.asof, assets=d.assets,
                     liabilities=d.liabilities, investments=d.investments)
        )
        warnings.extend(f"[{sf.path.name}] {w}" for w in d.warnings)

    if txn_frames:
        txns = pd.concat(txn_frames, ignore_index=True)
        keys = [k for k in DEDUP_KEYS if k in txns.columns]
        txns = txns.drop_duplicates(subset=keys).reset_index(drop=True)
        txns = txns.sort_values("date").reset_index(drop=True)
        txns["year"] = txns["date"].dt.year
        txns["month"] = txns["date"].dt.month
    else:
        txns = pd.DataFrame()

    return Ingested(txns=txns, snapshots=snapshots, files=files, warnings=warnings)


def _tag(df: pd.DataFrame, user: str) -> pd.DataFrame:
    f = df.copy()
    f.insert(0, "user", user)
    return f


def snapshot_for_year(snapshots: list, year: int) -> dict:
    """연도별 자산/부채/투자: 사용자마다 그 해에 가장 근접한(기준일<=연말 중 최신)
    스냅샷을 선택. 없으면 가장 이른 스냅샷을 사용."""
    year_end = pd.Timestamp(year=year, month=12, day=31)
    users = sorted({s.user for s in snapshots})
    assets, liabs, invs = [], [], []
    for user in users:
        us = [s for s in snapshots if s.user == user and s.asof is not None]
        if not us:
            continue
        candidates = [s for s in us if s.asof <= year_end]
        pick = max(candidates, key=lambda s: s.asof) if candidates \
            else min(us, key=lambda s: s.asof)
        if not pick.assets.empty:
            assets.append(_tag(pick.assets, user))
        if not pick.liabilities.empty:
            liabs.append(_tag(pick.liabilities, user))
        if not pick.investments.empty:
            invs.append(_tag(pick.investments, user))

    def cat(frames, cols):
        return pd.concat(frames, ignore_index=True) if frames \
            else pd.DataFrame(columns=cols)

    return {
        "assets": cat(assets, ["user", "group", "item", "name", "amount"]),
        "liabilities": cat(liabs, ["user", "item", "name", "amount"]),
        "investments": cat(
            invs, ["user", "kind", "broker", "name", "principal", "value", "ret"]),
    }


def files_for_year(files: list, year: int) -> list:
    """해당 연도의 거래를 포함할 수 있는 원본 파일 목록(기간이 연도와 겹치는 파일)."""
    year_start = pd.Timestamp(year=year, month=1, day=1)
    year_end = pd.Timestamp(year=year, month=12, day=31)
    out = []
    for sf in files:
        m = DATE_RE.search(sf.path.stem)
        if not m:
            continue
        start = pd.to_datetime(m.group(1))
        end = pd.to_datetime(m.group(2))
        if start <= year_end and end >= year_start:
            out.append(sf)
    return out
