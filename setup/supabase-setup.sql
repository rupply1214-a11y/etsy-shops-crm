-- Etsy Shops CRM: database setup
-- Run this once in Supabase: SQL Editor > New query > paste everything > Run.
-- Safe to run again: it only creates what is missing and resets the access rules.
-- Every row belongs to the signed-in account (owner). Nobody else can read or change it.

create extension if not exists pgcrypto;

create table if not exists public.shops (
  owner uuid not null default auth.uid() references auth.users(id) on delete cascade,
  id text not null,
  name text not null,
  url text default '',
  last_csv date,
  csv_every_days int default 14,
  schedules jsonb not null default '[]'::jsonb,
  sort int default 0,
  updated_at timestamptz default now(),
  primary key (owner, id)
);

create table if not exists public.tasks (
  owner uuid not null default auth.uid() references auth.users(id) on delete cascade,
  id text not null,
  shop text default '',
  title text not null,
  area text default 'other',
  sku text default '',
  due date,
  priority int default 2,
  status text not null default 'todo' check (status in ('todo','doing','done','skipped')),
  steps text default '',
  copy jsonb not null default '[]'::jsonb,
  follow_up_days int,
  notes text default '',
  plan text default '',
  source text default '',
  parent text,
  started_at timestamptz,
  done_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  primary key (owner, id)
);
create index if not exists tasks_due_idx on public.tasks (owner, due);

create table if not exists public.listings (
  owner uuid not null default auth.uid() references auth.users(id) on delete cascade,
  shop text not null,
  key text not null,
  title text,
  sku text default '',
  price numeric,
  currency text,
  quantity int,
  tags text default '',
  image_count int,
  description text default '',
  notes text default '',
  active boolean default true,
  imported_at timestamptz default now(),
  primary key (owner, shop, key)
);

create table if not exists public.orders (
  owner uuid not null default auth.uid() references auth.users(id) on delete cascade,
  shop text not null,
  transaction_id text not null,
  order_id text,
  sale_date date,
  item_name text,
  listing_id text,
  sku text default '',
  quantity int default 1,
  price numeric,
  discount numeric,
  item_total numeric,
  currency text,
  coupon text default '',
  buyer text default '',
  country text default '',
  primary key (owner, shop, transaction_id)
);
create index if not exists orders_date_idx on public.orders (owner, shop, sale_date);

create table if not exists public.customer_notes (
  owner uuid not null default auth.uid() references auth.users(id) on delete cascade,
  shop text not null,
  buyer text not null,
  notes text default '',
  tags text default '',
  updated_at timestamptz default now(),
  primary key (owner, shop, buyer)
);

create table if not exists public.datasets (
  owner uuid not null default auth.uid() references auth.users(id) on delete cascade,
  id uuid not null default gen_random_uuid(),
  name text not null,
  shop text default '',
  source_file text default '',
  columns jsonb not null default '[]'::jsonb,
  row_count int default 0,
  created_at timestamptz default now(),
  primary key (owner, id)
);

create table if not exists public.dataset_rows (
  owner uuid not null default auth.uid() references auth.users(id) on delete cascade,
  dataset_id uuid not null,
  row_no int not null,
  data jsonb not null,
  primary key (owner, dataset_id, row_no),
  foreign key (owner, dataset_id) references public.datasets (owner, id) on delete cascade
);

create table if not exists public.app_code (
  owner uuid not null default auth.uid() references auth.users(id) on delete cascade,
  name text not null,
  version text default '',
  content text not null,
  updated_at timestamptz default now(),
  primary key (owner, name)
);

-- Access rules: each signed-in account sees and edits only its own rows.
do $$
declare t text;
begin
  foreach t in array array['shops','tasks','listings','orders','customer_notes','datasets','dataset_rows','app_code'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists own_rows on public.%I', t);
    execute format('create policy own_rows on public.%I for all to authenticated using (owner = auth.uid()) with check (owner = auth.uid())', t);
    execute format('revoke all on public.%I from anon', t);
    execute format('grant select, insert, update, delete on public.%I to authenticated', t);
  end loop;
end $$;

-- Added in version 2: listing photo links (for thumbnails in Listings).
alter table public.listings add column if not exists images jsonb not null default '[]'::jsonb;
