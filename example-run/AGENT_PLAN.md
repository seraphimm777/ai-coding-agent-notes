# Execution Plan (reference output)

**Request:** Improve the application so users can better organise and search their notes.

This is the plan the agent's PLAN phase produces for this repository. It's included
here as a reference; running `agent/agent.py` for real writes a live version of this
file (`AGENT_PLAN.md`) into the target repo's root.

## 1. Feature decision
This repository is a Node/Express/MongoDB REST API only — there is no frontend here
(confirmed during exploration: no `views/`, `public/`, or frontend `package.json`;
the project README documents it as a "Restful CRUD API"). "Organise" and "search"
therefore need to be delivered as API capabilities a client can build on:

- **Tags** — add a `tags: [String]` field to the Note model so users can organise
  notes into freeform categories, plus a `GET /notes/tags` endpoint to list all tags
  in use (for building a filter UI).
- **Search** — add a MongoDB text index on `title` + `content` and support
  `GET /notes?search=keyword` for relevance-ranked keyword search, and
  `GET /notes?tag=name` for filtering by tag. Both are combinable.

This is the smallest change that turns "organise and search" from a UI-only concern
into something the existing CRUD API actually supports, without inventing a frontend
that doesn't exist in this repo.

## 2. Files to modify
- `app/models/note.model.js` — add `tags` field (normalized: trimmed, lowercased,
  deduped via a Mongoose setter) and two indexes (`text` on title/content, `1` on tags).
- `app/controllers/note.controller.js` — `create`/`update` accept `tags`; `findAll`
  gains `search`/`tag` query-param handling; new `listTags` controller.
- `app/routes/note.routes.js` — register `GET /notes/tags` (before `/notes/:noteId`
  so Express doesn't treat "tags" as an id).

## 3. Files to create
None — the change fits entirely within the existing MVC files, matching the repo's
existing (small, un-modularized) structure rather than introducing new layers.

## 4. Out of scope
- No frontend — none exists in this repo; adding one is a separate, much larger task.
- No pagination/rate limiting on search — not requested, and the existing `findAll`
  had none either; keeping scope tight.
- No auth/per-user notes — the existing API has no auth concept at all; adding one
  would change behavior far beyond "organise and search".
