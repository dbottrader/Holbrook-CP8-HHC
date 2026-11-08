-- Model pin and the run record for a mesh job.
-- A missing digest stays ineligible for deterministic verification.
-- Apply this before deploying the gpu-mesh function that writes the columns.
-- New columns are nullable or constant-default, so existing rows stay valid.

alter table public.gpumesh_nodes
  add column if not exists agent_commit text not null default '',
  add column if not exists runtime_name text not null default '',
  add column if not exists runtime_version text not null default '';

alter table public.gpumesh_jobs
  add column if not exists agent_commit text not null default '',
  add column if not exists runtime_name text not null default '',
  add column if not exists runtime_version text not null default '',
  add column if not exists top_k integer,
  add column if not exists top_p double precision,
  add column if not exists repeat_penalty double precision,
  add column if not exists num_ctx integer;

comment on column public.gpumesh_nodes.agent_commit is
  'Git commit of the node agent, or its version string when git is absent.';
comment on column public.gpumesh_nodes.runtime_name is
  'Inference runtime that advertised the models: ollama, vllm, or llamacpp.';
comment on column public.gpumesh_nodes.runtime_version is
  'Runtime version. For Ollama this is the version field from /api/version.';

comment on column public.gpumesh_jobs.agent_commit is
  'Git commit or version string of the agent that ran this job.';
comment on column public.gpumesh_jobs.runtime_name is
  'Runtime that ran this job.';
comment on column public.gpumesh_jobs.runtime_version is
  'Version of the runtime that ran this job.';
comment on column public.gpumesh_jobs.top_k is
  'Pinned sampling top_k. Deterministic jobs use 1.';
comment on column public.gpumesh_jobs.top_p is
  'Pinned sampling top_p. Deterministic jobs use 1 so Ollama does not apply 0.9.';
comment on column public.gpumesh_jobs.repeat_penalty is
  'Pinned repeat penalty. Deterministic jobs use 1 so Ollama does not apply 1.1.';
comment on column public.gpumesh_jobs.num_ctx is
  'Pinned context length. Deterministic jobs use 2048 so a Modelfile cannot change it.';
