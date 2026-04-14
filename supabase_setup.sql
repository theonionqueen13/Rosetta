-- supabase_setup.sql
-- Run this in your Supabase project: Dashboard → SQL Editor → New Query
-- -----------------------------------------------------------------------

-- 1. Create the user_profiles table
--    Each row stores one named chart profile belonging to one user.
-- -----------------------------------------------------------------------
create table if not exists public.user_profiles (
    id            uuid        primary key default gen_random_uuid(),
    user_id       uuid        not null references auth.users(id) on delete cascade,
    profile_name  text        not null,
    payload       jsonb       not null default '{}',
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now(),

    -- A user cannot have two profiles with the same name.
    unique (user_id, profile_name)
);

-- 2. Auto-update the updated_at timestamp on every write
-- -----------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger trg_user_profiles_updated_at
    before update on public.user_profiles
    for each row execute procedure public.set_updated_at();

-- 3. Enable Row-Level Security
--    Without this, any authenticated user could read ALL profiles.
-- -----------------------------------------------------------------------
alter table public.user_profiles enable row level security;

-- 4. RLS policy: each user can only see and modify their own rows
-- -----------------------------------------------------------------------
create policy "users_own_profiles"
    on public.user_profiles
    for all
    using  (auth.uid() = user_id)         -- read filter
    with check (auth.uid() = user_id);    -- write filter

-- -----------------------------------------------------------------------
-- Optional: index for fast lookups by user_id
-- -----------------------------------------------------------------------
create index if not exists idx_user_profiles_user_id
    on public.user_profiles (user_id);

-- -----------------------------------------------------------------------
-- User Profile Groups table
--    Allows users to organize profiles into named groups (folders).
-- -----------------------------------------------------------------------
create table if not exists public.user_profile_groups (
    id       uuid        primary key default gen_random_uuid(),
    user_id  uuid        not null references auth.users(id) on delete cascade,
    group_name text      not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    -- A user cannot have two groups with the same name.
    unique (user_id, group_name)
);

-- Enable RLS on user_profile_groups.
alter table public.user_profile_groups enable row level security;

-- RLS policy: each user can only see and modify their own groups.
create policy "users_own_profile_groups"
    on public.user_profile_groups
    for all
    using  (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- Index for fast lookups by user_id.
create index if not exists idx_user_profile_groups_user_id
    on public.user_profile_groups (user_id);

-- Optional: add group_id column to user_profiles (nullable, for organizing profiles into groups).
-- This allows "ungrouped" profiles (group_id = NULL) alongside grouped ones.
-- Uncomment if you want this feature:
-- alter table public.user_profiles add column if not exists group_id uuid references public.user_profile_groups(id) on delete set null;

-- -----------------------------------------------------------------------
-- Admin user table (for application-level admin checks)
-- -----------------------------------------------------------------------
-- -----------------------------------------------------------------------
create table if not exists public.user_admins (
    user_id   uuid primary key references auth.users(id) on delete cascade,
    created_at timestamptz not null default now()
);

alter table public.user_admins enable row level security;

create policy "users_see_their_admin_status"
    on public.user_admins
    for select
    using (auth.uid() = user_id);

-- -----------------------------------------------------------------------
-- Beta Feedback / Bug Reports table
-- -----------------------------------------------------------------------
create table if not exists public.user_feedback (
    id              uuid        primary key default gen_random_uuid(),
    user_id         uuid        references auth.users(id) on delete set null,  -- nullable for non-logged-in users
    user_email      text        not null,
    problem_types   jsonb       not null default '[]',
    description     text        not null,
    affected_features jsonb     not null default '[]',
    attachments     jsonb       not null default '{}',  -- chat_history, chart_image, screenshot, etc.
    still_having_problem text,
    blocking_issue  text,
    suggestions     text,
    love_feedback   text,
    other_feedback  text,
    app_state_snapshot jsonb    default '{}',
    admin_viewed    boolean     not null default false,
    created_at      timestamptz not null default now()
);

-- Enable RLS on user_feedback
alter table public.user_feedback enable row level security;

-- Anyone can INSERT feedback (even unauthenticated, for login issues)
create policy "anyone_can_submit_feedback"
    on public.user_feedback
    for insert
    with check (true);

-- Only admins can SELECT feedback
create policy "admins_can_read_feedback"
    on public.user_feedback
    for select
    using (
        exists (
            select 1 from public.user_admins
            where user_admins.user_id = auth.uid()
        )
    );

-- Only admins can UPDATE feedback (e.g., mark as viewed)
create policy "admins_can_update_feedback"
    on public.user_feedback
    for update
    using (
        exists (
            select 1 from public.user_admins
            where user_admins.user_id = auth.uid()
        )
    );

-- Index for faster queries
create index if not exists idx_user_feedback_created_at
    on public.user_feedback (created_at desc);

create index if not exists idx_user_feedback_admin_viewed
    on public.user_feedback (admin_viewed) where admin_viewed = false;

-- -----------------------------------------------------------------------
-- Admin Notifications queue (optional, for email delivery)
-- -----------------------------------------------------------------------
create table if not exists public.admin_notifications (
    id           uuid        primary key default gen_random_uuid(),
    admin_email  text        not null,
    feedback_id  uuid        references public.user_feedback(id) on delete cascade,
    user_email   text,
    problem_types jsonb,
    description_preview text,
    sent         boolean     not null default false,
    created_at   timestamptz not null default now()
);

alter table public.admin_notifications enable row level security;

-- Only admins can view notifications
create policy "admins_can_read_notifications"
    on public.admin_notifications
    for all
    using (
        exists (
            select 1 from public.user_admins
            where user_admins.user_id = auth.uid()
        )
    );
