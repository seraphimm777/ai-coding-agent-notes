"""
test_dry_run.py
----------------
Sanity-checks the tool loop WITHOUT a real Anthropic API key by monkeypatching
anthropic.Anthropic().messages.create with a scripted fake model that:
  1. calls list_files
  2. calls read_file on server.js
  3. calls write_file to create a new file
  4. returns a final text-only answer

This exists purely to prove the plumbing (tool dispatch, path safety,
message threading, loop termination) is correct before you run the real
thing with a live API key. It is NOT part of the shipped agent.
"""
import types
import anthropic

from tools import RepoTools
from llm import run_agentic_turn


class FakeBlock:
    def __init__(self, type_, **kw):
        self.type = type_
        for k, v in kw.items():
            setattr(self, k, v)


class FakeResponse:
    def __init__(self, content):
        self.content = content


SCRIPT = [
    FakeResponse([FakeBlock("text", text="Let me look around."),
                  FakeBlock("tool_use", id="1", name="list_files", input={"rel_path": "."})]),
    FakeResponse([FakeBlock("tool_use", id="2", name="read_file", input={"rel_path": "server.js"})]),
    FakeResponse([FakeBlock("tool_use", id="3", name="write_file",
                             input={"rel_path": "DRYRUN_TEST.txt", "content": "hello from dry run"})]),
    FakeResponse([FakeBlock("text", text="Repository Summary: fake summary. Done.")]),
]


class FakeMessages:
    def __init__(self):
        self.calls = iter(SCRIPT)

    def create(self, **kwargs):
        return next(self.calls)


class FakeClient:
    def __init__(self, *a, **kw):
        self.messages = FakeMessages()


def main():
    anthropic.Anthropic = FakeClient  # monkeypatch
    tools = RepoTools("/home/claude/build/app-repo")

    events = []
    def on_event(kind, detail):
        events.append((kind, detail))
        print(f"[{kind}] {detail[:80]}")

    result = run_agentic_turn(
        tools=tools,
        system_prompt="irrelevant for dry run",
        user_message="irrelevant for dry run",
        allowed_tools={"list_files", "read_file", "write_file", "run_command"},
        max_turns=10,
        on_event=on_event,
    )

    print("\nFinal result:", result)
    assert "Repository Summary" in result, "loop did not return final text"
    assert any(k == "tool_call" and "list_files" in d for k, d in events)
    assert any(k == "tool_call" and "read_file" in d for k, d in events)
    assert any(k == "tool_call" and "write_file" in d for k, d in events)

    written = tools.root / "DRYRUN_TEST.txt"
    assert written.exists() and written.read_text() == "hello from dry run"
    written.unlink()  # cleanup

    print("\nDRY RUN OK: tool loop, dispatch, and path-scoped file I/O all work.")


if __name__ == "__main__":
    main()
