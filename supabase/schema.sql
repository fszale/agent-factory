create extension if not exists pgcrypto;

create table if not exists threads (
  id uuid primary key default gen_random_uuid(),
  twin_id text not null,
  title text not null,
  status text not null default 'active',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists messages (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid not null references threads(id) on delete cascade,
  role text not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  run_id uuid null,
  created_at timestamptz not null default now()
);

create table if not exists runs (
  id uuid primary key default gen_random_uuid(),
  twin_id text not null,
  thread_id uuid null references threads(id) on delete set null,
  task_id uuid null,
  run_type text not null,
  status text not null,
  model_profile text null,
  provider text null,
  model text null,
  input_payload jsonb not null default '{}'::jsonb,
  output_payload jsonb not null default '{}'::jsonb,
  error text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists tasks (
  id uuid primary key default gen_random_uuid(),
  twin_id text not null,
  thread_id uuid null references threads(id) on delete set null,
  task_type text not null,
  status text not null,
  payload jsonb not null default '{}'::jsonb,
  result jsonb not null default '{}'::jsonb,
  run_id uuid null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists events (
  id uuid primary key default gen_random_uuid(),
  twin_id text not null,
  event_type text not null,
  source text not null,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'recorded',
  created_at timestamptz not null default now()
);

create table if not exists approvals (
  id uuid primary key default gen_random_uuid(),
  twin_id text not null,
  thread_id uuid null references threads(id) on delete set null,
  run_id uuid null,
  scope text not null,
  status text not null default 'pending',
  request_payload jsonb not null default '{}'::jsonb,
  resolution_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  resolved_at timestamptz null
);

create table if not exists corrections (
  id uuid primary key default gen_random_uuid(),
  twin_id text not null,
  thread_id uuid null references threads(id) on delete set null,
  message_id uuid null,
  scope text not null,
  instruction text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists artifact_proposals (
  id uuid primary key default gen_random_uuid(),
  twin_id text not null,
  artifact_type text not null,
  artifact_path text not null,
  proposal jsonb not null default '{}'::jsonb,
  source_correction_id uuid null references corrections(id) on delete set null,
  status text not null default 'proposed',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists api_clients (
  id uuid primary key default gen_random_uuid(),
  client_id text not null unique,
  factory_id text null,
  name text not null,
  key_prefix text not null unique,
  key_hash text not null,
  status text not null default 'active',
  allowed_twins jsonb not null default '["*"]'::jsonb,
  allowed_actions jsonb not null default '[]'::jsonb,
  rate_limit_per_minute integer not null default 60,
  metadata jsonb not null default '{}'::jsonb,
  last_used_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists admin_identities (
  user_id uuid primary key,
  email text null,
  role text not null default 'admin',
  allowed_twins jsonb not null default '["*"]'::jsonb,
  allowed_actions jsonb not null default '["*"]'::jsonb,
  status text not null default 'active',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists audit_events (
  id uuid primary key default gen_random_uuid(),
  actor_type text not null,
  actor_id text not null,
  factory_id text null,
  action text not null,
  target_type text not null,
  target_id text null,
  twin_id text null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- Phase 2: improvement-loop tables
create table if not exists traces (
  id uuid primary key default gen_random_uuid(),
  twin_id text not null,
  task_type text not null,
  action text not null,
  outcome text not null,
  signals jsonb not null default '{}'::jsonb,
  scores jsonb not null default '{}'::jsonb,
  run_id uuid null,
  thread_id uuid null references threads(id) on delete set null,
  correction_id uuid null references corrections(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists roi_snapshots (
  id uuid primary key default gen_random_uuid(),
  twin_id text not null,
  week_start date not null,
  primary_metric_value double precision null,
  baseline_value double precision null,
  improvement_vs_baseline_pct double precision null,
  weekly_roi_delta double precision null,
  usefulness_score double precision null,
  useful_completion_rate double precision null,
  curve_classification text null,
  data_quality_score double precision null,
  context_notes text null,
  created_at timestamptz not null default now()
);

create table if not exists improvement_candidates (
  id uuid primary key default gen_random_uuid(),
  twin_id text not null,
  candidate_type text not null,
  status text not null default 'proposed',
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists improvement_events (
  id uuid primary key default gen_random_uuid(),
  twin_id text not null,
  candidate_id uuid null references improvement_candidates(id) on delete set null,
  change_type text not null,
  applied_mode text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_traces_twin_id on traces(twin_id);
create index if not exists idx_roi_snapshots_twin_id on roi_snapshots(twin_id);
create index if not exists idx_improvement_candidates_twin_id on improvement_candidates(twin_id);
create index if not exists idx_improvement_events_twin_id on improvement_events(twin_id);

create index if not exists idx_threads_twin_id on threads(twin_id);
create index if not exists idx_messages_thread_id on messages(thread_id);
create index if not exists idx_runs_twin_id on runs(twin_id);
create index if not exists idx_runs_thread_id on runs(thread_id);
create index if not exists idx_tasks_twin_id on tasks(twin_id);
create index if not exists idx_events_twin_id on events(twin_id);
create index if not exists idx_approvals_twin_id on approvals(twin_id);
create index if not exists idx_corrections_twin_id on corrections(twin_id);
create index if not exists idx_artifact_proposals_twin_id on artifact_proposals(twin_id);
create index if not exists idx_api_clients_client_id on api_clients(client_id);
create index if not exists idx_admin_identities_status on admin_identities(status);
create index if not exists idx_audit_events_twin_id on audit_events(twin_id);

create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists set_threads_updated_at on threads;
create trigger set_threads_updated_at
before update on threads
for each row execute function set_updated_at();

drop trigger if exists set_runs_updated_at on runs;
create trigger set_runs_updated_at
before update on runs
for each row execute function set_updated_at();

drop trigger if exists set_tasks_updated_at on tasks;
create trigger set_tasks_updated_at
before update on tasks
for each row execute function set_updated_at();

drop trigger if exists set_approvals_updated_at on approvals;
create trigger set_approvals_updated_at
before update on approvals
for each row execute function set_updated_at();

drop trigger if exists set_artifact_proposals_updated_at on artifact_proposals;
create trigger set_artifact_proposals_updated_at
before update on artifact_proposals
for each row execute function set_updated_at();

drop trigger if exists set_api_clients_updated_at on api_clients;
create trigger set_api_clients_updated_at
before update on api_clients
for each row execute function set_updated_at();

drop trigger if exists set_admin_identities_updated_at on admin_identities;
create trigger set_admin_identities_updated_at
before update on admin_identities
for each row execute function set_updated_at();
