"""Run a repo's .claude/agents/leakage-auditor.md prompt headless via the Agent SDK.

usage: python agent/run_leakage_auditor.py <repo> <base_commit> <model> <out.txt> <venv_scripts_dir>

Used for docs/AUDIT.md Part A:
  python agent/run_leakage_auditor.py ../teammate b183a4e claude-opus-5-5 audit_teammate.txt .venv/Scripts

setting_sources=[] so the audited repo's settings.json (hooks, Ollama env) is
NOT loaded; the auditor gets exactly the subagent's tools: Read, Grep, Glob, Bash.
"""
import asyncio
import os
import sys
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

repo, base, model, out, venv = sys.argv[1:6]
md = (Path(repo) / ".claude/agents/leakage-auditor.md").read_text(encoding="utf-8")
body = md.split("---", 2)[2].strip()  # drop YAML frontmatter

prompt = (
    f"The diff under review is everything since the unmodified starter commit {base}: "
    f"run `git diff {base} HEAD -- src tests` to see it, and read the current files. "
    "Python with the pinned requirements is on PATH as `python`; you may run "
    "`python -m pytest`, `python -m src.<module>` and git read commands to verify claims."
)


async def main():
    env = {"PATH": venv + os.pathsep + os.environ.get("PATH", "")}
    opts = ClaudeAgentOptions(
        system_prompt=body,
        cwd=repo,
        setting_sources=[],
        allowed_tools=["Read", "Grep", "Glob", "Bash"],
        disallowed_tools=["Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch"],
        model=model,
        max_turns=60,
        env=env,
    )
    final = None
    async for m in query(prompt=prompt, options=opts):
        if isinstance(m, ResultMessage):
            final = m
    text = (final.result or "") if final else "(no result)"
    meta = f"model={model} turns={getattr(final, 'num_turns', '?')} is_error={getattr(final, 'is_error', '?')}"
    Path(out).write_text(meta + "\n\n" + text, encoding="utf-8")
    print(meta)


asyncio.run(main())
