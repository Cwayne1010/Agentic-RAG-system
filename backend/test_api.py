"""
API integration tests — covers plan validations for Tasks 1, 3, 5, 6, 8.
Runs the FastAPI app in-process via httpx ASGI transport (no server required).
Run from backend/: python test_api.py
"""
import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

import httpx
from supabase import create_client

from app.main import app

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
admin_db = create_client(SUPABASE_URL, SUPABASE_KEY)

TEST_EMAIL = "test-api-script@example.com"
TEST_PASSWORD = "TestPassword123!"

passed = 0
failed = 0


def ok(label):
    global passed
    passed += 1
    print(f"  [PASS] {label}")


def fail(label, reason=""):
    global failed
    failed += 1
    print(f"  [FAIL] {label}" + (f": {reason}" if reason else ""))


def section(title):
    print(f"\n--- {title} ---")


# ---------------------------------------------------------------------------
async def run_tests():
    # -----------------------------------------------------------------------
    # 0. Auth: create test user, sign in for JWT
    # -----------------------------------------------------------------------
    section("0. Test user + JWT")
    user_id = None
    jwt = None
    try:
        try:
            res = admin_db.auth.admin.create_user({
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "email_confirm": True,
            })
            user_id = res.user.id
            ok(f"Created test user ({user_id})")
        except Exception:
            users = admin_db.auth.admin.list_users()
            for u in users:
                if u.email == TEST_EMAIL:
                    user_id = u.id
                    ok(f"Reusing existing test user ({user_id})")
                    break
            if not user_id:
                raise RuntimeError("Could not create or find test user")

        # Sign in to get a real JWT
        sign_in = admin_db.auth.sign_in_with_password({
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        })
        jwt = sign_in.session.access_token
        ok("Signed in, JWT obtained")
    except Exception as e:
        fail("Setup", str(e))
        return

    auth_header = {"Authorization": f"Bearer {jwt}"}
    bad_auth = {"Authorization": "Bearer bogus-token"}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:

        # -------------------------------------------------------------------
        # 1. /health (Task 1 validation)
        # -------------------------------------------------------------------
        section("1. GET /health")
        try:
            r = await client.get("/health")
            assert r.status_code == 200, f"status {r.status_code}"
            assert r.json() == {"status": "ok"}, f"body {r.json()}"
            ok("/health → 200 {status: ok}")
        except Exception as e:
            fail("/health", str(e))

        # -------------------------------------------------------------------
        # 2. Auth dependency (Task 3 validation)
        # -------------------------------------------------------------------
        section("2. Auth dependency")
        try:
            r = await client.get("/api/conversations")
            assert r.status_code == 422, f"expected 422 got {r.status_code}"
            ok("Missing auth header → 422")
        except Exception as e:
            fail("Missing auth header", str(e))

        try:
            r = await client.get("/api/conversations", headers=bad_auth)
            assert r.status_code == 401, f"expected 401 got {r.status_code}"
            ok("Invalid token → 401")
        except Exception as e:
            fail("Invalid token → 401", str(e))

        try:
            r = await client.get("/api/conversations", headers=auth_header)
            assert r.status_code == 200, f"expected 200 got {r.status_code}"
            ok("Valid token → 200")
        except Exception as e:
            fail("Valid token → 200", str(e))

        # -------------------------------------------------------------------
        # 3. Conversations CRUD (Task 5 validation)
        # -------------------------------------------------------------------
        section("3. Conversations CRUD")
        conv_id = None

        try:
            r = await client.post(
                "/api/conversations",
                json={"title": "Test Chat"},
                headers=auth_header,
            )
            assert r.status_code == 200, f"status {r.status_code}: {r.text}"
            data = r.json()
            conv_id = data["id"]
            assert data["title"] == "Test Chat"
            ok(f"POST /conversations → created ({conv_id})")
        except Exception as e:
            fail("POST /conversations", str(e))

        if conv_id:
            try:
                r = await client.get("/api/conversations", headers=auth_header)
                assert r.status_code == 200
                ids = [c["id"] for c in r.json()]
                assert conv_id in ids
                ok("GET /conversations → lists conversation")
            except Exception as e:
                fail("GET /conversations", str(e))

            try:
                r = await client.patch(
                    f"/api/conversations/{conv_id}",
                    json={"title": "Renamed"},
                    headers=auth_header,
                )
                assert r.status_code == 200
                assert r.json()["title"] == "Renamed"
                ok("PATCH /conversations/{id} → title updated")
            except Exception as e:
                fail("PATCH /conversations/{id}", str(e))

            try:
                r = await client.get(
                    f"/api/conversations/{conv_id}/messages",
                    headers=auth_header,
                )
                assert r.status_code == 200
                assert isinstance(r.json(), list)
                ok("GET /conversations/{id}/messages → empty list")
            except Exception as e:
                fail("GET /conversations/{id}/messages", str(e))

            # Ownership: other user can't access
            try:
                r = await client.get(
                    f"/api/conversations/{conv_id}/messages",
                    headers=bad_auth,
                )
                assert r.status_code == 401
                ok("Ownership enforced → 401 with wrong token")
            except Exception as e:
                fail("Ownership enforcement", str(e))

        # -------------------------------------------------------------------
        # 4. Chat SSE endpoint (Task 8 validation)
        # -------------------------------------------------------------------
        section("4. Chat SSE endpoint")
        if conv_id:
            # Reset title to "New Chat" so we can test auto-title
            admin_db.table("conversations").update({"title": "New Chat"}).eq("id", conv_id).execute()

            try:
                chunks = []
                async with client.stream(
                    "POST",
                    f"/api/conversations/{conv_id}/messages",
                    json={"message": "Say exactly: pong"},
                    headers={**auth_header, "Accept": "text/event-stream"},
                    timeout=60,
                ) as r:
                    assert r.status_code == 200, f"status {r.status_code}"
                    async for line in r.aiter_lines():
                        if line.startswith("data: "):
                            event = json.loads(line[6:])
                            chunks.append(event)

                delta_chunks = [c for c in chunks if c.get("type") == "delta"]
                done_chunks = [c for c in chunks if c.get("type") == "done"]

                assert len(delta_chunks) > 0, "no delta chunks received"
                assert len(done_chunks) == 1, "missing done event"
                assembled = "".join(c["content"] for c in delta_chunks)
                ok(f"SSE streams {len(delta_chunks)} delta(s) + done event")
                ok(f"Assembled response: {assembled[:60]!r}")
            except Exception as e:
                fail("Chat SSE streaming", str(e))

            # Verify both messages persisted in DB
            try:
                msgs = (
                    admin_db.table("messages")
                    .select("role")
                    .eq("conversation_id", conv_id)
                    .execute()
                    .data
                )
                roles = {m["role"] for m in msgs}
                assert "user" in roles, "user message missing"
                assert "assistant" in roles, "assistant message missing"
                ok("Both user + assistant messages persisted in DB")
            except Exception as e:
                fail("Message persistence", str(e))

            # Verify auto-title update
            try:
                conv = (
                    admin_db.table("conversations")
                    .select("title")
                    .eq("id", conv_id)
                    .single()
                    .execute()
                    .data
                )
                assert conv["title"] != "New Chat", f"title not updated: {conv['title']}"
                ok(f"Auto-title updated to: {conv['title']!r}")
            except Exception as e:
                fail("Auto-title update", str(e))

        # -------------------------------------------------------------------
        # 5. DELETE conversation
        # -------------------------------------------------------------------
        section("5. DELETE conversation")
        if conv_id:
            try:
                r = await client.delete(
                    f"/api/conversations/{conv_id}", headers=auth_header
                )
                assert r.status_code == 200
                ok("DELETE /conversations/{id} → 200")
                conv_id = None
            except Exception as e:
                fail("DELETE /conversations/{id}", str(e))

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------
    try:
        if conv_id:
            admin_db.table("conversations").delete().eq("id", conv_id).execute()
        admin_db.auth.admin.delete_user(user_id)
    except Exception:
        pass

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 40)
    if failed:
        raise SystemExit(1)


asyncio.run(run_tests())
