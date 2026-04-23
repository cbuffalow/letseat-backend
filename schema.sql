-- ============================================================
-- ForkIt Database Schema
-- Run this in your Supabase SQL editor (Dashboard > SQL Editor)
-- ============================================================

-- Enable UUID generation
create extension if not exists "pgcrypto";


-- ── Users ────────────────────────────────────────────────────
create table if not exists users (
  id              uuid primary key default gen_random_uuid(),
  email           text unique not null,
  password_hash   text not null,
  display_name    text not null,
  preferences     jsonb not null default '{
    "restrictions": [],
    "cuisines_liked": [],
    "cuisines_disliked": [],
    "price_range": [1, 2, 3, 4]
  }'::jsonb,
  created_at      timestamptz default now()
);


-- ── Sessions ─────────────────────────────────────────────────
create table if not exists sessions (
  id              uuid primary key default gen_random_uuid(),
  host_id         uuid not null references users(id) on delete cascade,
  name            text not null,
  code            text not null,           -- 6-char join code
  latitude        float not null,
  longitude       float not null,
  radius_meters   int not null default 2000,
  status          text not null default 'waiting',  -- waiting | swiping | results
  created_at      timestamptz default now(),

  constraint status_values check (status in ('waiting', 'swiping', 'results'))
);

create index if not exists idx_sessions_code on sessions(code);


-- ── Session Members ──────────────────────────────────────────
create table if not exists session_members (
  id              uuid primary key default gen_random_uuid(),
  session_id      uuid not null references sessions(id) on delete cascade,
  user_id         uuid not null references users(id) on delete cascade,
  done_swiping    boolean not null default false,
  joined_at       timestamptz default now(),

  unique (session_id, user_id)
);


-- ── Session Restaurants (cached Yelp results) ────────────────
create table if not exists session_restaurants (
  id              uuid primary key default gen_random_uuid(),
  session_id      uuid not null references sessions(id) on delete cascade,
  restaurant_id   text not null,           -- Yelp business ID
  restaurant_data jsonb not null,          -- Full restaurant object

  unique (session_id, restaurant_id)
);


-- ── Votes ────────────────────────────────────────────────────
create table if not exists votes (
  id              uuid primary key default gen_random_uuid(),
  session_id      uuid not null references sessions(id) on delete cascade,
  user_id         uuid not null references users(id) on delete cascade,
  restaurant_id   text not null,
  direction       text not null,           -- 'right' (like) or 'left' (pass)
  voted_at        timestamptz default now(),

  unique (session_id, user_id, restaurant_id),
  constraint direction_values check (direction in ('left', 'right'))
);

create index if not exists idx_votes_session on votes(session_id);
