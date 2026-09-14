# agentgrid-project-manager

`agentgrid-project-manager` owns project identity and workspace metadata.

It tracks project ID, display name, repository path, workspace mapping, historical agent membership, configuration, open or closed state, and last activity. It does not route requests, manage agents, or duplicate runtime liveness state.

`Project.agents` means agents that belong to or were created for the project. Running, stopped, and failed state must come from Agent Manager.

## CLI

```sh
./bin/agentgrid-project-manager --store /tmp/projects.sqlite3 open demo --path . --name Demo --json
./bin/agentgrid-project-manager --store /tmp/projects.sqlite3 list --json
./bin/agentgrid-project-manager --store /tmp/projects.sqlite3 inspect demo --json
./bin/agentgrid-project-manager --store /tmp/projects.sqlite3 add-agent demo ag-001 --json
./bin/agentgrid-project-manager --store /tmp/projects.sqlite3 close demo --json
```

## Python API

```python
from agentgrid_project_manager import ProjectManager

manager = ProjectManager("/tmp/projects.sqlite3")
project = manager.open_project("demo", path=".", name="Demo")
```
