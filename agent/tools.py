"""
tools.py
--------
Sandboxed tool implementations the agent (LLM) is allowed to call.

Every tool that touches the filesystem is scoped to `repo_root` and refuses
to read/write outside it (basic path-traversal protection). This module has
no LLM-specific code in it on purpose: it's the "hands" of the agent, kept
separate from the "brain" (llm.py) so it can be unit tested or reused with a
different model/provider.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".DS_Store", "dist", "build"}
MAX_FILE_BYTES = 200_000  # guard against accidentally dumping huge/binary files into the LLM context


@dataclass
class ToolResult:
    ok: bool
    output: str


class RepoTools:
    """Filesystem + shell tools, all confined to `repo_root`."""

    def __init__(self, repo_root: str):
        self.root = Path(repo_root).resolve()
        if not self.root.exists():
            raise FileNotFoundError(f"repo_root does not exist: {self.root}")

    # ---- safety -----------------------------------------------------
    def _resolve(self, rel_path: str) -> Path:
        candidate = (self.root / rel_path).resolve()
        if not str(candidate).startswith(str(self.root)):
            raise PermissionError(f"Path escapes repo root: {rel_path}")
        return candidate

    # ---- read-only tools ---------------------------------------------
    def list_files(self, rel_path: str = ".", max_depth: int = 4) -> ToolResult:
        """Recursively list files/directories under rel_path, up to max_depth."""
        start = self._resolve(rel_path)
        if not start.exists():
            return ToolResult(False, f"Path not found: {rel_path}")

        lines = []
        base_depth = len(start.parts)
        for dirpath, dirnames, filenames in os.walk(start):
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
            depth = len(Path(dirpath).parts) - base_depth
            if depth > max_depth:
                dirnames[:] = []
                continue
            rel_dir = Path(dirpath).relative_to(self.root)
            for f in sorted(filenames):
                lines.append(str(rel_dir / f))
        return ToolResult(True, "\n".join(sorted(lines)) or "(empty)")

    def read_file(self, rel_path: str) -> ToolResult:
        path = self._resolve(rel_path)
        if not path.exists() or not path.is_file():
            return ToolResult(False, f"File not found: {rel_path}")
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            return ToolResult(False, f"File too large to read ({size} bytes): {rel_path}")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ToolResult(False, f"File is not text-decodable (binary?): {rel_path}")
        numbered = "\n".join(f"{i+1:>5}\t{line}" for i, line in enumerate(text.splitlines()))
        return ToolResult(True, numbered or "(empty file)")

    # ---- write tools ---------------------------------------------------
    def write_file(self, rel_path: str, content: str) -> ToolResult:
        path = self._resolve(rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        existed = path.exists()
        path.write_text(content, encoding="utf-8")
        return ToolResult(True, f"{'Updated' if existed else 'Created'} {rel_path} ({len(content)} bytes)")

    # ---- shell (heavily restricted, read-mostly verification) ----------
    ALLOWED_COMMANDS = {"node", "npm", "git", "ls", "cat"}

    def run_command(self, command: str, timeout: int = 30) -> ToolResult:
        program = command.strip().split()[0] if command.strip() else ""
        if program not in self.ALLOWED_COMMANDS:
            return ToolResult(False, f"Command '{program}' is not on the allow-list {sorted(self.ALLOWED_COMMANDS)}")
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
            return ToolResult(proc.returncode == 0, out.strip()[:4000] or "(no output)")
        except subprocess.TimeoutExpired:
            return ToolResult(False, "Command timed out")
