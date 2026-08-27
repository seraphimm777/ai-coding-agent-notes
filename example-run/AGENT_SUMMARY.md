# Change Summary (reference output)

Added tagging and search to the Notes API so users can organise and find notes
without a UI change:

**New/changed endpoints**
- `GET /notes?search=keyword` — full-text search across `title` + `content`,
  ranked by MongoDB text-search relevance score.
- `GET /notes?tag=work` — filter notes by tag (case-insensitive; both params
  can be combined: `?search=foo&tag=work`).
- `GET /notes/tags` — returns the sorted, distinct list of tags currently in use,
  e.g. `["personal","recipe","work"]`, for building a filter/tag-cloud UI.
- `POST /notes` / `PUT /notes/:noteId` — now accept an optional `tags: string[]`
  field. Tags are trimmed, lowercased, and deduped server-side, so `"Work"` and
  `" work "` both normalize to `"work"`.

**Example**
```
POST /notes
{ "title": "Pasta", "content": "Boil water, add salt...", "tags": ["Recipe", "Dinner"] }

GET /notes?search=pasta        -> returns the note above, ranked by relevance
GET /notes?tag=recipe          -> returns the note above
GET /notes/tags                -> ["dinner", "recipe"]
```

**Assumptions / trade-offs**
- This repo is backend-only (confirmed during exploration — no frontend files
  exist), so the feature is delivered as API surface a client can consume; no
  frontend was built.
- Existing behavior is unchanged: `GET /notes` with no query params still returns
  all notes, newest first, in the same shape as before (with `tags: []` added).
- No pagination was added to search results — the original `findAll` had none
  either, so this keeps scope consistent with the existing app.

**Next steps for the user**
- No new dependencies — the tags/search feature is built entirely on Mongoose,
  which was already a dependency.
- If you have existing notes in the database from before this change, they'll
  simply have `tags: []` until edited — no migration needed.
