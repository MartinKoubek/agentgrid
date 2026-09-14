# Execution / Test Manager

## Responsibility

Runs project-specific build, deploy, validation, and end-to-end workflows.

The core service is generic. Platform-specific behavior belongs to adapters.

## Possible adapters

```text
Android / ADB / Emulator
Web / Playwright
SSH
Docker
REST API
Desktop UI
```

## Android example

```text
build
  -> start/reuse emulator
  -> deploy APK
  -> launch app
  -> interact with UI
  -> inspect expected values
  -> collect logcat
  -> determine result
```

A project agent can use the result to modify the implementation and repeat the workflow until the scenario passes or requires escalation.
