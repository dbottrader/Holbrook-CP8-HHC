-- Hardware backend reported at registration: cuda, rocm, or cpu.
-- The inference runtime stays in gpumesh_nodes.backend (ollama, vllm, llamacpp, cpu).
-- Default 'cpu' keeps rows written before this column on the old behavior.

alter table public.gpumesh_nodes
  add column if not exists accelerator text not null default 'cpu';

comment on column public.gpumesh_nodes.accelerator is
  'Hardware backend from the worker: cuda, rocm, or cpu. Inference runtime stays in backend.';
