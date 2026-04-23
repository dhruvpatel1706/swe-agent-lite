# swe-agent-lite

**A SWE-bench-style agent benchmark for Claude.** Eight hand-curated bug-fix tasks. Five tools (`read_file`, `list_dir`, `edit_file`, `run_tests`, `finish`). Sandboxed per-task workspace. Scored by whether pytest passes after the agent stops.

Unlike the big benchmarks, every task here takes ~30 seconds to run and has a known-good human fix so you can verify the scorer is honest. The point isn't absolute pass rate — it's failure-mode legibility. When the agent fails a task, `swe-agent-lite` tells you *how* (never ran tests, ran tests but didn't edit, edit didn't verify, infinite loop, etc.), which is the information you actually need to tune the agent.

```
$ swe-agent-lite tasks
                                  Tasks
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ id                  ┃ title                                        ┃ difficulty ┃ tags                     ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 01-off-by-one       │ sum_first_n returns the wrong sum            │ easy       │ off-by-one, range        │
│ 02-empty-list       │ average crashes on empty input               │ easy       │ edge-case, div-by-zero   │
│ 03-wrong-comparison │ is_adult returns True for age 17             │ easy       │ wrong-operator           │
│ 04-dict-typo        │ get_user_name always returns None            │ easy       │ typo                     │
│ 05-mutable-default  │ add_item leaks state between calls           │ medium     │ mutable-default          │
│ 06-silent-swallow   │ parse_int returns 0 for invalid strings      │ easy       │ silent-error             │
│ 07-missing-filter   │ filter_long returns everything               │ medium     │ missing-condition        │
│ 08-recursion-base   │ factorial overflows the call stack           │ medium     │ missing-base-case        │
└─────────────────────┴──────────────────────────────────────────────┴────────────┴──────────────────────────┘

$ swe-agent-lite run

01-off-by-one — sum_first_n returns the wrong sum
  → list_dir('.')
  → read_file('repo/solution.py')
  → run_tests → pytest FAILED (exit 1)
  → edit_file('repo/solution.py')
  → run_tests → pytest PASSED
  → finish('fixed off-by-one...')
  pass in 6 iters, 8.2s

02-empty-list — average crashes on empty input
  → ...
  pass in 5 iters, 6.9s

...

                         Run 20260423T213000Z
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ task                ┃ status ┃ iters ┃ time  ┃ failure modes     ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ 01-off-by-one       │ pass   │     6 │  8.2s │                   │
│ 02-empty-list       │ pass   │     5 │  6.9s │                   │
│ 03-wrong-comparison │ pass   │     4 │  5.2s │                   │
│ 04-dict-typo        │ pass   │     5 │  7.1s │                   │
│ 05-mutable-default  │ pass   │     7 │ 10.1s │                   │
│ 06-silent-swallow   │ pass   │     5 │  7.8s │                   │
│ 07-missing-filter   │ pass   │     5 │  7.4s │                   │
│ 08-recursion-base   │ fail   │    20 │ 42.1s │ hit_iteration_lim…│
└─────────────────────┴────────┴───────┴───────┴───────────────────┘

7/8 tasks passed (87%)
```

---

## Why this exists

The frontier benchmarks (SWE-bench, HumanEval+, etc.) are valuable but heavyweight. They run against real GitHub issues across hundreds of tasks, each needing Docker per-repo. Great for production research, terrible for "I tweaked the system prompt yesterday — did it help?"

`swe-agent-lite` is deliberately the opposite: **small, curated, fast, legible**. Tasks are bugs every developer has seen (off-by-ones, mutable defaults, typos, missing edge cases). The agent gets the minimum surface area that's plausibly *enough* to solve them (no bash, no git, no network). Every failure gets a tag so you can tell agent-limit failures from edit-never-verified failures.

## Install

```bash
git clone https://github.com/dhruvpatel1706/swe-agent-lite.git
cd swe-agent-lite
pip install -e .
```

Python 3.10+. Set the API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Commands

```bash
swe-agent-lite tasks                    # List the bundled task suite
swe-agent-lite run                      # Run the full suite
swe-agent-lite run 01-off-by-one 03-wrong-comparison   # Run specific tasks
swe-agent-lite run --model claude-sonnet-4-6   # Try a different model
swe-agent-lite run --max-iterations 10         # Tighter tool-use budget
swe-agent-lite list                     # Past runs, newest first
swe-agent-lite show 20260423T213000Z    # Full trajectory dump
```

Artifacts live at `~/.swe-agent-lite/runs/`.

## The agent surface, on purpose

Five tools is the whole surface. If the benchmark is "can the agent fix a bug", giving it `bash` is a confound — now you're also measuring "can the agent compose shell one-liners". The tools we do provide:

- **`read_file(path)`** — read any file in the workspace.
- **`list_dir(path)`** — list a directory. Recommended first call on every task.
- **`edit_file(path, old_string, new_string)`** — exact-string replace. Fails loudly if `old_string` doesn't match exactly or matches multiple places.
- **`run_tests()`** — run pytest on the task's tests with a short timeout.
- **`finish(summary)`** — signal done. The agent *must* have seen `run_tests` pass before calling this or it's an `exit_early` failure.

No `write_file`, no shell, no network. Adding them is on the v0.2 roadmap behind a flag, but v0.1 constrains the surface so failure attribution is clean.

## Failure-mode tags

When a task fails, `swe-agent-lite` categorizes why by inspecting the trajectory:

| tag | what happened |
|---|---|
| `hit_iteration_limit` | Agent never called `finish` and we bailed after N iterations |
| `never_ran_tests` | Agent never invoked `run_tests` — almost always bad |
| `didnt_edit` | Agent finished without editing anything |
| `edit_but_no_retest` | Agent edited but didn't verify with `run_tests` before finishing |
| `tests_were_timing_out` | Agent's own `run_tests` calls kept timing out (infinite loops) |
| `agent_timeout` | Scorer's final pytest call itself timed out |
| `exit_early` | Agent called `finish` but tests are still failing |
| `framework_error:*` | Our own bug — shouldn't happen in steady state |

These are heuristic, not causal. They're meant to make per-task post-mortems faster to scan, not to claim a root cause.

## Safety considerations

The agent reads and writes files via `edit_file`. The `Workspace` object refuses any path outside the per-task sandbox — symlink-escape attempts get caught too. `run_tests` runs `pytest` under a hard subprocess timeout. There's no shell tool, no network, no eval. That said:

- The tasks *are* Python code that gets executed. The curated task set is all benign; if you add your own tasks with untrusted code, run them in a container.
- A malicious spec file could embed arbitrary Python in `solution.py`. We run pytest inside a subprocess with a timeout, but not under seccomp or similar. For serious use, add a container wrapper.

## Reproducing results

Because the cases are hand-curated and small, you can reproduce a run with any model by setting the API key and running the CLI. Pass rates will vary across model versions and time; the artifact format is versioned so old runs stay comparable.

## Limitations

- **Small N (8 tasks).** This is a smoke test, not a benchmark with tight confidence intervals. A ±1 task difference is noise.
- **Easy tasks by design.** These are bugs you could fix yourself in 30 seconds. They measure "can the agent execute the read-edit-verify loop reliably", not "can the agent reason about complex code". Both matter; this one is cheaper to measure.
- **Static tasks, future leak risk.** Once a task's canonical fix ends up in pre-training, the benchmark gets easier for future model versions. That's fine for a public portfolio piece; serious use would rotate in fresh tasks.
- **Python only.** Every task is a Python file with a pytest suite. Other languages would need a pluggable runner.

## Roadmap

- **v0.2** — more tasks (target: 20), including a couple that span multiple files.
- **v0.2** — optional `write_file` tool behind a `--allow-new-files` flag.
- **v0.3** — aggregate drift report across runs (tag-level pass-rate trends).
- **v0.3** — per-task token/cost reporting.

## License

MIT.
