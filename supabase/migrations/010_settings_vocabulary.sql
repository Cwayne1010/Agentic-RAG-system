alter table app_settings
  add column if not exists business_description text not null default '',
  add column if not exists topic_vocabulary jsonb not null default '[]'::jsonb;
