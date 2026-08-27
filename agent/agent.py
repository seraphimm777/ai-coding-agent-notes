#!/usr/bin/env python3
"""
agent.py
--------
Entry point for the AI coding agent.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python agent.py --repo /path/to/node-easy-notes-app \\
        --request "Improve the application so users can better organise and search their notes."

Workflow (see README.md for full architecture write-up):
    1. EXPLORE   - read-only tool loop that builds a repository summary.
    2. PLAN      - no tools; turns the summary + request into a short written plan.
    3. IMPLEMENT - read/write tool loop that executes the plan against the repo.
    4. SUMMARIZE - read-only tool loop that reports what was actually changed.

Every phase reuses the same `run_agentic_turn` tool-loop (llm.py) with a
different system prompt and tool allow-list, which is what keeps this agent
generic: nothing about "notes", "tags" or "search" is hardcoded anywhere in
this file or in prompts.py. It works the same way for any request on any repo.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from llm import run_agentic_turn
from tools import RepoTools
import prompts

DIVIDER = "=" * 72


def log(kind: str, detail: str) -> None:
    if kind == "thought":
        prefix = "  · reasoning:"
    elif kind == "tool_call":
        prefix = "  -> tool:    "
    elif kind == "tool_result":
        prefix = "  <- result:  "
    else:
        prefix = "  "
    for line in detail.splitlines() or [""]:
        print(f"{prefix} {line}")


def phase_header(n: int, name: str) -> None:
    print(f"\n{DIVIDER}\nPHASE {n}: {name}\n{DIVIDER}")


def run(repo_path: str, request: str, max_turns_explore=10, max_turns_implement=16, max_turns_summarize=6) -> None:
    tools = RepoTools(repo_path)
    t0 = time.time()

    # ---- Phase 1: Explore ------------------------------------------------
    phase_header(1, "EXPLORE REPOSITORY")
    repo_summary = run_agentic_turn(
        tools=tools,
        system_prompt=prompts.EXPLORE_SYSTEM,
        user_message="Explore this repository and produce a Repository Summary.",
        allowed_tools={"list_files", "read_file", "run_command"},
        max_turns=max_turns_explore,
        on_event=log,
    )
    print("\n--- Repository Summary ---\n" + repo_summary)

    # ---- Phase 2: Plan -----------------------------------------------------
    phase_header(2, "EXECUTION PLAN")
    plan = run_agentic_turn(
        tools=tools,
        system_prompt=prompts.PLAN_SYSTEM,
        user_message=(
            f"Repository Summary:\n{repo_summary}\n\n"
            f"Product request:\n\"{request}\"\n\n"
            "Write the execution plan now."
        ),
        allowed_tools=set(),  # no tools in this phase by design
        max_turns=1,
        on_event=log,
    )
    print("\n--- Execution Plan ---\n" + plan)
    Path(tools.root / "AGENT_PLAN.md").write_text(
        f"# Execution Plan\n\n**Request:** {request}\n\n{plan}\n", encoding="utf-8"
    )

    # ---- Phase 3: Implement -------------------------------------------------
    phase_header(3, "IMPLEMENT")
    impl_notes = run_agentic_turn(
        tools=tools,
        system_prompt=prompts.IMPLEMENT_SYSTEM,
        user_message=f"Approved plan:\n{plan}\n\nImplement it now.",
        allowed_tools={"list_files", "read_file", "write_file", "run_command"},
        max_turns=max_turns_implement,
        on_event=log,
    )
    print("\n--- Implementation Notes ---\n" + impl_notes)

    # ---- Phase 4: Summarize ---------------------------------------------------
    phase_header(4, "SUMMARY")
    summary = run_agentic_turn(
        tools=tools,
        system_prompt=prompts.SUMMARIZE_SYSTEM,
        user_message=(
            f"Original request:\n\"{request}\"\n\nPlan:\n{plan}\n\n"
            f"Implementation notes:\n{impl_notes}\n\nWrite the final summary now."
        ),
        allowed_tools={"list_files", "read_file", "run_command"},
        max_turns=max_turns_summarize,
        on_event=log,
    )
    print("\n--- Final Summary ---\n" + summary)
    Path(tools.root / "AGENT_SUMMARY.md").write_text(summary, encoding="utf-8")

    elapsed = time.time() - t0
    print(f"\n{DIVIDER}\nDone in {elapsed:.1f}s. Wrote AGENT_PLAN.md and AGENT_SUMMARY.md to the repo.\n{DIVIDER}")


def main():
    parser = argparse.ArgumentParser(description="AI coding agent for an existing repository.")
    parser.add_argument("--repo", required=True, help="Path to the target repository")
    parser.add_argument("--request", required=True, help="Product request in plain English")
    args = parser.parse_args()

    if not Path(args.repo).exists():
        print(f"Repo path does not exist: {args.repo}", file=sys.stderr)
        sys.exit(1)

    run(args.repo, args.request)


if __name__ == "__main__":
    main()
