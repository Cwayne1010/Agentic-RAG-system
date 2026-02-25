alter table app_settings
  add column if not exists metadata_schema jsonb not null default '[
    {"name":"doc_type","type":"string","description":"Document type","allowed_values":["contract","report","email","memo","technical","article","other"],"nullable":false},
    {"name":"language","type":"string","description":"ISO 639-1 language code","nullable":false},
    {"name":"topics","type":"array","description":"Topics from controlled vocabulary","nullable":false},
    {"name":"summary","type":"string","description":"1-2 sentence document summary","nullable":false},
    {"name":"entities","type":"array","description":"Named people, organisations, places (max 10)","nullable":false},
    {"name":"date","type":"date","description":"ISO 8601 document date if found","nullable":true}
  ]'::jsonb;
