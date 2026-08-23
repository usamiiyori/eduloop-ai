-- EduLoop AI — L2承認機能（Phase 5）
--
-- 設計方針:
--   * Web承認画面はSupabase Auth(authenticated)で直接Supabaseに接続する
--     （docs/ARCHITECTURE.md 2.4節・9章）。teacher_profiles等の将来の教員コミュニティ
--     機能とは異なり、承認操作(status変更)はオーナー等ごく少数の「reviewers」にのみ許可する。
--   * status変更は生テーブルへのUPDATEを許可せず、SECURITY DEFINER関数経由に限定する。
--     理由: RLSのUPDATEポリシーだけではscore等の他カラムの改変や不正な状態遷移
--     (例: published直行)を防げないため。関数側で遷移ルールを固定し、audit_logへの
--     記録も同一トランザクションで必ず行う。
--   * 変更方法: このファイルは変更しない。変更が必要な場合は 0003_*.sql 以降として追記する。

-- ─────────────────────────────────────────────────────────────
-- reviewers（承認権限を持つユーザー）
-- ─────────────────────────────────────────────────────────────

create table reviewers (
    id                  uuid primary key references auth.users (id) on delete cascade,
    email               text not null,
    created_at          timestamptz not null default now()
);

alter table reviewers enable row level security;
-- 本人が自分の行だけ確認できる（画面側で「レビュー権限あり」判定に使う）。
create policy reviewers_select_own on reviewers
    for select
    to authenticated
    using (auth.uid() = id);

create or replace function is_reviewer()
returns boolean
language sql
security definer
set search_path = public
stable
as $$
    select exists (select 1 from reviewers where id = auth.uid());
$$;

-- ─────────────────────────────────────────────────────────────
-- reviewers向け SELECT ポリシー（未公開ステータスも閲覧可能にする）
-- ─────────────────────────────────────────────────────────────

create policy drafts_select_reviewer on drafts
    for select
    to authenticated
    using (is_reviewer());

create policy web_articles_select_reviewer on web_articles
    for select
    to authenticated
    using (is_reviewer());

create policy x_thread_posts_select_reviewer on x_thread_posts
    for select
    to authenticated
    using (is_reviewer());

create policy youtube_scripts_select_reviewer on youtube_scripts
    for select
    to authenticated
    using (is_reviewer());

create policy citations_select_reviewer on citations
    for select
    to authenticated
    using (is_reviewer());

create policy harness_runs_select_reviewer on harness_runs
    for select
    to authenticated
    using (is_reviewer());

create policy harness_gate_results_select_reviewer on harness_gate_results
    for select
    to authenticated
    using (is_reviewer());

create policy audit_log_select_reviewer on audit_log
    for select
    to authenticated
    using (is_reviewer());

-- ─────────────────────────────────────────────────────────────
-- 承認/却下/修正指示（状態遷移を固定した関数経由のみ許可）
-- ─────────────────────────────────────────────────────────────

create or replace function l2_approve_draft(p_draft_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    if not is_reviewer() then
        raise exception 'reviewer権限がありません';
    end if;

    update drafts
       set status = 'approved', updated_at = now()
     where id = p_draft_id
       and status in ('draft', 'needs_human');

    if not found then
        raise exception 'draft % は承認待ち状態ではありません', p_draft_id;
    end if;

    insert into audit_log (actor, action, draft_id, detail)
    values (coalesce(auth.jwt() ->> 'email', auth.uid()::text), 'l2_approved', p_draft_id, '{}'::jsonb);
end;
$$;

create or replace function l2_reject_draft(p_draft_id uuid, p_reason text)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    if not is_reviewer() then
        raise exception 'reviewer権限がありません';
    end if;

    update drafts
       set status = 'rejected', updated_at = now()
     where id = p_draft_id
       and status in ('draft', 'needs_human');

    if not found then
        raise exception 'draft % は承認待ち状態ではありません', p_draft_id;
    end if;

    insert into audit_log (actor, action, draft_id, detail)
    values (
        coalesce(auth.jwt() ->> 'email', auth.uid()::text),
        'l2_rejected',
        p_draft_id,
        jsonb_build_object('reason', p_reason)
    );
end;
$$;

create or replace function l2_request_revision(p_draft_id uuid, p_instruction text)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    if not is_reviewer() then
        raise exception 'reviewer権限がありません';
    end if;

    update drafts
       set status = 'draft', retry_count = 0, updated_at = now()
     where id = p_draft_id
       and status in ('draft', 'needs_human');

    if not found then
        raise exception 'draft % は承認待ち状態ではありません', p_draft_id;
    end if;

    insert into audit_log (actor, action, draft_id, detail)
    values (
        coalesce(auth.jwt() ->> 'email', auth.uid()::text),
        'l2_revision_requested',
        p_draft_id,
        jsonb_build_object('instruction', p_instruction)
    );
end;
$$;

revoke execute on function l2_approve_draft(uuid) from public;
revoke execute on function l2_reject_draft(uuid, text) from public;
revoke execute on function l2_request_revision(uuid, text) from public;
grant execute on function l2_approve_draft(uuid) to authenticated;
grant execute on function l2_reject_draft(uuid, text) to authenticated;
grant execute on function l2_request_revision(uuid, text) to authenticated;
