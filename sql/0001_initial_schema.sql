-- EduLoop AI — 初期スキーマ（Phase 1）
--
-- 設計方針:
--   * サービス層（scrapers/processors/harness/publishers）はすべて service_role キーで接続する。
--     service_role は Supabase の仕様上 RLS を常にバイパスするため、以下の RLS ポリシーは
--     「万一 anon/authenticated キーが漏洩・誤用された場合の防御」として機能する。
--   * 内部処理専用テーブル（raw_documents, drafts, harness_runs, audit_log, source_health等）は
--     RLSを有効化した上でanon/authenticatedへのポリシーを一切与えない＝完全非公開とする。
--   * 公開対象は「承認済み(published)の記事」のみ。drafts.status='published' を経由するテーブルにのみ
--     anon向けSELECTポリシーを与える（L2ゲートを経ないコンテンツは公開しない、CLAUDE.md第2章）。
--   * 教員コミュニティ機能（teacher_profiles / teacher_comments）はPhase1時点では未使用だが、
--     後付け拡張を避けるため初期スキーマから設計する（CLAUDE.md第8章）。
--
-- 変更方法: このファイルは変更しない。変更が必要な場合は 0002_*.sql 以降として追記する。

create extension if not exists pgcrypto;
-- 埋め込み類似度（G1事実整合性のハイブリッド照合 / G5重複判定）に使用。
-- vector(768) は暫定値。Phase 3/4で実際に採用する埋め込みモデルの次元数に合わせて要修正（未確認事項）。
create extension if not exists vector;

-- ─────────────────────────────────────────────────────────────
-- 一次情報・書誌
-- ─────────────────────────────────────────────────────────────

create table raw_documents (
    id                  uuid primary key default gen_random_uuid(),
    source_id           text not null,                   -- config/sources.yaml の SourceConfig.id
    fetch_type          text not null check (fetch_type in ('rss', 'html_diff', 'pdf')),
    url                 text not null,
    title               text not null,
    published_at        timestamptz,
    fetched_at          timestamptz not null default now(),
    content_hash        text not null,                    -- HTML差分検知用
    raw_text            text not null,
    page_offsets        jsonb not null default '[]',       -- PDF用ページ境界（PageOffsetのリスト）
    license_snapshot    jsonb not null,                    -- 取得時点のライセンス条件スナップショット
    embedding           vector(768),                       -- 未確認: 次元数はPhase3/4で確定
    created_at          timestamptz not null default now()
);
create index raw_documents_source_id_idx on raw_documents (source_id);
create index raw_documents_content_hash_idx on raw_documents (source_id, content_hash);

alter table raw_documents enable row level security;
-- anon/authenticated 向けポリシーなし = 完全非公開。service_role のみアクセス可。

create table citations (
    id                  uuid primary key default gen_random_uuid(),
    raw_document_id     uuid not null references raw_documents (id) on delete cascade,
    author_or_organization text not null,
    title               text not null,
    container_title     text,
    publisher           text,
    published_date      date,
    url                 text not null,
    accessed_date       date not null default current_date,
    page                text,
    created_at          timestamptz not null default now()
);
create index citations_raw_document_id_idx on citations (raw_document_id);

alter table citations enable row level security;

create table source_health (
    source_id           text primary key,
    last_success_at     timestamptz,
    last_failure_at     timestamptz,
    consecutive_failures integer not null default 0,
    last_error          text not null default '',
    updated_at          timestamptz not null default now()
);

alter table source_health enable row level security;

-- ─────────────────────────────────────────────────────────────
-- 生成物（drafts）と3配信形式
-- ─────────────────────────────────────────────────────────────

create table drafts (
    id                  uuid primary key default gen_random_uuid(),
    raw_document_ids    uuid[] not null,
    format              text not null check (format in ('web_article', 'x_thread', 'youtube_script')),
    status              text not null default 'draft'
                            check (status in ('draft', 'needs_human', 'approved', 'rejected', 'published')),
    fact                text not null,
    implication         text not null,
    discussion          text not null,
    citation_ids        uuid[] not null default '{}',
    score_impact        integer not null check (score_impact between 1 and 5),
    score_timeliness    integer not null check (score_timeliness between 1 and 5),
    score_controversy   integer not null check (score_controversy between 1 and 5),
    score_total         integer generated always as (score_impact * score_timeliness * score_controversy) stored,
    retry_count         integer not null default 0 check (retry_count between 0 and 3),
    embedding           vector(768), -- G5重複判定用。未確認: 次元数はPhase3/4で確定
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);
create index drafts_status_idx on drafts (status);
create index drafts_score_total_idx on drafts (score_total);

alter table drafts enable row level security;
-- 公開ポリシー: status='published' の記事のみ anon が参照可能（web_articles経由での結合参照を想定）。
create policy drafts_select_published on drafts
    for select
    to anon, authenticated
    using (status = 'published');

create table web_articles (
    draft_id            uuid primary key references drafts (id) on delete cascade,
    title               text not null,
    slug                text not null unique,
    body_markdown       text not null,
    utm_campaign        text not null,
    created_at          timestamptz not null default now()
);

alter table web_articles enable row level security;
create policy web_articles_select_published on web_articles
    for select
    to anon, authenticated
    using (exists (
        select 1 from drafts d where d.id = web_articles.draft_id and d.status = 'published'
    ));

create table x_thread_posts (
    id                  uuid primary key default gen_random_uuid(),
    draft_id            uuid not null references drafts (id) on delete cascade,
    order_index         integer not null check (order_index >= 0),
    text                text not null check (char_length(text) <= 140),
    unique (draft_id, order_index)
);

alter table x_thread_posts enable row level security;
create policy x_thread_posts_select_published on x_thread_posts
    for select
    to anon, authenticated
    using (exists (
        select 1 from drafts d where d.id = x_thread_posts.draft_id and d.status = 'published'
    ));

create table youtube_scripts (
    draft_id            uuid primary key references drafts (id) on delete cascade,
    script_text         text not null,
    description_text    text not null,
    created_at          timestamptz not null default now()
);

alter table youtube_scripts enable row level security;
create policy youtube_scripts_select_published on youtube_scripts
    for select
    to anon, authenticated
    using (exists (
        select 1 from drafts d where d.id = youtube_scripts.draft_id and d.status = 'published'
    ));

-- ─────────────────────────────────────────────────────────────
-- ハーネス（G1〜G6）検証結果
-- ─────────────────────────────────────────────────────────────

create table harness_runs (
    id                  uuid primary key default gen_random_uuid(),
    draft_id            uuid not null references drafts (id) on delete cascade,
    attempt             integer not null check (attempt between 1 and 3),
    created_at          timestamptz not null default now()
);
create index harness_runs_draft_id_idx on harness_runs (draft_id);

alter table harness_runs enable row level security;

create table harness_gate_results (
    id                  uuid primary key default gen_random_uuid(),
    harness_run_id      uuid not null references harness_runs (id) on delete cascade,
    gate                text not null check (gate in ('G1', 'G2', 'G3', 'G4', 'G5', 'G6')),
    passed              boolean not null,
    reason              text not null default ''
);
create index harness_gate_results_run_id_idx on harness_gate_results (harness_run_id);

alter table harness_gate_results enable row level security;

-- ─────────────────────────────────────────────────────────────
-- 監査ログ
-- ─────────────────────────────────────────────────────────────

create table audit_log (
    id                  uuid primary key default gen_random_uuid(),
    actor               text not null,   -- 'system' または承認者の識別子
    action              text not null check (action in (
                            'l1_generated', 'harness_blocked', 'l2_approved', 'l2_rejected',
                            'l2_revision_requested', 'published', 'cost_limit_exceeded'
                        )),
    draft_id            uuid references drafts (id) on delete set null,
    detail              jsonb not null default '{}',
    created_at          timestamptz not null default now()
);
create index audit_log_draft_id_idx on audit_log (draft_id);

alter table audit_log enable row level security;

-- ─────────────────────────────────────────────────────────────
-- 収益KPI計測（docs/ARCHITECTURE.md 第4章）
-- ─────────────────────────────────────────────────────────────

create table post_metrics (
    id                  uuid primary key default gen_random_uuid(),
    draft_id            uuid not null references drafts (id) on delete cascade,
    channel             text not null,       -- 'x' / 'youtube' 等
    impressions         integer not null default 0 check (impressions >= 0),
    profile_clicks      integer not null default 0 check (profile_clicks >= 0),
    data_source         text not null check (data_source in ('manual', 'api')),
    recorded_at         timestamptz not null default now()
);
create index post_metrics_draft_id_idx on post_metrics (draft_id);

alter table post_metrics enable row level security;

create table link_clicks (
    id                  uuid primary key default gen_random_uuid(),
    draft_id            uuid not null references drafts (id) on delete cascade,
    utm_campaign        text not null,
    url                 text not null,
    referrer            text,
    clicked_at          timestamptz not null default now()
);
create index link_clicks_draft_id_idx on link_clicks (draft_id);

alter table link_clicks enable row level security;
-- 計測エンドポイントから anon で直接INSERTできるようにする（Web記事のクリック計測用）。
create policy link_clicks_insert_anon on link_clicks
    for insert
    to anon
    with check (true);

create table conversions (
    id                  uuid primary key default gen_random_uuid(),
    draft_id            uuid not null references drafts (id) on delete cascade,
    channel             text not null,       -- 'note' 等
    amount_jpy          integer not null check (amount_jpy >= 0),
    data_source         text not null check (data_source in ('manual', 'api')),
    recorded_at         timestamptz not null default now()
);
create index conversions_draft_id_idx on conversions (draft_id);

alter table conversions enable row level security;

create table inbound_leads (
    id                  uuid primary key default gen_random_uuid(),
    name                text not null,
    contact             text not null,
    message             text not null,
    source_channel      text not null,
    created_at          timestamptz not null default now()
);

alter table inbound_leads enable row level security;
-- 問い合わせフォームから anon で直接INSERTできるようにする（読み取りは service_role のみ）。
create policy inbound_leads_insert_anon on inbound_leads
    for insert
    to anon
    with check (true);

-- ─────────────────────────────────────────────────────────────
-- 教員コミュニティ（将来拡張。Phase1時点では未使用だが初期スキーマに含める）
-- ─────────────────────────────────────────────────────────────

create table teacher_profiles (
    id                  uuid primary key references auth.users (id) on delete cascade,
    display_name        text not null,
    region              text,             -- 例:「愛知県」。市区町村・学校名までは保持しない（PII配慮）
    created_at          timestamptz not null default now()
);

alter table teacher_profiles enable row level security;
create policy teacher_profiles_select_all on teacher_profiles
    for select
    to authenticated
    using (true);
create policy teacher_profiles_insert_own on teacher_profiles
    for insert
    to authenticated
    with check (auth.uid() = id);
create policy teacher_profiles_update_own on teacher_profiles
    for update
    to authenticated
    using (auth.uid() = id)
    with check (auth.uid() = id);

create table teacher_comments (
    id                  uuid primary key default gen_random_uuid(),
    teacher_id          uuid not null references teacher_profiles (id) on delete cascade,
    draft_id            uuid not null references drafts (id) on delete cascade,
    comment             text not null,
    created_at          timestamptz not null default now()
);
create index teacher_comments_draft_id_idx on teacher_comments (draft_id);

alter table teacher_comments enable row level security;
create policy teacher_comments_select_on_published on teacher_comments
    for select
    to authenticated
    using (exists (
        select 1 from drafts d where d.id = teacher_comments.draft_id and d.status = 'published'
    ));
create policy teacher_comments_insert_own on teacher_comments
    for insert
    to authenticated
    with check (auth.uid() = teacher_id);
