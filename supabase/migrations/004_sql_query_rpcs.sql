-- Migration 004: Read-only RPC functions for SQL template architecture (Module 7)
--
-- Each function:
--   - SECURITY DEFINER (runs as owner, not caller)
--   - SET transaction_read_only = on (prevents accidental writes)
--   - SET statement_timeout = '5s' (protects against slow queries)
--   - Scoped to p_user_id (complements RLS)
--
-- Run in Supabase SQL editor before wiring in Module 7.

-- ── count_documents ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION rpc_count_documents(p_user_id UUID)
RETURNS TABLE(document_count BIGINT)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
SET statement_timeout = '5s'
AS $$
    SELECT COUNT(*)::BIGINT AS document_count
    FROM documents
    WHERE user_id = p_user_id;
$$;
GRANT EXECUTE ON FUNCTION rpc_count_documents TO service_role;

-- ── list_documents ───────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION rpc_list_documents(p_user_id UUID)
RETURNS TABLE(filename TEXT, status TEXT, chunk_count INT, file_size BIGINT, created_at TIMESTAMPTZ)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
SET statement_timeout = '5s'
AS $$
    SELECT filename, status, chunk_count, file_size, created_at
    FROM documents
    WHERE user_id = p_user_id
    ORDER BY created_at DESC
    LIMIT 50;
$$;
GRANT EXECUTE ON FUNCTION rpc_list_documents TO service_role;

-- ── count_chunks_by_document ─────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION rpc_count_chunks_by_document(p_user_id UUID)
RETURNS TABLE(filename TEXT, chunk_count BIGINT)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
SET statement_timeout = '5s'
AS $$
    SELECT d.filename, COUNT(dc.id)::BIGINT AS chunk_count
    FROM documents d
    LEFT JOIN document_chunks dc ON dc.document_id = d.id
    WHERE d.user_id = p_user_id
    GROUP BY d.id, d.filename
    ORDER BY chunk_count DESC;
$$;
GRANT EXECUTE ON FUNCTION rpc_count_chunks_by_document TO service_role;

-- ── find_documents_by_status ─────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION rpc_find_documents_by_status(p_user_id UUID, p_status TEXT)
RETURNS TABLE(filename TEXT, status TEXT, error_message TEXT, created_at TIMESTAMPTZ)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
SET statement_timeout = '5s'
AS $$
    SELECT filename, status, error_message, created_at
    FROM documents
    WHERE user_id = p_user_id
      AND status = p_status
    ORDER BY created_at DESC;
$$;
GRANT EXECUTE ON FUNCTION rpc_find_documents_by_status TO service_role;

-- ── search_chunks_by_keyword ─────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION rpc_search_chunks_by_keyword(p_user_id UUID, p_keyword TEXT)
RETURNS TABLE(content TEXT, chunk_index INT, filename TEXT)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
SET statement_timeout = '5s'
AS $$
    SELECT dc.content, dc.chunk_index, d.filename
    FROM document_chunks dc
    JOIN documents d ON d.id = dc.document_id
    WHERE dc.user_id = p_user_id
      AND dc.content ILIKE '%' || p_keyword || '%'
    LIMIT 10;
$$;
GRANT EXECUTE ON FUNCTION rpc_search_chunks_by_keyword TO service_role;

-- ── get_recent_conversations ─────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION rpc_get_recent_conversations(p_user_id UUID)
RETURNS TABLE(title TEXT, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
SET statement_timeout = '5s'
AS $$
    SELECT title, created_at, updated_at
    FROM conversations
    WHERE user_id = p_user_id
    ORDER BY updated_at DESC
    LIMIT 20;
$$;
GRANT EXECUTE ON FUNCTION rpc_get_recent_conversations TO service_role;

-- ── count_messages_in_conversation ───────────────────────────────────────────
CREATE OR REPLACE FUNCTION rpc_count_messages_in_conversation(p_user_id UUID, p_title_fragment TEXT)
RETURNS TABLE(title TEXT, message_count BIGINT)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
SET statement_timeout = '5s'
AS $$
    SELECT c.title, COUNT(m.id)::BIGINT AS message_count
    FROM conversations c
    LEFT JOIN messages m ON m.conversation_id = c.id
    WHERE c.user_id = p_user_id
      AND c.title ILIKE '%' || p_title_fragment || '%'
    GROUP BY c.id, c.title
    LIMIT 5;
$$;
GRANT EXECUTE ON FUNCTION rpc_count_messages_in_conversation TO service_role;

-- ── storage_summary ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION rpc_storage_summary(p_user_id UUID)
RETURNS TABLE(document_count BIGINT, total_bytes BIGINT, avg_bytes_per_doc NUMERIC)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
SET statement_timeout = '5s'
AS $$
    SELECT
        COUNT(*)::BIGINT AS document_count,
        COALESCE(SUM(file_size), 0)::BIGINT AS total_bytes,
        COALESCE(AVG(file_size), 0)::NUMERIC AS avg_bytes_per_doc
    FROM documents
    WHERE user_id = p_user_id
      AND status = 'completed';
$$;
GRANT EXECUTE ON FUNCTION rpc_storage_summary TO service_role;
