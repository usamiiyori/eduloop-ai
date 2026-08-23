-- EduLoop AI — Phase6 運用機能（コスト計測・キルスイッチ）
--
-- 設計方針:
--   * llm_cost_log: 生成AI呼び出し1回ごとのトークン数・推定コストを記録する。
--     make cost / make doctor および日次コスト上限判定（自動停止）に使う。
--     推定コストは常に有料プラン料金で計算する「上限見積り」であり、実際の請求額
--     （無料枠を使っている場合は0円）とは異なりうる（docs/運用マニュアル.md参照）。
--   * system_control: L1/L2/L3パイプラインの一時停止フラグ（キルスイッチ）を保持する
--     1行だけのテーブル。service_roleのみアクセス可能（オーナーの `make stop` は
--     ローカル.envのservice_roleキー経由でこのテーブルを更新する）。
--   * 変更方法: このファイルは変更しない。変更が必要な場合は 0004_*.sql 以降として追記する。

create table llm_cost_log (
    id                  uuid primary key default gen_random_uuid(),
    draft_id            uuid references drafts (id) on delete set null,
    purpose             text not null,       -- 'extraction' / 'x_thread' / 'youtube_script' / 'embedding' 等
    model               text not null,
    input_tokens        integer not null default 0 check (input_tokens >= 0),
    output_tokens       integer not null default 0 check (output_tokens >= 0),
    estimated_cost_usd  numeric(10, 6) not null default 0 check (estimated_cost_usd >= 0),
    created_at          timestamptz not null default now()
);
create index llm_cost_log_created_at_idx on llm_cost_log (created_at);

alter table llm_cost_log enable row level security;
-- anon/authenticated向けポリシーなし = service_roleのみアクセス可能。

create table system_control (
    id                  boolean primary key default true check (id),  -- 1行だけに固定するトリック
    paused              boolean not null default false,
    paused_reason       text not null default '',
    updated_at          timestamptz not null default now()
);
insert into system_control (id, paused) values (true, false);

alter table system_control enable row level security;
