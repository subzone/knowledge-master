# GitHub Copilot Integration

Use Knowledge Master with GitHub Copilot's agent mode (VS Code).

## Setup

Add to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "knowledge-master": {
      "command": "km-server"
    }
  }
}
```

Or globally at `~/.vscode/mcp.json`.

## Usage in Copilot Chat

In VS Code, open Copilot Chat (Ctrl+Shift+I) and switch to Agent mode (@workspace). The tools appear automatically:

```
@workspace /knowledge-master search "how does the auth middleware work?"

@workspace /knowledge-master safe_to_change "auth/service.py"

@workspace /knowledge-master blast_radius "postgres"

@workspace /knowledge-master who_owns "src/api/routes.py"
```

## Example workflows

### Before refactoring
```
Me: Is it safe to change the database connection module?

Copilot: [calls safe_to_change("db/connection.py")]
Risk: RISKY — 12 files import this module, 3 test files cover it.
Affected: api.py, auth.py, users.py, orders.py...
Recommendation: Update tests first, then refactor incrementally.
```

### Understanding a new codebase
```
Me: What technologies does this project use and who owns the auth service?

Copilot: [calls get_status(), then who_owns("auth/")]
This project uses Python, FastAPI, PostgreSQL, Docker, Terraform.
Auth service is owned by Alex (85% of recent changes).
```

### Before a PR review
```
Me: What's the blast radius of the changes in this PR?

Copilot: [calls blast_radius for each changed file]
Direct impact: 5 files
Service impact: auth-service, user-service
People to notify: Alex, Maria
```
