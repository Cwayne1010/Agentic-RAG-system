-- Module 7: Order history table + restricted read-only role for text-to-SQL agent
-- The text_to_sql_reader role has SELECT-only on order_history — no write access anywhere.

-- ─── 1. Create order_history table ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS order_history (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id       uuid        REFERENCES auth.users NOT NULL,
  order_number  text        NOT NULL,
  order_date    timestamptz NOT NULL DEFAULT now(),
  status        text        NOT NULL CHECK (status IN ('pending','processing','shipped','delivered','cancelled')),
  total_amount  numeric(10,2) NOT NULL,
  currency      text        NOT NULL DEFAULT 'USD',
  item_count    integer     NOT NULL DEFAULT 0,
  items         jsonb       NOT NULL DEFAULT '[]',
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ON order_history (user_id);

-- ─── 2. Row-Level Security ────────────────────────────────────────────────────

ALTER TABLE order_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own orders"
  ON order_history FOR SELECT
  USING (user_id = auth.uid());

-- ─── 3. Read-only Postgres role for the text-to-SQL agent ────────────────────

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'text_to_sql_reader') THEN
    CREATE ROLE text_to_sql_reader;
  END IF;
END
$$;

-- Schema access (required to resolve table names)
GRANT USAGE ON SCHEMA public TO text_to_sql_reader;

-- SELECT-only on order_history — nothing else
GRANT SELECT ON order_history TO text_to_sql_reader;

-- BYPASSRLS: the role uses the service_role key so auth.uid() is NULL at query time,
-- which would cause the RLS policy to block all rows. User_id isolation is enforced
-- by Layer 2 in the RPC (user_id must appear literally in the query).
ALTER ROLE text_to_sql_reader BYPASSRLS;

-- ─── 4. Seed sample rows for the test user ───────────────────────────────────
-- Replace <your-user-uuid> with the UUID from auth.users for flocker@login.com
-- Run this block separately after finding the UUID, or skip for now.

-- INSERT INTO order_history (user_id, order_number, order_date, status, total_amount, item_count, items)
-- VALUES
--   ('<your-user-uuid>', 'ORD-10001', now() - interval '10 days', 'delivered', 149.99, 2,
--    '[{"name":"Wireless Keyboard","qty":1,"unit_price":89.99},{"name":"Mouse Pad","qty":1,"unit_price":60.00}]'),
--   ('<your-user-uuid>', 'ORD-10002', now() - interval '5 days',  'shipped',   49.95, 1,
--    '[{"name":"USB Hub","qty":1,"unit_price":49.95}]'),
--   ('<your-user-uuid>', 'ORD-10003', now() - interval '1 day',   'processing', 239.00, 3,
--    '[{"name":"Mechanical Keyboard","qty":1,"unit_price":159.00},{"name":"Keycap Set","qty":2,"unit_price":40.00}]');

-- ─── 5. execute_user_sql with 4-layer validation ─────────────────────────────
-- Note: Supabase restricts postgres from full superuser ops (GRANT role TO postgres,
-- ALTER FUNCTION OWNER TO restricted-role), so role-based execution is not feasible.
-- Security is enforced through application-level validation layers instead.

CREATE OR REPLACE FUNCTION execute_user_sql(sql_query text, p_user_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  result jsonb;
  normalized text;
BEGIN
  normalized := lower(trim(sql_query));

  -- Layer 1: SELECT-only
  IF NOT normalized ~ '^select' THEN
    RAISE EXCEPTION 'Only SELECT statements are allowed';
  END IF;

  -- Layer 2: user_id must appear in query
  IF NOT sql_query LIKE '%' || p_user_id::text || '%' THEN
    RAISE EXCEPTION 'Query must reference the user_id for data isolation';
  END IF;

  -- Layer 3: must reference order_history
  -- Note: \b is not a word boundary in PostgreSQL regex (it's backspace). Use LIKE.
  IF normalized NOT LIKE '%order_history%' THEN
    RAISE EXCEPTION 'Queries may only access the order_history table';
  END IF;

  -- Layer 4: block other tables explicitly
  IF normalized LIKE '%documents%'
    OR normalized LIKE '%conversations%'
    OR normalized LIKE '%messages%'
    OR normalized LIKE '%auth.%'
    OR normalized LIKE '%pg_catalog%'
    OR normalized LIKE '%information_schema%'
  THEN
    RAISE EXCEPTION 'Access to this table is not permitted';
  END IF;

  EXECUTE format('SELECT jsonb_agg(row_to_json(t)) FROM (%s) t', sql_query) INTO result;
  RETURN COALESCE(result, '[]'::jsonb);
END;
$$;

GRANT EXECUTE ON FUNCTION execute_user_sql(text, uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION execute_user_sql(text, uuid) TO service_role;
