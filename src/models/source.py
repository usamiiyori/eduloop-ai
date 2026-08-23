"""収集ソースレジストリ（config/sources.yaml）に対応する Pydantic v2 モデル。"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator


class LicenseType(StrEnum):
    """ソースの利用許諾種別。判定不能な場合は UNCONFIRMED を用い、quote_only 相当で扱う。

    PUBLIC_DATA_TERMS_1_0（公共データ利用規約 第1.0版）は2024年7月にデジタル庁が策定した
    政府標準利用規約(第2.0版)の後継。既存サイトが移行済みかは個別確認が必要（2026年時点）。
    """

    GOV_STANDARD_TERMS_2_0 = "gov_standard_terms_2_0"
    PUBLIC_DATA_TERMS_1_0 = "public_data_terms_1_0"
    CC_BY_4_0 = "cc-by-4.0"
    CC_BY_NC_ND_4_0 = "cc-by-nc-nd-4.0"
    ARXIV_VARIES = "arxiv-varies"
    COPYRIGHTED_QUOTE_ONLY = "copyrighted-quote-only"
    UNCONFIRMED = "unconfirmed"


class RedistributionMode(StrEnum):
    """G2ゲートが強制する再配布ルール。"""

    FULL_ALLOWED = "full_allowed"
    SUMMARY_ONLY = "summary_only"
    QUOTE_ONLY = "quote_only"


class FetchType(StrEnum):
    RSS = "rss"
    HTML_DIFF = "html_diff"
    PDF = "pdf"


class SourceAxis(StrEnum):
    """収集ソースの3軸分類（docs/ARCHITECTURE.md 第1章）。"""

    A_POLICY_JP = "a_policy_jp"
    B_LOCAL_GOV = "b_local_gov"
    C_GLOBAL_ACADEMIC = "c_global_academic"


class SourceConfig(BaseModel):
    """`config/sources.yaml` の1エントリ。ライセンス台帳を必須フィールドとして持つ。"""

    id: str
    name: str
    axis: SourceAxis
    fetch_type: FetchType
    url: str
    license: LicenseType
    attribution_required: bool
    redistribution: RedistributionMode
    quote_max_ratio: float | None = Field(
        default=None, description="quote_only の場合のみ必須。原文に対する引用可能比率(0-1)。"
    )
    crawl_interval_seconds: int = Field(default=3600, ge=3, description="robots.txt遵守。最低3秒。")
    robots_txt_override: bool = Field(
        default=False,
        description=(
            "robots.txtがDisallowでも収集を許可する例外フラグ。"
            "サイト全体を汎用クローラー避けに設定しつつ、別途ドキュメント化されたAPI利用規約で"
            "プログラムからのアクセスを明示的に許可しているサイト（例: arXiv export API）のみに"
            "使う。override_justification必須。安易な多用禁止（CLAUDE.md第11章）。"
        ),
    )
    override_justification: str | None = Field(
        default=None, description="robots_txt_override=true の場合、根拠となる公式文書を明記"
    )
    notes: str = ""

    @model_validator(mode="after")
    def _validate_quote_ratio(self) -> SourceConfig:
        if self.redistribution == RedistributionMode.QUOTE_ONLY and self.quote_max_ratio is None:
            raise ValueError(
                f"source '{self.id}': redistribution=quote_only の場合 quote_max_ratio が必須です"
            )
        not_quote_only = self.redistribution != RedistributionMode.QUOTE_ONLY
        if not_quote_only and self.quote_max_ratio is not None:
            raise ValueError(
                f"source '{self.id}': quote_max_ratio は redistribution=quote_only の時のみ"
                " 指定できます"
            )
        if self.quote_max_ratio is not None and not (0 < self.quote_max_ratio <= 1):
            raise ValueError(
                f"source '{self.id}': quote_max_ratio は 0〜1 の範囲で指定してください"
            )
        if self.robots_txt_override and not self.override_justification:
            raise ValueError(
                f"source '{self.id}': robots_txt_override=true には"
                " override_justification が必須です"
            )
        return self


def load_sources(path: str | Path = "config/sources.yaml") -> list[SourceConfig]:
    """sources.yaml を読み込み検証済みの SourceConfig 一覧を返す。id重複は不正として弾く。"""
    raw: list[dict[str, Any]] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    sources = [SourceConfig.model_validate(entry) for entry in raw]
    ids = [s.id for s in sources]
    if len(ids) != len(set(ids)):
        duplicates = {i for i in ids if ids.count(i) > 1}
        raise ValueError(f"sources.yaml に重複した id があります: {duplicates}")
    return sources
