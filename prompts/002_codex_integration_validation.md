# 002 — Validate Codex integration and failed-start handling

You are the AgentGrid implementation agent. Execute this prompt against the **current branch**. Read `AGENTS.md` and inspect the existing code and tests first. The review baseline is commit `3ba5caac03a0a11a81ce6a88541a74db599cd2db` (`Harden Codex adapter reliability`), not a request to reset to that revision. Keep all changes focused and preserve provider-neutral architecture.

## Goal and priority

1. Fix the currently failing **real tmux paste E2E** test and restore green CI.
2. Exercise the actual interactive Codex adapter locally when credentials and the CLI are available; report what was and was not verified.
3. Make a failed agent startup observable, project-owned, and non-orphaned from the Orchestrator entry point.

**Do not** implement semantic Codex completion, automatic approval, Master Codex, or a new agent protocol in this task. An idle/quiet terminal is not proof that Codex has finished a turn.

## 1. Fix the failing tmux paste test — do not weaken it

The GitHub Actions run for commit `3ba5caac` failed in `agentgrid-tmux/tests/e2e/test_tmux_roundtrip.py::test_tmux_paste_text_delivers_multiline_prompt_as_one_terminal_paste`: after launching the recorder, `capture-pane` found no running tmux server before `RECORDER_READY` was seen. CI: https://github.com/MartinKoubek/agentgrid/actions/runs/35074976672 .

Inspect the generated recorder script, its stderr/exit status, and the test's tmux lifecycle. In particular, check whether Python escape sequences in the enclosing triple-quoted test string (e.g. `b"\r"`) become an unintended literal carriage return in the generated `.py` source. Use a raw outer string or escape backslashes appropriately, and add an early source/launch diagnostic where useful. Do **not** assume this is the only failure; rerun the test after fixing the launch problem and diagnose any subsequent mismatch independently.

The recorder is a raw terminal consumer. If the test asserts `ESC[200~` / `ESC[201~`, explicitly enable bracketed-paste mode (`ESC[?2004h`) in the recorder before advertising `RECORDER_READY`, and disable it during cleanup. Verify the actual behavior of the installed tmux version; do not assert framing sequences unless the receiving application requested bracketed paste. Preserve the key acceptance criteria:

- one UTF-8 multiline prompt, including blank lines and shell metacharacters, is delivered verbatim and exactly once;
- the payload is not executed by a shell;
- exactly one deliberate submit Enter follows the paste;
- temporary file and tmux buffer cleanup still work, including on failure;
- test failures remain failures, not `pytest.skip()` or broad exception swallowing.

Keep an isolated tmux socket, bounded waits, and reliable cleanup. Run the focused test several times if feasible, then `./bin/test-all`.

## 2. Validate the real Codex CLI, honestly

Inspect the installed CLI and its documented flags (`which codex`, `codex --version`, `codex --help`) before relying on flags or UI assumptions. Run the existing opt-in test locally **only if** the environment has the CLI, authenticated access, network, and available quota:

```sh
AGENTGRID_TEST_REAL_CODEX=1 python3.11 -m pytest agentgrid-agent/tests/e2e/test_codex_adapter_runtime.py -q -s
```

Verify actual observations: a worker becomes ready, receives the first prompt, produces a response-only marker not present in the submitted prompt, receives a second related prompt in the *same logical session* (same pane/runtime/endpoint identity), produces the second response, and stops. Add an actual multiline prompt to the smoke scenario or a separate opt-in check to validate the bracketed-paste path against Codex itself. Make sure the markers cannot be satisfied by echoed input or stale terminal history. Avoid relying on `capture-pane` history offsets as if they were a durable append-only log; account for TUI redraws where necessary.

If access or authentication is unavailable, do not fake success, provision credentials, or put secrets into files. Keep normal CI deterministic and the real-Codex test explicitly opt-in. In your final report distinguish `tested against real Codex: PASS / FAIL / NOT RUN`, the exact CLI version if available, and the reason for NOT RUN. Do not make a claim of a working real-Codex E2E based only on fake tests.

## 3. Handle startup failure at the Orchestrator boundary

Current path: `AgentManager._start()` can return an `Agent` with `state=FAILED` and an error. `Orchestrator.handle_request()` on `START_AGENT` immediately calls `agent_manager.send()` and only then `_attach_agent()`. The ensuing exception can discard a useful decision, leave the failed agent out of project ownership/history, and make the startup failure hard to inspect.

Implement a **small provider-independent** fix:

- Record project association and initial task for an allocated agent before sending the first task, including when startup failed. Do not invent ownership when the project does not exist; preserve a clear diagnostic.
- Check the returned agent state after `start()`; if startup failed, do not call `send()`. Return a structured, inspectable failure decision (or use the repository's existing failure representation) carrying project ID, agent ID and the startup error. Do not misreport `START_AGENT` success.
- If the first `send()` fails, retain project ownership and agent identity, preserve the cause, and return/report an explicit failure instead of silently leaving an unassociated process. Avoid treating an ambiguous submission as safe to retry automatically; duplicate prompt delivery is possible.
- Review best-effort cleanup after failed startup. A `stop()` request is not proof the worker exited: check liveness after cleanup and retain an explicit diagnostic when the worker is still running. Do not globally convert every exception to `STOPPED`.
- Preserve normal `START_AGENT`, `CONTINUE_AGENT`, `AGENT_FAILED -> PARK`, deterministic fake-agent behavior, and existing state persistence. Keep Codex-specific UI handling inside the adapter.

Add deterministic regression tests for: `start()` returning `FAILED` (no send; project association and error accessible); first `send()` raising (no lost agent ID/project ownership, no silent success); cleanup failing or leaving a live process (observable error); successful start and continuation unchanged. Where appropriate, ensure that a subsequent router decision does not continue a `FAILED` worker.

## 4. Validate and report

Run focused unit/E2E tests and **`./bin/test-all`**; verify the new pushed commit's GitHub Actions run if you have access. Do not claim CI green until the run for your commit actually succeeds. Update only the relevant documentation to reflect verified capabilities and limitations.

Finish with a concise report: files changed, root cause of the recorder failure, exact tests/results, real-Codex test status, remaining risks, and commit SHA if committed.

**Definition of done:** the tmux paste E2E passes without weakened assertions; full deterministic tests pass; failed startup is a visible project-owned failure with no unchecked orphan; and actual Codex integration is either demonstrated or explicitly marked unverified. The next milestone, *after this*, is structured worker-state detection rather than adding more TUI quiescence heuristics.
