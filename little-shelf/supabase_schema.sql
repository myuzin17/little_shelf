-- Supabase 대시보드 > SQL Editor 에 통째로 붙여넣고 Run 하세요.

create table if not exists public.shelves (
  id          text primary key check (id ~ '^[A-Za-z0-9_-]{6,32}$'),
  owner_name  text not null check (char_length(owner_name) between 1 and 15),
  created_at  timestamptz not null default now()
);

create table if not exists public.gifts (
  id              uuid primary key default gen_random_uuid(),
  shelf_id        text not null references public.shelves(id) on delete cascade,
  slot_number     smallint not null check (slot_number between 1 and 20),
  sender_name     text not null check (char_length(sender_name) between 1 and 15),
  container_type  text not null,
  container_color text not null,
  flowers         jsonb not null
                  check (jsonb_typeof(flowers) = 'array' and jsonb_array_length(flowers) between 1 and 3),
  message         text not null default '' check (char_length(message) <= 100),
  created_at      timestamptz not null default now(),
  -- 같은 선반의 같은 칸에는 선물이 하나만. 동시에 저장해도 DB가 한 건만 통과시킵니다.
  constraint gifts_shelf_slot_unique unique (shelf_id, slot_number)
);

create index if not exists gifts_shelf_id_idx on public.gifts (shelf_id);

-- 접근 제어: RLS를 켜고 정책을 만들지 않으면 anon/authenticated 키로는 아무것도 읽고 쓸 수 없습니다.
-- 앱(서버)은 service_role 키로만 접근하며, 코드에는 조회(select)와 등록(insert)만 있습니다.
alter table public.shelves enable row level security;
alter table public.gifts   enable row level security;
revoke all on public.shelves from anon, authenticated;
revoke all on public.gifts   from anon, authenticated;
