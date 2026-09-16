# 001 — Make the Codex adapter reliable

You are implementing the task described in this file in the AgentGrid repository. Read `AGENTS.md` and inspect the current implementation before making changes. The baseline is the Codex adapter MVP introduced in commit `9ad24e5c501d72aa9878438f30d60d1e121b98d1`; work from the current branch, not a detached historical revision.

## Objective

Make the existing Codex worker usable with a real interactive Codex CLI. Fix four concrete review findings: startup/readiness, atomic multiline prompt submission, shutdown races, and a meaningful optional real-Codex smoke test. Keep provider-specific UI/protocol details in `CodexAgentAdapter` and generic terminal transport in `agentgrid-tmux`. Do not redesign AgentGrid or implement semantic task completion/approval automation.

## 1. Startup readiness and error reporting

Inspect `agentgrid-agent/agentgrid_agent/adapters/codex.py`, `agentgrid_agent/manager.py`, the `AgentAdapter` contract, and tmux's `PaneEndpoint`. Currently `CodexAgentAdapter.start()` is a no-op and `AgentManager._start()` marks the agent RUNNING immediately; `Orchestrator.handle_request()` can send the first task while Codex is initializing, displaying a login prompt, or failing to start.

Implement a bounded, testable readiness gate before the first prompt. Distinguish **process alive** from **Codex ready to accept a task**. Use a supported signal/interaction verified against the installed Codex CLI, not a guessed flag, arbitrary sleep, or an untested screenshot substring. If the CLI does not expose a stable machine-readable readiness protocol, document and implement the most conservative verifiable MVP approach, with a clear timeout/failure instead of silently submitting into an unknown UI state. Authentication/startup failures must be visible and must not be reported as a successfully initialized worker. Preserve provider neutrality in the manager: only generic readiness/start failure state may cross the adapter boundary. Check that failed startup does not silently orphan a live pane or wrongly attach a project agent.

Do not introduce a full task-completion parser as part of this change. For a second prompt, do not blindly type over an in-progress Codex interaction: either establish a reliable input-ready condition or fail clearly/document the limitation until the protocol milestone.

## 2. Reliable multiline prompt transport

`CodexAgentAdapter.send()` currently calls `tmux.send_text(pane_id, text)` then `tmux.send_key(pane_id, "ENTER")`; `tmuxio.writer.send_text()` delegates to `tmux send-keys -l`. This does not establish that embedded newlines are delivered as **one pasted prompt** to an interactive TUI.

Add a **provider-independent** paste operation to `agentgrid-tmux`, selecting and verifying a tmux-version-supported bracketed-paste mechanism (e.g. tmux buffer/paste-buffer with bracketed paste when supported). Keep tmux commands exclusively in `tmuxio`; Codex adapter must call only the public tmux abstraction. Handle Unicode, multiline content, shell metacharacters, and large prompts without shell evaluation or accidental repeated Enter. Do not leave prompt contents in a persistent/shared tmux buffer: use a unique buffer and clean it up even on failure. Avoid accidentally logging sensitive prompt contents. Codex adapter should paste the entire prompt and submit **exactly once**, according to the verified Codex CLI behavior.

Add focused tmux transport tests using a deterministic local terminal/PTY consumer that records the actual received input and submissions. A mock asserting `send_text()` received a multiline Python string is not sufficient. Test at least two paragraphs with embedded newlines, Unicode, and shell metacharacters. Preserve the old `send_text` / `send_key` APIs for current callers.

## 3. Race-safe stop

Current `CodexAgentAdapter.stop()` unconditionally sends `C-c` followed by `C-d` when initially alive. If the first key terminates the worker and the pane disappears, the second key can raise `TmuxCommandError`. Conversely, the keys might leave the process alive and `AgentManager.stop()` may return RUNNING after its bounded wait.

Implement a bounded, idempotent termination sequence. After each shutdown action, re-check the controlled worker's endpoint/runtime identity before sending another key. Normal pane/server disappearance during shutdown should result in STOPPED, not an exception or FAILED. Do not mask unrelated transport/programming errors as successful shutdown. If a worker does not terminate within the deadline, return/report a truthful still-running or explicit stop-failed outcome; do not claim success. Use the existing tmux abstraction for any further signal/termination operation, and do not kill a human-owned pane or an unrelated process. Add deterministic tests for disappearance after `C-c`, an already stopped worker, and a worker that ignores graceful shutdown.

## 4. Make the optional real-Codex smoke test meaningful

In `agentgrid-agent/tests/e2e/test_codex_adapter_runtime.py`, the test sends a prompt **containing** `AGENTGRID_CODEX_SMOKE_READY` and searches captured output for that string, so echoed input alone can satisfy it. Replace this with response-only markers **not present verbatim in the input**, and ensure they appear in output produced after submission. Verify two related requests in the same logical Codex worker/session and inspect the worker identity between requests. Test startup, first reply, continuation, read, and stop. Timeouts should show useful output diagnostics. The real test remains opt-in via `AGENTGRID_TEST_REAL_CODEX=1` and must not make ordinary CI depend on Codex credentials, network access, or model output. If the opt-in test cannot be run here, explicitly report it as **not verified**; do not claim CI proves real-Codex behavior.

## Constraints and acceptance criteria

- Inspect actual locally installed `codex --help` / `codex --version` and tmux capabilities before relying on flags or UI behavior. If unavailable, document what could not be verified and rely on deterministic tests rather than inventing behavior.
- Keep fake-agent tests and provider-substitution vertical slice intact. Do not introduce Codex-specific branches into Router, Orchestrator, Monitor, Dispatcher, or Event Queue.
- Add regression tests for readiness timeout/login/error, multiline *actual terminal delivery*, stop race, and smoke-test false positives. Do not silence errors or turn real failures into `pytest.skip()`; only the explicitly opt-in real service test may be skipped when prerequisites are unavailable.
- Run focused tests first, then `./bin/test-all`. Report the exact tests run and their results; do not claim GitHub Actions is green unless the new commit's check has actually completed successfully.
- Update the adapter's README with verified behavior and remaining limitations, without describing this MVP as an autonomous Codex Master.

**Done means:** startup does not send into an unready CLI, a multiline prompt is delivered and submitted as one request, shutdown survives pane disappearance without a false success, and the opt-in smoke test cannot pass on echoed input alone and exercises a second turn in the same worker. Keep the implementation minimal and coherent.
