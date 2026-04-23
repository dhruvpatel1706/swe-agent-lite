"""The agent loop.

Claude tool-use with a hard iteration cap. Each turn:
  1. Send messages + tools to the Messages API.
  2. If the response has `tool_use` blocks, execute each, collect
     `tool_result` blocks, and append to the conversation.
  3. If the response is `end_turn` with no tool use, or the agent called
     `finish`, or we hit the iteration cap, stop.
"""

from __future__ import annotations

from typing import Callable

import anthropic

from swe_agent_lite.models import ToolCall, Trajectory
from swe_agent_lite.tools import TOOLS, Workspace, dispatch

SYSTEM_PROMPT = """You are a focused software engineer fixing one small bug.

You work in a sandboxed workspace with five tools: read_file, list_dir,
edit_file, run_tests, and finish. You cannot run arbitrary shell, access
the network, or write files outside the workspace.

How to approach a task:
  1. First call list_dir('.') to see the layout. Then list_dir on the
     repo and tests directories.
  2. Read the source file(s) AND the test file(s) — the tests tell you
     what behavior is expected.
  3. Run the tests first, without editing, so you see the actual failure.
  4. Make the smallest edit that fixes the test. Prefer one-line fixes.
  5. Run the tests again. If green, call finish. If red, iterate.

Do not over-engineer. Do not add new features. Do not refactor. Do not
write documentation. You are scored on whether the tests pass after you
finish — nothing else."""


def _find_tool_uses(content: list) -> list[tuple[str, str, dict]]:
    """Extract tool_use blocks. Returns [(tool_use_id, name, input), ...]."""
    out = []
    for block in content:
        if getattr(block, "type", None) == "tool_use":
            out.append(
                (
                    getattr(block, "id", ""),
                    getattr(block, "name", ""),
                    getattr(block, "input", {}) or {},
                )
            )
    return out


def _find_text(content: list) -> str:
    """Concatenate every text block — used for trajectory logging."""
    chunks = []
    for block in content:
        if getattr(block, "type", None) == "text":
            chunks.append(getattr(block, "text", ""))
    return "".join(chunks)


def _assistant_blocks_for_history(content: list) -> list:
    """Return the response content blocks suitable for replay as an assistant
    message. The Anthropic SDK returns typed block objects; we convert them
    to plain dicts so they round-trip through the API cleanly.

    Block types we need to preserve:
      - text
      - tool_use
      - thinking (when adaptive thinking is on)

    Anything else is dropped.
    """
    out: list[dict] = []
    for block in content:
        t = getattr(block, "type", None)
        if t == "text":
            out.append({"type": "text", "text": getattr(block, "text", "")})
        elif t == "tool_use":
            out.append(
                {
                    "type": "tool_use",
                    "id": getattr(block, "id", ""),
                    "name": getattr(block, "name", ""),
                    "input": getattr(block, "input", {}) or {},
                }
            )
        elif t == "thinking":
            # Echo thinking back — the API needs the full chain of blocks
            # when tool-use calls are ongoing, or it rejects the next turn
            # with a message-shape error.
            entry = {
                "type": "thinking",
                "thinking": getattr(block, "thinking", ""),
            }
            sig = getattr(block, "signature", None)
            if sig:
                entry["signature"] = sig
            out.append(entry)
    return out


def run_agent(
    task_prompt: str,
    ws: Workspace,
    *,
    client: anthropic.Anthropic,
    model: str,
    max_iterations: int = 20,
    on_tool_call: Callable[[ToolCall], None] | None = None,
) -> Trajectory:
    """Run the tool-use loop until the agent finishes or we hit the cap."""
    messages: list[dict] = [{"role": "user", "content": task_prompt}]
    tool_calls: list[ToolCall] = []
    assistant_text: list[str] = []
    finished = False
    hit_limit = False

    for iteration in range(1, max_iterations + 1):
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        text = _find_text(response.content)
        if text:
            assistant_text.append(text)

        uses = _find_tool_uses(response.content)
        stop_reason = getattr(response, "stop_reason", None)

        # Always echo the assistant's complete response back into history,
        # including thinking/tool_use blocks, before we answer with tool_results.
        messages.append(
            {"role": "assistant", "content": _assistant_blocks_for_history(response.content)}
        )

        if not uses:
            # No tool calls this turn. Either the agent is done talking
            # (end_turn) or ran out of tokens. Either way, stop.
            break

        # Build the user turn: one tool_result block per tool_use call.
        tool_result_blocks: list[dict] = []
        for use_id, name, inputs in uses:
            output = dispatch(name, inputs, ws)
            preview = output if len(output) <= 200 else output[:200] + "..."
            tc = ToolCall(name=name, input=inputs, output_preview=preview)
            tool_calls.append(tc)
            if on_tool_call is not None:
                on_tool_call(tc)
            tool_result_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": use_id,
                    "content": output,
                }
            )
            if name == "finish":
                finished = True

        messages.append({"role": "user", "content": tool_result_blocks})

        if finished:
            break

        # stop_reason of "end_turn" without tool_use already broke out above;
        # we only get here if there were tool uses.
        _ = stop_reason  # keep the variable meaningful for future checks

    else:
        hit_limit = True

    return Trajectory(
        task_id="",  # filled in by runner
        iterations=iteration,
        tool_calls=tool_calls,
        assistant_text=assistant_text,
        finished_cleanly=finished,
        hit_iteration_limit=hit_limit,
    )


def task_prompt(task, ws: Workspace) -> str:  # type: ignore[no-untyped-def]
    """Compose the initial user prompt describing a task to the agent."""
    rel_repo = ws.repo_dir.relative_to(ws.root)
    rel_tests = ws.tests_dir.relative_to(ws.root)
    return (
        f"# Task: {task.title}\n\n"
        f"{task.problem}\n\n"
        f"Workspace layout:\n"
        f"  - Source code is in `{rel_repo}/`.\n"
        f"  - Failing tests are in `{rel_tests}/`.\n"
        f"  - Your fix succeeds when `pytest {rel_tests}` passes.\n\n"
        "Use the tools to inspect the code, make the fix, and verify with "
        "run_tests. Call `finish` once tests pass."
    )
