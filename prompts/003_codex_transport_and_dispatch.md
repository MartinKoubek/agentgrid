# 003 — Fix Codex transport and dispatch reliability

You are implementing this task in the AgentGrid repository. Read `AGENTS.md` and inspect the current branch and relevant tests before changing code. Review baseline: commit `4fc3d7deb6d4d9c85d499625352fdfde97e5637a` (`Validate Codex integration failure handling`); **work on the latest branch HEAD, do not reset to this commit**. Keep the existing provider-neutral architecture and fake-agent deterministic test coverage.

## Priority and scope

1. Restore green CI by fixing the actual multiline tmux paste transport bug.
2. Make project association and both initial/continuation prompt failures observable without falsely reporting success or automatically duplicating an ambiguously submitted prompt.
3. Validate the real Codex CLI locally if credentials/network/quota allow, and report honestly what was verified.

Do **not** implement structured worker-state detection, automatic approvals, a Master Codex, or a general orchestrator rewrite in this task. Quiet terminal output is not proof of completion or readiness for another task.

## 1. Fix the actual tmux multiline transport bug

The GitHub Actions run for `4fc3d7de` is red: https://github.com/MartinKoubek/agentgrid/actions/runs/35078657418 . `agentgrid-tmux/tests/e2e/test_tmux_roundtrip.py::test_tmux_paste_text_delivers_multiline_prompt_as_one_terminal_paste` now launches the recorder, but it captures only:

```python
b'\x1b[200~First paragraph with caf\xc3\xa9.\r'
```

The recorder stops at the first carriage return instead of receiving the complete multiline UTF-8 prompt and bracketed-paste close marker. Inspect `agentgrid-tmux/tmuxio/writer.py::paste_text()` and the tmux version/manual. `paste-buffer` defaults to converting line feeds to carriage returns unless `-r` is set. Add `-r` to the **generic tmux transport** (not the Codex adapter or test), preserving the existing `-p` bracketed mode, `-d` deletion behavior, uniquely named buffer, and `finally` cleanup. Verify the actual tmux semantics instead of relying only on the presumed flag behavior.

Keep strict byte-level E2E checks: exact UTF-8 payload delivered once, internal LF and blank lines preserved, shell metacharacters not executed, bracketed paste start/end when the receiver enabled it, and one separate submit Enter. Improve the raw recorder if needed so that it reads **through the closing bracketed-paste marker** before treating a subsequent `\r` as submission; do not simply weaken the assertions or replace the E2E with a mock. Update unit-test expectations for `paste-buffer` arguments and maintain buffer/temp-file cleanup tests, including failure paths. Run the focused test repeatedly, then `./bin/test-all`.

## 2. Do not report an unassociated worker as successfully dispatched

Inspect `agentgrid-orchestrator/agentgrid_orchestrator/orchestrator.py`, project persistence, `AgentManager`, and current tests. `_attach_agent()` returns a string on project lookup failure; successful `START_AGENT` can still send work and return success with `project_association_error`. `project_manager.save()` can also raise after the worker was created.

Design the smallest provider-independent correction:

- Validate that the target project exists (and its cwd is available where required) **before** starting a project-scoped worker. Do not silently fall back to the caller's cwd for a missing project.
- After agent allocation, persist the agent ID, project ownership, and initial task **before** sending. If association cannot be persisted, do not dispatch the prompt or return successful `START_AGENT`; return a structured, inspectable failure with project ID, agent ID if allocated, and the underlying cause.
- Handle any already-started but unassociated worker explicitly: attempt bounded best-effort cleanup, check actual liveness, preserve the agent registry record and cleanup diagnostics, and never claim it was stopped if still alive. If cleanup fails, expose the orphan/reconciliation risk instead of swallowing it.
- Preserve the current `AGENT_START_FAILED` and `AGENT_SEND_FAILED` semantics, the existing project history model, and normal fake-agent flows. Do not auto-retry uncertain submissions.

Test missing-project preflight (no worker started), project-save failure after allocation (no send, inspectable identity and cleanup), successful project association, startup failure, and cleanup failure/worker still alive. Avoid tests that merely assert a string error while a worker remains silently active.

## 3. Handle CONTINUE_AGENT submission failures symmetrically

Currently the `CONTINUE_AGENT` branch calls `agent_manager.send()` without a structured failure path. A tmux/send error might occur **after** bytes were delivered, so blindly repeating the request can duplicate work.

- Return a provider-neutral `AGENT_SEND_FAILED` (or equivalent existing explicit failure action) with project ID, agent ID, request, error, and an indication that delivery may be uncertain. Do not leak an unstructured exception for expected send-path failures.
- Preserve project/agent association and an inspectable record of the **attempted** task, without presenting it as a confirmed completion or guaranteed successful delivery. Use the simplest existing persistence mechanism, and do not overwrite previous task context or add duplicate task text on retries.
- Do not mark a worker `STOPPED`/`FAILED` merely because the send operation failed if its actual lifecycle state is unknown; retain state and actionable diagnostics. No automatic retry or second send.
- Check `agentgrid-dispatcher` mapping: these explicit failures must PARK for user/operator attention, not ACK. Preserve existing AGENT_FAILED -> PARK behavior and successful continuation behavior.

Add deterministic regression tests for successful CONTINUE_AGENT, send exceptions before/after possible delivery, unchanged agent identity/project ownership, and failure mapping. If persistence needs a field, keep it generic and migration-safe rather than Codex-specific.

## 4. Validate the real Codex path, without fabricating success

Inspect `which codex`, `codex --version`, and available CLI help. If this local environment has an authenticated Codex CLI, network access, and quota, run the existing opt-in integration test and verify two **actual responses** in the same worker plus a multiline prompt and shutdown:

```sh
AGENTGRID_TEST_REAL_CODEX=1 python3.11 -m pytest agentgrid-agent/tests/e2e/test_codex_adapter_runtime.py -q -s
```

If unavailable, state `real Codex: NOT RUN` with the reason and exact version if known. Never write credentials or mark a test passed based on echoed prompts. Standard CI must stay deterministic and credential-free. Do not assume terminal quiescence proves a Codex turn is finished; defer an explicit state/protocol solution to the next milestone.

## Validation, commit, and push — mandatory

Run focused tests and `./bin/test-all` to completion. Fix any deterministic failures; do not skip, xfail, or weaken failing tests. Inspect `git status` and commit **only task-related changes** with a descriptive message. **Push the implementation commit(s) to the intended remote branch**; do not stop at a local commit. If the branch is protected, do not force-push: push an appropriate feature branch and report its URL/PR status. Verify the GitHub Actions run for the pushed implementation SHA and report its actual status; if CI is still running or failed, state that precisely and include the run URL. If push is blocked by authentication/permissions, explicitly report the failure rather than claiming success.

Finish with: root cause and fix of the LF/CR issue; files changed; tests and results; real Codex PASS/FAIL/NOT RUN; any unresolved association/delivery uncertainty; implementation commit SHA, branch, push result, and CI run/status. The task is complete only when the strict paste E2E and full deterministic suite pass and the changes have been committed **and pushed**. Next separate milestone: structured Codex worker-state/protocol detection.
