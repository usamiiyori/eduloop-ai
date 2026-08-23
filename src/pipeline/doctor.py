"""`make doctor`: APIキー・DB接続・各ソース疎通・直近実行結果を日本語で診断する。
CLAUDE.md第0章ルール2「オーナーにトレースバックを読ませない」に従い、例外は必ず日本語の
「何が起きたか/なぜか/取るべき操作」に変換してから表示する。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from pydantic import BaseModel

from src.config import get_settings
from src.processors.llm_client import generate_structured
from src.store import cost_log, source_health_store, supabase_client, system_control


@dataclass
class CheckResult:
    label: str
    ok: bool
    detail: str


class _PingResponse(BaseModel):
    ok: bool


async def _check_env_keys() -> CheckResult:
    settings = get_settings()
    missing = []
    if not settings.supabase_url:
        missing.append("SUPABASE_URL")
    if not settings.supabase_service_role_key:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if not settings.google_genai_api_key:
        missing.append("GOOGLE_GENAI_API_KEY")
    if not settings.slack_webhook_url:
        missing.append("SLACK_WEBHOOK_URL")
    if not settings.scraper_contact_url:
        missing.append("SCRAPER_CONTACT_URL")

    if not missing:
        return CheckResult("必須の環境変数(.env)", True, "すべて設定されています")
    return CheckResult(
        "必須の環境変数(.env)",
        False,
        f"未設定: {', '.join(missing)}。docs/運用マニュアル.md を参照して.envに設定してください",
    )


async def _check_supabase() -> CheckResult:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        detail = "SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY未設定のため確認できません"
        return CheckResult("Supabase接続", False, detail)
    try:
        await supabase_client.select("system_control", params={"select": "paused"})
    except Exception as exc:  # noqa: BLE001 — オーナー向けに日本語へ変換して表示する
        return CheckResult("Supabase接続", False, f"接続に失敗しました: {exc}")
    return CheckResult("Supabase接続", True, "接続できています")


async def _check_gemini() -> CheckResult:
    settings = get_settings()
    if not settings.google_genai_api_key:
        return CheckResult(
            "Gemini API接続", False, "GOOGLE_GENAI_API_KEY未設定のため確認できません"
        )
    try:
        prompt = '次のJSONだけを返してください: {"ok": true}'
        await generate_structured(prompt, _PingResponse)
    except Exception as exc:  # noqa: BLE001
        return CheckResult("Gemini API接続", False, f"呼び出しに失敗しました: {exc}")
    return CheckResult(
        "Gemini API接続", True, "接続できています(この確認で少額のAPI利用が発生します)"
    )


async def _check_kill_switch() -> CheckResult:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return CheckResult("キルスイッチ状態", False, "Supabase未接続のため確認できません")
    try:
        paused, reason = await system_control.is_paused()
    except Exception as exc:  # noqa: BLE001
        return CheckResult("キルスイッチ状態", False, f"確認に失敗しました: {exc}")
    if paused:
        detail = (
            f"停止中です(理由: {reason or '未記入'})。再開するにはSQL Editorで"
            " `update system_control set paused = false;` を実行してください"
        )
        return CheckResult("キルスイッチ状態", False, detail)
    return CheckResult("キルスイッチ状態", True, "稼働中です")


async def _check_cost() -> CheckResult:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return CheckResult("本日のコスト", False, "Supabase未接続のため確認できません")
    try:
        spent = await cost_log.today_total_usd()
    except Exception as exc:  # noqa: BLE001
        return CheckResult("本日のコスト", False, f"確認に失敗しました: {exc}")
    limit = settings.llm_daily_cost_limit_usd
    ok = spent < limit
    suffix = "" if ok else "（上限に到達しています）"
    return CheckResult("本日のコスト", ok, f"推定${spent:.4f} / 上限${limit:.2f}{suffix}")


async def _check_source_health() -> list[CheckResult]:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return [CheckResult("収集ソースの疎通状況", False, "Supabase未接続のため確認できません")]
    try:
        healths = await source_health_store.all_health()
    except Exception as exc:  # noqa: BLE001
        return [CheckResult("収集ソースの疎通状況", False, f"確認に失敗しました: {exc}")]
    if not healths:
        return [
            CheckResult("収集ソースの疎通状況", True, "実行履歴がまだありません(初回のL1実行前)")
        ]

    results = []
    for h in sorted(healths, key=lambda x: x.source_id):
        if h.consecutive_failures >= source_health_store.NOTIFY_THRESHOLD:
            results.append(
                CheckResult(
                    f"ソース: {h.source_id}",
                    False,
                    f"{h.consecutive_failures}回連続失敗。直近のエラー: {h.last_error}",
                )
            )
        else:
            results.append(
                CheckResult(f"ソース: {h.source_id}", True, f"正常(直近成功: {h.last_success_at})")
            )
    return results


async def run() -> None:
    print("=== EduLoop AI 診断結果 ===\n")

    checks = [
        await _check_env_keys(),
        await _check_supabase(),
        await _check_gemini(),
        await _check_kill_switch(),
        await _check_cost(),
    ]
    checks.extend(await _check_source_health())

    for c in checks:
        mark = "OK" if c.ok else "NG"
        print(f"[{mark}] {c.label}: {c.detail}")

    ng_count = sum(1 for c in checks if not c.ok)
    print()
    if ng_count == 0:
        print("すべて正常です。")
    else:
        print(f"{ng_count}件の異常があります。上記の対処法に従って修正してください。")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
