<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Project Notes

- Frontend API access belongs in `lib/api.ts`; components should not inline backend `fetch` calls.
- The `/` new-run console loads consulting types from `GET /tasks`, uploads context files through multipart `POST /documents`, and passes uploaded IDs to `POST /runs` as `document_ids`.
- Failed runs resume in place through `POST /runs/{run_id}/retry`; keep retry UX on the current run detail URL and route calls through `lib/api.ts`.
- Multipart upload must use `FormData` without manually setting `Content-Type`; JSON endpoints still use the shared typed request helper.
- Keep frontend DTOs in `lib/types.ts` aligned with backend Pydantic schemas when changing API surfaces.
