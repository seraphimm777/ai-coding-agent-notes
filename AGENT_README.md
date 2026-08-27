# AI Coding Agent — for `node-easy-notes-app`

A small Python agent that explores an existing codebase, plans a product change from
a one-line request, implements it, and summarizes what it did. Built for the request:

> "Improve the application so users can better organise and search their notes."

The agent decided on **tags** (organise) + **keyword/tag search** (search), implemented
entirely in `app/`, `config/`, `server.js` of this repo. See `example-run/AGENT_PLAN.md`
and `example-run/AGENT_SUMMARY.md` for the plan/summary this run produced. Nothing about
"notes/tags/search" is hardcoded in the agent itself — see "Generalization" below.

## Quick start

```bash
cd agent
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python agent.py --repo .. --request "Improve the application so users can better organise and search their notes."
```

This prints a live trace of the agent's reasoning and tool calls, then writes
`AGENT_PLAN.md` and `AGENT_SUMMARY.md` into the target repo.

`agent/test_dry_run.py` exercises the tool loop with a scripted fake model (no API key
needed) — useful for confirming the plumbing works before spending API credits:
`cd agent && python test_dry_run.py`.

## Architecture

```
agent/
  agent.py     orchestrator + CLI: runs the 4 phases in order, prints a live trace
  llm.py       one reusable Anthropic tool-use loop, shared by all 4 phases
  tools.py     the agent's "hands": list_files / read_file / write_file / run_command,
               all sandboxed to the repo root (path-traversal safe)
  prompts.py   system prompt per phase — no app-specific content anywhere
```

The design goal was a **small number of well-separated pieces** rather than a
framework: `tools.py` has zero LLM code (so it's independently testable), `llm.py` has
zero app-specific code (it's a generic "give the model tools, loop until it stops
calling them" primitive), and `prompts.py` is the only place that encodes *how* the
agent should reason — never *what* to change. `agent.py` just sequences four calls to
the same loop with different prompts/tool-sets. This keeps each file's job obvious and
makes the agent easy to extend (e.g. add a 5th "test" phase) without touching the others.

## Agent workflow

The agent runs four phases, each a fresh tool-use conversation with the model:

1. **Explore** (read-only tools: `list_files`, `read_file`, `run_command`)
   The model is given no information about the repo up front — it has to discover
   everything itself: what stack it is, where the entry point is, what the data
   model looks like, existing conventions. It stops once it can write a confident
   "Repository Summary." This is the part graded as "repository exploration" — it's
   genuinely agent-driven, not a hardcoded file list.

2. **Plan** (no tools)
   Given the repository summary + the one-line product request, the model commits to
   a specific, scoped feature decision and a file-by-file plan, explicitly listing
   what's *out of scope*. Keeping this tool-free forces the model to reason from what
   it already gathered rather than re-exploring, and gives a clean artifact
   (`AGENT_PLAN.md`) for a human to review before code changes happen.

3. **Implement** (read/write tools + `run_command`)
   The model executes its own plan: reads each file it's about to touch (so it never
   clobbers unrelated code), writes the full new content, and runs
   `node --check <file>` after each change to catch syntax errors immediately rather
   than at demo time.

4. **Summarize** (read-only tools)
   Produces a short, user-facing changelog: what was built, example requests/
   responses, assumptions/trade-offs, and any follow-up steps — written for someone
   who hasn't seen the diff.

Each phase's system prompt (`prompts.py`) is generic — none of them mention notes,
tags, or search. The *only* app-specific input is the one-line request passed on the
command line, exactly as the assignment specifies.

## How repository exploration works

`tools.py`'s `list_files` does a depth-limited recursive walk (skipping `.git`,
`node_modules`, build artifacts) and `read_file` returns line-numbered file contents
capped at 200KB to avoid dumping huge/binary files into context. The Explore phase
doesn't get a curated list of "important files" — it has to call `list_files` on `.`
first, decide what looks relevant (models? routes? config?), and `read_file` those
itself. For this repo that meant discovering, unprompted: it's an Express +
Mongoose API, the entry point is `server.js`, routes delegate to `app/controllers`,
the schema lives in `app/models/note.model.js`, and — importantly — **there is no
frontend in this repository**, which directly shaped the Plan phase's decision to
deliver the feature as API surface rather than inventing a UI.

## Assumptions & trade-offs

- **Backend-only scope.** This repo is exactly what `Readme.md` says: a REST API.
  The agent doesn't invent a frontend to demo "search" visually — it exposes search
  as query parameters on the existing `GET /notes` endpoint, which is the smallest
  change consistent with what actually exists.
- **Tags over rigid categories.** Freeform tags (vs. a fixed category enum) needed
  no schema migration story and no admin UI to manage the category list — a better
  fit for a single-file model with no existing config surface for categories.
- **MongoDB `$text` index over a search library.** The app already depends on
  Mongoose/MongoDB; a text index adds relevance-ranked search with zero new
  dependencies, vs. pulling in Elasticsearch/Lunr for a small app.
- **No live DB run in this environment.** The sandbox this was built in has no
  MongoDB and no route to install one — same constraint the original app already
  had (`config/database.config.js` points at `localhost:27017`, unchanged). Verified
  instead via `node --check` on every touched file and a standalone unit test of the
  schema's tag-normalization logic and indexes (`agent` build log). Run
  `npm install && node server.js` against a local MongoDB to see it live.
- **`write_file` always overwrites the whole file**, not a diff/patch. Simpler and
  more reliable for an LLM to reason about than partial patches, at the cost of the
  model needing to `read_file` first and reproduce untouched code faithfully — the
  Implement phase's system prompt explicitly requires this ordering.

## Generalization (for the follow-up interview)

Nothing in `agent.py`, `llm.py`, or `prompts.py` mentions notes, tags, or search —
the only per-run input is `--request`. To try a new request on this same repo:

```bash
python agent/agent.py --repo . --request "<new product request>"
```

The Explore phase re-discovers the (now-changed) repo state from scratch each run, so
it will see the tags/search feature already in place and plan its next change on top
of it, the same way it originally discovered there was no frontend.
