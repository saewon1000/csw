"""설정: 지출내역 폴더 경로와 파일 접두사 → 표시 이름 매핑만 관리.

사용 년도/사용자/파일 경로는 더 이상 수동 설정하지 않고, 지출내역 폴더의 파일에서
자동으로 추론한다.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent  # 상대경로 기준 (repo 내 account_book)
CONFIG_PATH = BASE_DIR / "config.json"
DEFAULT_EXPORT_DIR = "지출내역"


def resolve_path(p: str) -> Path:
    """config에 저장된 경로(상대/절대)를 절대 경로로 변환."""
    if not p:
        return Path("")
    path = Path(p)
    return path if path.is_absolute() else (ROOT_DIR / path)


@dataclass
class AppConfig:
    export_dir: str = DEFAULT_EXPORT_DIR
    # 파일명 접두사(예: 세원) → 표시 이름(예: 천세원)
    user_names: dict = field(default_factory=lambda: {"세원": "천세원", "유진": "하유진"})

    @classmethod
    def default(cls) -> "AppConfig":
        return cls()


def load_config() -> AppConfig:
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return AppConfig(
            export_dir=data.get("export_dir", DEFAULT_EXPORT_DIR),
            user_names=data.get("user_names", AppConfig.default().user_names),
        )
    cfg = AppConfig.default()
    save_config(cfg)
    return cfg


def save_config(cfg: AppConfig) -> None:
    CONFIG_PATH.write_text(
        json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8"
    )
