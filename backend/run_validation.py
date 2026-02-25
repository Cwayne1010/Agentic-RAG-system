#!/usr/bin/env python3
"""
Automated Validation Runner — Modules 1 & 2

Covers (automated):
  P1, P3, A3, C1–C5, CH4, CH5, V4, D2, D3, D4(sql), V1, V3, S1–S4, I1, I2, SQL2–SQL4

Skipped (manual — browser / LangSmith):
  P2, A1, A2, A4, CH1, CH2, CH3, D1, D4(browser), D5, D6, V2, L1, V5, S5, UX1–UX4, R1–R3

Skipped (requires Supabase SQL editor):
  I3, SQL1

Usage:
  cd backend && source venv/bin/activate && python run_validation.py
"""

import asyncio
import importlib.util
import json
import os
import sys

import httpx
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

BACKEND = "http://localhost:8000"
FLOCKER_EMAIL = "flocker@login.com"
FLOCKER_PASS = "flocker"
CLOCKER_EMAIL = "clocker@login.com"
CLOCKER_PASS = "clocker"

# ANSI colours
G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
B = "\033[94m"
BOLD = "\033[1m"
X = "\033[0m"

results: dict[str, bool | None] = {}


def ok(name: str, detail: str = "") -> None:
    results[name] = True
    print(f"  {G}✓ PASS{X} {name}" + (f"  {detail}" if detail else ""))


def fail(name: str, detail: str = "") -> None:
    results[name] = False
    print(f"  {R}✗ FAIL{X} {name}" + (f"  {detail}" if detail else ""))


def skip(name: str, detail: str = "") -> None:
    results[name] = None
    print(f"  {Y}⊘ SKIP{X} {name}" + (f"  {detail}" if detail else ""))


def manual(name: str, sql: str) -> None:
    results[name] = None
    print(f"  {Y}⊘ MANUAL{X} {name}  — paste into Supabase SQL editor:")
    for line in sql.strip().splitlines():
        print(f"      {line}")


def section(title: str) -> None:
    print(f"\n{BOLD}{B}{'─'*50}{X}")
    print(f"{BOLD}{B}  {title}{X}")
    print(f"{BOLD}{B}{'─'*50}{X}")


async def sign_in(supabase_url: str, service_key: str, email: str, password: str) -> tuple[str, str]:
    """Get a user JWT + user_id via the Supabase auth REST API.
    Keeps the service-role admin client unpolluted (signing in via the client
    switches its internal token from service-role to the user JWT, breaking RLS bypass)."""
    async with httpx.AsyncClient() as auth_http:
        r = await auth_http.post(
            f"{supabase_url}/auth/v1/token?grant_type=password",
            headers={"apikey": service_key, "Content-Type": "application/json"},
            json={"email": email, "password": password},
        )
        r.raise_for_status()
        data = r.json()
        return data["access_token"], data["user"]["id"]


async def main() -> None:
    supabase_url = os.getenv("SUPABASE_URL", "")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if not supabase_url or not service_key:
        print(f"{R}Error: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set.{X}")
        sys.exit(1)

    # Dedicated admin client — service role key, NEVER signed in as a user.
    # Signing in via the client replaces its token with the user JWT, which re-enables RLS.
    sb = create_client(supabase_url, service_key)

    # Get tokens via REST API (leaves sb's service-role session intact)
    try:
        flocker_token, flocker_id = await sign_in(supabase_url, service_key, FLOCKER_EMAIL, FLOCKER_PASS)
    except Exception as e:
        print(f"{R}Could not authenticate flocker: {e}{X}")
        sys.exit(1)

    try:
        clocker_token, _ = await sign_in(supabase_url, service_key, CLOCKER_EMAIL, CLOCKER_PASS)
    except Exception as e:
        clocker_token = None
        print(f"{Y}Warning: Could not authenticate clocker ({e}) — I1/I2 will be skipped{X}")

    fh = {"Authorization": f"Bearer {flocker_token}"}
    ch = {"Authorization": f"Bearer {clocker_token}"} if clocker_token else {}

    async with httpx.AsyncClient(base_url=BACKEND, timeout=30) as http:

        # ── PRE-FLIGHT ──────────────────────────────────────────────────────
        section("PRE-FLIGHT")

        # P1
        try:
            r = await http.get("/health")
            if r.status_code == 200 and r.json().get("status") == "ok":
                ok("P1", "backend healthy")
            else:
                fail("P1", f"HTTP {r.status_code}: {r.text[:80]}")
        except Exception as e:
            fail("P1", f"Connection refused — is the backend running? ({e})")

        # P3
        required = [
            "SUPABASE_URL",
            "SUPABASE_SERVICE_ROLE_KEY",
            "OPENROUTER_API_KEY",
            "OPENAI_API_KEY",
            "LANGSMITH_API_KEY",
        ]
        missing = [k for k in required if not os.getenv(k)]
        if not missing:
            ok("P3", "all env vars present")
        else:
            fail("P3", f"missing: {missing}")

        # ── AUTHENTICATION ──────────────────────────────────────────────────
        section("AUTHENTICATION")

        # A3
        r = await http.get("/api/conversations", headers={"Authorization": "Bearer fake_token_12345"})
        if r.status_code == 401:
            ok("A3", "bad JWT rejected with 401")
        else:
            fail("A3", f"expected 401, got {r.status_code}")

        # ── CONVERSATIONS ────────────────────────────────────────────────────
        section("CONVERSATIONS")

        conv_id: str | None = None
        deleted_conv_id: str | None = None

        # C1
        r = await http.post("/api/conversations", headers=fh, json={"title": "Test Conversation"})
        if r.status_code in (200, 201) and "id" in r.json():
            conv_id = r.json()["id"]
            ok("C1", f"created {conv_id[:8]}…  (HTTP {r.status_code})")
        else:
            fail("C1", f"HTTP {r.status_code}: {r.text[:80]}")

        # C2
        if conv_id:
            r = await http.get("/api/conversations", headers=fh)
            ids = [c["id"] for c in r.json()] if r.status_code == 200 else []
            if r.status_code == 200 and conv_id in ids:
                ok("C2", f"{len(ids)} conversation(s) listed")
            else:
                fail("C2", f"conv not in list (HTTP {r.status_code})")
        else:
            skip("C2", "no conv_id from C1")

        # C3
        if conv_id:
            r = await http.patch(
                f"/api/conversations/{conv_id}", headers=fh, json={"title": "Renamed"}
            )
            if r.status_code == 200 and r.json().get("title") == "Renamed":
                ok("C3", "title updated")
            else:
                fail("C3", f"HTTP {r.status_code}: {r.text[:80]}")
        else:
            skip("C3", "no conv_id from C1")

        # C4
        if conv_id:
            r = await http.delete(f"/api/conversations/{conv_id}", headers=fh)
            if r.status_code in (200, 204):
                deleted_conv_id = conv_id
                conv_id = None
                ok("C4", "deleted")
            else:
                fail("C4", f"HTTP {r.status_code}: {r.text[:80]}")
        else:
            skip("C4", "no conv_id from C1")

        # C5 — cascade check via service role
        if deleted_conv_id:
            res = (
                sb.table("messages")
                .select("id", count="exact")
                .eq("conversation_id", deleted_conv_id)
                .execute()
            )
            count = res.count if res.count is not None else len(res.data)
            if count == 0:
                ok("C5", "no orphaned messages")
            else:
                fail("C5", f"{count} orphaned messages remain")
        else:
            skip("C5", "no deleted conv from C4")

        # ── CHAT ─────────────────────────────────────────────────────────────
        section("CHAT")

        # Create a fresh conversation for chat tests
        r = await http.post("/api/conversations", headers=fh, json={"title": "Chat Test"})
        chat_conv_id = r.json()["id"] if r.status_code in (200, 201) else None

        if chat_conv_id:
            # CH5 + V4 — send a message, read full SSE stream until done event
            sse_lines: list[str] = []
            try:
                async with http.stream(
                    "POST",
                    f"/api/conversations/{chat_conv_id}/messages",
                    headers={**fh, "Content-Type": "application/json"},
                    content=json.dumps({"message": "How many hours per month does the manual tickler process consume?"}),
                ) as resp:
                    async for raw in resp.aiter_lines():
                        if raw.strip():
                            sse_lines.append(raw)
                        # Stop once we see the done event (stream complete, DB written)
                        if raw.strip() == 'data: {"type": "done"}' or '"type":"done"' in raw:
                            break
                        if len(sse_lines) >= 200:  # safety cap
                            break
            except Exception as e:
                fail("CH5", f"SSE request failed: {e}")

            data_lines = [l for l in sse_lines if l.startswith("data:")]

            # CH5
            if data_lines:
                ok("CH5", f"{len(data_lines)} data: lines received")
            else:
                fail("CH5", f"no data: lines — raw: {sse_lines[:3]}")

            # V4 — retrieval event ordering
            event_types: list[str] = []
            for line in data_lines:
                try:
                    payload = json.loads(line[5:])
                    event_types.append(payload.get("type", "?"))
                except Exception:
                    pass

            if event_types and event_types[0] == "retrieval":
                ok("V4", f"retrieval event first (types: {event_types[:4]})")
            elif event_types:
                skip(
                    "V4",
                    f"first event is '{event_types[0]}' — upload test.txt to trigger retrieval",
                )
            else:
                skip("V4", "no typed events parsed")

            # CH4 — both roles persisted
            msgs = (
                sb.table("messages")
                .select("role")
                .eq("conversation_id", chat_conv_id)
                .execute()
            )
            roles = {m["role"] for m in msgs.data}
            if "user" in roles and "assistant" in roles:
                ok("CH4", f"{len(msgs.data)} message(s) stored with correct roles")
            else:
                fail("CH4", f"roles found: {roles}")

            # Cleanup
            await http.delete(f"/api/conversations/{chat_conv_id}", headers=fh)
        else:
            fail("CH5", "could not create chat conversation")
            skip("CH4", "no chat conversation")
            skip("V4", "no chat conversation")

        # ── DOCUMENTS ────────────────────────────────────────────────────────
        section("DOCUMENTS")

        # D2
        r = await http.get("/api/documents", headers=fh)
        if r.status_code == 200:
            docs = r.json()
            completed = [d for d in docs if d.get("status") == "completed"]
            ok("D2", f"{len(docs)} document(s), {len(completed)} completed")
        else:
            fail("D2", f"HTTP {r.status_code}: {r.text[:80]}")
            docs = []
            completed = []

        # D3 — chunk count across all completed docs (embedding_dims check is manual SQL)
        if completed:
            d3_results = []
            for doc in completed:
                chunks = (
                    sb.table("document_chunks")
                    .select("id", count="exact")
                    .eq("document_id", doc["id"])
                    .execute()
                )
                count = chunks.count if chunks.count is not None else len(chunks.data)
                d3_results.append((doc["filename"], count))

            zero_chunk_docs = [f for f, c in d3_results if c == 0]
            summary = ", ".join(f"'{f}'={c}" for f, c in d3_results)
            if not zero_chunk_docs:
                ok("D3", f"{summary}  (run SQL to confirm embedding_dims=1536)")
            else:
                fail("D3", f"0 chunks for: {zero_chunk_docs}  |  all: {summary}")
        else:
            skip("D3", "no completed documents — upload a document first")

        # D4 (SQL part) — orphaned chunks
        all_chunks = sb.table("document_chunks").select("document_id").execute()
        all_doc_ids = {d["id"] for d in sb.table("documents").select("id").execute().data}
        chunk_doc_ids = {c["document_id"] for c in all_chunks.data}
        orphans = chunk_doc_ids - all_doc_ids
        if not orphans:
            ok("D4", "no orphaned chunks")
        else:
            fail("D4", f"{len(orphans)} orphaned chunk document_id(s)")

        # ── VECTOR SEARCH & RAG ───────────────────────────────────────────────
        section("VECTOR SEARCH & RAG")

        # V1 — RPC self-similarity
        sample = sb.table("document_chunks").select("id,embedding").limit(1).execute()
        if sample.data and sample.data[0].get("embedding"):
            embedding = sample.data[0]["embedding"]
            rpc = sb.rpc(
                "match_document_chunks",
                {
                    "query_embedding": embedding,
                    "match_count": 5,
                    "match_user_id": flocker_id,
                },
            ).execute()
            if rpc.data:
                ok("V1", f"RPC returned {len(rpc.data)} result(s)")
            else:
                fail("V1", "RPC returned 0 results at threshold 0.1")
        else:
            skip("V1", "no chunks in DB — upload a document first")

        # V3 — user-scoped chunk counts
        flocker_doc_ids = [
            d["id"]
            for d in sb.table("documents").select("id").eq("user_id", flocker_id).execute().data
        ]
        if flocker_doc_ids:
            f_chunks = (
                sb.table("document_chunks")
                .select("id", count="exact")
                .in_("document_id", flocker_doc_ids)
                .execute()
            )
            all_count_res = (
                sb.table("document_chunks").select("id", count="exact").execute()
            )
            f_count = f_chunks.count if f_chunks.count is not None else len(f_chunks.data)
            a_count = all_count_res.count if all_count_res.count is not None else len(all_count_res.data)
            if f_count == a_count:
                ok("V3", f"all {a_count} chunk(s) belong to flocker")
            else:
                skip(
                    "V3",
                    f"flocker has {f_count}/{a_count} chunk(s)"
                    " — other users may have documents too (check manually)",
                )
        else:
            skip("V3", "flocker has no documents")

        # ── SETTINGS ─────────────────────────────────────────────────────────
        section("SETTINGS")

        # S1
        r = await http.get("/api/settings", headers=fh)
        original_chat_model: str | None = None
        if r.status_code == 200 and "embedding_model" in r.json() and "chat_model" in r.json():
            original_chat_model = r.json()["chat_model"]
            ok("S1", f"chat_model={original_chat_model}")
        else:
            fail("S1", f"HTTP {r.status_code}: {r.text[:80]}")

        # S2
        r = await http.patch(
            "/api/settings", headers=fh, json={"chat_model": "google/gemini-2.0-flash"}
        )
        if r.status_code == 200 and r.json().get("chat_model") == "google/gemini-2.0-flash":
            ok("S2", "chat model updated")
            if original_chat_model:
                await http.patch(
                    "/api/settings", headers=fh, json={"chat_model": original_chat_model}
                )
        else:
            fail("S2", f"HTTP {r.status_code}: {r.text[:80]}")

        # S3
        r = await http.post(
            "/api/settings/validate-model",
            headers=fh,
            json={"model_id": "fake/nonexistent-model-xyz-abc"},
        )
        rejected = r.status_code >= 400 or (r.status_code == 200 and not r.json().get("valid", True))
        if rejected:
            ok("S3", f"invalid model rejected (HTTP {r.status_code})")
        else:
            fail("S3", f"invalid model accepted: {r.json()}")

        # S4 — embedding lock
        flocker_docs_count_res = (
            sb.table("documents")
            .select("id", count="exact")
            .eq("user_id", flocker_id)
            .execute()
        )
        flocker_doc_count = (
            flocker_docs_count_res.count
            if flocker_docs_count_res.count is not None
            else len(flocker_docs_count_res.data)
        )
        if flocker_doc_count > 0:
            r = await http.patch(
                "/api/settings", headers=fh, json={"embedding_model": "text-embedding-3-large"}
            )
            if r.status_code >= 400:
                ok("S4", "embedding model locked while docs exist")
            else:
                fail("S4", f"embedding model changed despite {flocker_doc_count} docs (HTTP {r.status_code})")
        else:
            skip("S4", "flocker has no documents — upload one first")

        # ── DATA ISOLATION ────────────────────────────────────────────────────
        section("DATA ISOLATION")

        # I1
        if clocker_token:
            r = await http.post(
                "/api/conversations", headers=ch, json={"title": "Clocker Private"}
            )
            if r.status_code in (200, 201):
                clocker_conv_id = r.json()["id"]
                r2 = await http.get("/api/conversations", headers=fh)
                flocker_ids = {c["id"] for c in r2.json()} if r2.status_code == 200 else set()
                if clocker_conv_id not in flocker_ids:
                    ok("I1", "flocker cannot see clocker's conversation")
                else:
                    fail("I1", "clocker's conversation visible to flocker!")
                await http.delete(f"/api/conversations/{clocker_conv_id}", headers=ch)
            else:
                fail("I1", f"could not create clocker conversation: HTTP {r.status_code}")
        else:
            skip("I1", "clocker auth failed")

        # I2
        if clocker_token:
            r_f = await http.get("/api/documents", headers=fh)
            r_c = await http.get("/api/documents", headers=ch)
            if r_f.status_code == 200 and r_c.status_code == 200:
                f_ids = {d["id"] for d in r_f.json()}
                c_ids = {d["id"] for d in r_c.json()}
                overlap = f_ids & c_ids
                if not overlap:
                    ok("I2", "no document overlap between users")
                else:
                    fail("I2", f"{len(overlap)} document(s) visible to both users!")
            else:
                fail("I2", f"HTTP flocker={r_f.status_code} clocker={r_c.status_code}")
        else:
            skip("I2", "clocker auth failed")

        # I3 — needs Supabase SQL editor
        manual(
            "I3",
            """SELECT tablename, policyname, cmd
FROM pg_policies
WHERE tablename IN ('conversations','messages','documents','document_chunks')
ORDER BY tablename, policyname;
-- Pass: ≥1 policy per table""",
        )

        # ── SQL TEMPLATES ─────────────────────────────────────────────────────
        section("SQL TEMPLATES")

        tools_path = os.path.join(os.path.dirname(__file__), "app", "tools", "sql_templates.py")
        if os.path.exists(tools_path):
            spec = importlib.util.spec_from_file_location("sql_templates", tools_path)
            sql_mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            try:
                spec.loader.exec_module(sql_mod)  # type: ignore[union-attr]
                execute_query = sql_mod.execute_query

                # SQL2 — valid template returns data
                try:
                    result = await execute_query("count_documents", {}, flocker_id)
                    ok("SQL2", f"count_documents → {result.rows}")
                except Exception as e:
                    fail("SQL2", str(e)[:80])

                # SQL3 — invalid template name rejected
                try:
                    await execute_query("DROP TABLE documents", {}, "any-id")
                    fail("SQL3", "should have raised ValueError")
                except ValueError:
                    ok("SQL3", "invalid template name rejected")
                except Exception as e:
                    fail("SQL3", f"unexpected error: {e}")

                # SQL4 — missing required param rejected
                try:
                    await execute_query("find_documents_by_status", {}, flocker_id)
                    fail("SQL4", "should have raised ValueError for missing param")
                except ValueError:
                    ok("SQL4", "missing param rejected")
                except Exception as e:
                    fail("SQL4", f"unexpected error: {e}")

            except Exception as e:
                fail("SQL2", f"failed to load sql_templates: {e}")
                skip("SQL3", "module load failed")
                skip("SQL4", "module load failed")

            # SQL1 — needs Supabase SQL editor
            manual(
                "SQL1",
                """SELECT routine_name
FROM information_schema.routines
WHERE routine_schema = 'public' AND routine_name LIKE 'rpc_%'
ORDER BY routine_name;
-- Pass: 8 rows""",
            )
        else:
            skip("SQL2", "app/tools/sql_templates.py not found")
            skip("SQL3", "app/tools/sql_templates.py not found")
            skip("SQL4", "app/tools/sql_templates.py not found")
            skip("SQL1", "app/tools/sql_templates.py not found")

        # ── RECORD MANAGER ────────────────────────────────────────────────────────
        section("RECORD MANAGER")

        # RM1 — content_hash column exists
        try:
            sb.table("documents").select("content_hash").limit(1).execute()
            ok("RM1", "content_hash column exists")
        except Exception as e:
            fail("RM1", f"column missing — apply 008_content_hash.sql ({str(e)[:60]})")

        # RM2 — partial index (needs SQL editor)
        manual(
            "RM2",
            """SELECT indexname, indexdef FROM pg_indexes
WHERE tablename = 'documents' AND indexname = 'uq_documents_user_completed_hash';
-- Pass: 1 row; indexdef contains WHERE (status = 'completed')""",
        )

        # Helper: poll until a document reaches a terminal status
        async def wait_for_status(doc_id: str, terminal: set, timeout: int = 25) -> str | None:
            for _ in range(timeout):
                await asyncio.sleep(1)
                r_poll = await http.get("/api/documents", headers=fh)
                if r_poll.status_code == 200:
                    for d in r_poll.json():
                        if d["id"] == doc_id and d["status"] in terminal:
                            return d["status"]
            return None

        dedup_content = b"hello record manager dedup test content unique 12345"
        import hashlib as _hashlib
        expected_hash = _hashlib.sha256(dedup_content).hexdigest()
        dedup_doc_id = None

        # RM3 + RM7: upload, wait for completed, upload again → expect 409
        r = await http.post(
            "/api/documents/upload",
            headers=fh,
            files={"file": ("rm_test_dedup.txt", dedup_content, "text/plain")},
        )
        if r.status_code == 200:
            dedup_doc_id = r.json()["id"]
            status = await wait_for_status(dedup_doc_id, {"completed", "failed"})

            # RM7 — hash stored correctly
            db_row = sb.table("documents").select("content_hash").eq("id", dedup_doc_id).execute()
            stored_hash = db_row.data[0].get("content_hash") if db_row.data else None
            if stored_hash == expected_hash:
                ok("RM7", f"hash matches ({expected_hash[:16]}...)")
            else:
                fail("RM7", f"expected {expected_hash[:16]}... stored {str(stored_hash)[:16]}...")

            if status == "completed":
                r2 = await http.post(
                    "/api/documents/upload",
                    headers=fh,
                    files={"file": ("rm_test_dedup.txt", dedup_content, "text/plain")},
                )
                if r2.status_code == 409 and "Duplicate" in r2.json().get("detail", ""):
                    ok("RM3", r2.json()["detail"][:70])
                else:
                    fail("RM3", f"expected 409, got {r2.status_code}: {r2.text[:80]}")
            else:
                skip("RM3", f"first upload did not complete (status={status}) — check ingestion")
                skip("RM7", "depends on RM3")
        else:
            fail("RM3", f"first upload failed: HTTP {r.status_code}: {r.text[:80]}")
            skip("RM7", "first upload failed")

        # RM4 — incremental update: same filename, new content → old deleted, new created
        v1 = b"version one content for incremental update test"
        v2 = b"version two completely different content for update test"
        r1 = await http.post(
            "/api/documents/upload",
            headers=fh,
            files={"file": ("rm_update_test.txt", v1, "text/plain")},
        )
        if r1.status_code == 200:
            old_id = r1.json()["id"]
            await wait_for_status(old_id, {"completed", "failed"})
            r2 = await http.post(
                "/api/documents/upload",
                headers=fh,
                files={"file": ("rm_update_test.txt", v2, "text/plain")},
            )
            if r2.status_code == 200 and r2.json()["id"] != old_id:
                new_id = r2.json()["id"]
                old_check = sb.table("documents").select("id").eq("id", old_id).execute()
                name_check = (
                    sb.table("documents")
                    .select("id")
                    .eq("user_id", flocker_id)
                    .eq("filename", "rm_update_test.txt")
                    .execute()
                )
                if not old_check.data and len(name_check.data) == 1:
                    ok("RM4", f"old doc gone, new id {new_id[:8]}... — only 1 row with that filename")
                elif old_check.data:
                    fail("RM4", "old document still exists in DB after update")
                else:
                    fail("RM4", f"{len(name_check.data)} rows with same filename (expected 1)")
            else:
                fail("RM4", f"HTTP {r2.status_code} or same id returned: {r2.text[:80]}")
        else:
            fail("RM4", f"v1 upload failed: HTTP {r1.status_code}: {r1.text[:80]}")

        # RM5 — re-upload of failed doc is allowed
        rm5_content = b"rm5 failed retry test content xyz987abc"
        r_init = await http.post(
            "/api/documents/upload",
            headers=fh,
            files={"file": ("rm5_retry_test.txt", rm5_content, "text/plain")},
        )
        if r_init.status_code == 200:
            rm5_id = r_init.json()["id"]
            await wait_for_status(rm5_id, {"completed", "failed"})
            # Force status to failed so the partial index no longer covers it
            sb.table("documents").update({"status": "failed"}).eq("id", rm5_id).execute()
            r_retry = await http.post(
                "/api/documents/upload",
                headers=fh,
                files={"file": ("rm5_retry_test.txt", rm5_content, "text/plain")},
            )
            if r_retry.status_code == 200:
                ok("RM5", "failed doc re-upload returns 200 (not 409)")
            else:
                fail("RM5", f"expected 200, got {r_retry.status_code}: {r_retry.text[:80]}")
        else:
            skip("RM5", f"setup upload failed: HTTP {r_init.status_code}")

        # RM6 — cross-user: clocker can upload content flocker already has completed
        if clocker_token:
            rm6_content = b"shared content cross-user isolation test unique content 654321"
            r_f = await http.post(
                "/api/documents/upload",
                headers=fh,
                files={"file": ("rm6_crossuser.txt", rm6_content, "text/plain")},
            )
            if r_f.status_code == 200:
                rm6_id = r_f.json()["id"]
                await wait_for_status(rm6_id, {"completed", "failed"})
                r_c = await http.post(
                    "/api/documents/upload",
                    headers=ch,
                    files={"file": ("rm6_crossuser.txt", rm6_content, "text/plain")},
                )
                if r_c.status_code == 200:
                    ok("RM6", "clocker can upload flocker's content — no cross-user dedup")
                else:
                    fail("RM6", f"expected 200, got {r_c.status_code}: {r_c.text[:80]}")
            else:
                fail("RM6", f"flocker upload failed: HTTP {r_f.status_code}")
        else:
            skip("RM6", "clocker auth failed")

        # Cleanup test documents created during RM tests
        test_names = {"rm_test_dedup.txt", "rm_update_test.txt", "rm5_retry_test.txt", "rm6_crossuser.txt"}
        for token, label in [(flocker_token, "flocker"), (clocker_token, "clocker") if clocker_token else (None, None)]:
            if not token:
                continue
            r_list = await http.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
            if r_list.status_code == 200:
                for doc in r_list.json():
                    if doc["filename"] in test_names:
                        await http.delete(
                            f"/api/documents/{doc['id']}",
                            headers={"Authorization": f"Bearer {token}"},
                        )

    # ── SUMMARY ───────────────────────────────────────────────────────────────
    passed = sum(1 for v in results.values() if v is True)
    failed_list = [k for k, v in results.items() if v is False]
    skipped = sum(1 for v in results.values() if v is None)

    print(f"\n{BOLD}{'═'*50}{X}")
    print(f"{BOLD}  RESULTS{X}")
    print(f"{'═'*50}")
    print(
        f"  {G}{passed} passed{X}   "
        f"{R}{len(failed_list)} failed{X}   "
        f"{Y}{skipped} skipped/manual{X}   "
        f"({len(results)} automated)"
    )
    if failed_list:
        print(f"\n  {R}Failed:{X}")
        for name in failed_list:
            print(f"    • {name}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
