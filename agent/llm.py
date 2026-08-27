"""
llm.py
------
Thin wrapper around the Anthropic Messages API that runs a tool-use loop:
the model is given a system prompt + a set of tools, it calls tools, we
execute them against RepoTools, feed results back, and repeat until the
model stops calling tools (or we hit max_turns).

Kept deliberately generic (system_prompt + tool set are passed in) so the
same loop is reused for the Explore, Plan, Implement and Summarize phases
in agent.py, just with different prompts/toolsets/max_turns.
"""

from __future__ import annotations

import os
from typing import Callable

import anthropic

from tools import RepoTools, ToolResult

MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-4-5")

TOOL_SCHEMAS = [
    {
        "name": "list_files",
        "description": "Recursively list files under a directory in the repo (skips .git/node_modules).",
        "input_schema": {
            "type": "object",
            "properties": {
                "rel_path": {"type": "string", "description": "Directory relative to repo root, e.g. '.' or 'app/controllers'"},
                "max_depth": {"type": "integer", "description": "How many directory levels deep to recurse"},
            },
        },
    },
    {
        "name": "read_file",
        "description": "Read a text file from the repo, returned with line numbers.",
        "input_schema": {
            "type": "object",
            "properties": {"rel_path": {"type": "string"}},
            "required": ["rel_path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a text file in the repo with the given full content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "rel_path": {"type": "string"},
                "content": {"type": "string", "description": "The FULL new content of the file"},
            },
            "required": ["rel_path", "content"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a whitelisted shell command in the repo root (node, npm, git, ls, cat). Use this to sanity-check syntax, e.g. 'node --check server.js'.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
]


def _dispatch(tools: RepoTools, name: str, inp: dict) -> ToolResult:
    if name == "list_files":
        return tools.list_files(inp.get("rel_path", "."), inp.get("max_depth", 4))
    if name == "read_file":
        return tools.read_file(inp["rel_path"])
    if name == "write_file":
        return tools.write_file(inp["rel_path"], inp["content"])
    if name == "run_command":
        return tools.run_command(inp["command"])
    return ToolResult(False, f"Unknown tool: {name}")


def run_agentic_turn(
    tools: RepoTools,
    system_prompt: str,
    user_message: str,
    allowed_tools: set[str],
    max_turns: int = 12,
    on_event: Callable[[str, str], None] | None = None,
) -> str:
    """
    Runs a tool-use conversation until the model returns a final text-only
    reply (no more tool calls) or max_turns is hit. Returns the model's
    final text answer.

    `on_event(kind, detail)` is an optional callback used to print a live
    trace of what the agent is doing (see agent.py's CLI logger).
    """
    client = anthropic.Anthropic()
    schemas = [t for t in TOOL_SCHEMAS if t["name"] in allowed_tools]
    messages = [{"role": "user", "content": user_message}]

    for _ in range(max_turns):
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=schemas,
            messages=messages,
        )

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b.text for b in response.content if b.type == "text"]

        if on_event and text_blocks:
            on_event("thought", "\n".join(text_blocks))

        if not tool_uses:
            return "\n".join(text_blocks).strip()

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for call in tool_uses:
            if on_event:
                on_event("tool_call", f"{call.name}({call.input})")
            result = _dispatch(tools, call.name, call.input)
            if on_event:
                preview = result.output[:300] + ("..." if len(result.output) > 300 else "")
                on_event("tool_result", preview)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": result.output,
                    "is_error": not result.ok,
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return "(Agent hit max_turns without producing a final answer.)"
