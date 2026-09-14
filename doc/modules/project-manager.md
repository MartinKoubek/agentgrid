# Project Manager

## Responsibility

Owns project identity and project/workspace metadata.

## Typical information

- project ID and display name
- repository/path
- current branch
- tmux workspace mapping
- active agents
- last activity
- project configuration

## Example operations

```text
open_project("android-app")
get_project("android-app")
list_projects()
close_project("android-app")
get_last_active_project()
```

The Project Manager knows what a project is and where it lives. It does not decide which agent should receive a new request; that is the Context Router's responsibility.
