# CLAUDE.md

RAG app with chat (default) and document ingestion interfaces. Config via env vars, no admin UI.

## Stack
- Frontend: SvelteKit + Tailwind + shadcn-svelte
- Backend: Python + FastAPI
- Database: Supabase (Postgres, pgvector, Auth, Storage, Realtime)
- LLM: OpenAI (Module 1), OpenRouter (Module 2+)
- Observability: LangSmith

## Context Usage
- Notify the user when context usage reaches 50% - stop and alert them before continuing

## Rules
- Python backend must use a `venv` virtual environment
- No LangChain, no LangGraph - raw SDK calls only
- Use Pydantic for structured LLM outputs
- All tables need Row-Level Security - users only see their own data
- Stream chat responses via SSE
- Use Supabase Realtime for ingestion status updates
- Module 2+ uses stateless completions - store and send chat history yourself
- Ingestion is manual file upload only - no connectors or automated pipelines

## Planning
- Save all plans to `.agent/plans/` folder
- Naming convention: `{sequence}.{plan-name}.md` (e.g., `1.auth-setup.md`, `2.document-ingestion.md`)
- Plans should be detailed enough to execute without ambiguity
- Each task in the plan must include at least one validation test to verify it works
- Assess complexity and single-pass feasibility - can an agent realistically complete this in one go?
- Include a complexity indicator at the top of each plan:
  - ✅ **Simple** - Single-pass executable, low risk
  - ⚠️ **Medium** - May need iteration, some complexity
  - 🔴 **Complex** - Break into sub-plans before executing

## Development Flow
1. **Plan** - Create a detailed plan and save it to `.agent/plans/`
2. **Build** - Execute the plan to implement the feature
3. **Validate** - Test and verify the implementation works correctly. Use browser testing where applicable via an appropriate MCP
4. **Iterate** - Fix any issues found during validation

## Testing
- Always output the full test code/commands for the user to run manually (SQL to paste into Supabase dashboard, curl commands, browser steps, etc.)
- Do not assume tests can be run automatically — surface them explicitly so the user can execute them
- The validation suite lives at `.agent/plans/validation/` (3 files: backend-api, ragas-eval, frontend-ux) — update it whenever new features are built:
  - Add new test cases for every new endpoint, UI interaction, or database behaviour
  - Add the new tests to the Pass/Fail Tracker checklist at the bottom of the relevant file
  - Keep the Execution Order table accurate (note any prerequisites)

## Markdown Formatting
All markdown docs (plans, validation files, notes) must follow this structure:
- `##` sections with a blank line before each
- Test entries formatted as `### ID — Description` with fenced code block, **Pass:** and **Fail:** on separate lines
- Every test file ends with an Execution Order table and a Pass/Fail Tracker checklist (`[x]`, `[ ]`, `[-]`)
- Tables use standard GFM pipe syntax with header separator row

## Dev Commands
**Restart backend:**
```bash
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8001
```

## Progress
Check PROGRESS.md for current module status. Update it as you complete tasks.

## Test Credentials
For browser testing and validation
- **Email** flocker@login.com
- **Password** flocker

For testing the isolation of data between users
- **Email** clocker@login.com
- **Password** clocker
