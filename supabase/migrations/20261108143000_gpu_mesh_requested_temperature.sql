-- Client temperature for a mesh job. The executed temperature column stays 0.
-- gpumesh_jobs.seed already exists and stores the hub-assigned seed.
-- Apply this before deploying the gpu-mesh function that writes the column.

alter table public.gpumesh_jobs
  add column if not exists requested_temperature double precision;

comment on column public.gpumesh_jobs.requested_temperature is
  'Temperature the client asked for. Volunteer jobs execute at temperature 0 with gpumesh_jobs.seed.';
