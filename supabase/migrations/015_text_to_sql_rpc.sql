-- Safe SQL executor for Text-to-SQL tool (Module 7)
-- Only allows SELECT statements; validates the user_id is present in the query.
CREATE OR REPLACE FUNCTION execute_user_sql(sql_query text, p_user_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  result jsonb;
BEGIN
  -- Validate SELECT-only
  IF NOT lower(trim(sql_query)) ~ '^select' THEN
    RAISE EXCEPTION 'Only SELECT statements are allowed';
  END IF;

  -- Require the user_id literal to be present (defense-in-depth)
  IF NOT sql_query LIKE '%' || p_user_id::text || '%' THEN
    RAISE EXCEPTION 'Query must reference the user_id for data isolation';
  END IF;

  EXECUTE format('SELECT jsonb_agg(row_to_json(t)) FROM (%s) t', sql_query) INTO result;
  RETURN COALESCE(result, '[]'::jsonb);
END;
$$;

-- Allow authenticated users to call this function
GRANT EXECUTE ON FUNCTION execute_user_sql(text, uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION execute_user_sql(text, uuid) TO service_role;
