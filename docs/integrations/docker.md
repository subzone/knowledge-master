# Docker Integration

Run Knowledge Master without installing Python.

## Docker image

```bash
# Run the MCP server
docker run --network host ghcr.io/subzone/knowledge-master:latest km-server

# Run the web UI
docker run --network host ghcr.io/subzone/knowledge-master:latest km serve
```

## Full stack with Docker Compose

```yaml
services:
  falkordb:
    image: falkordb/falkordb:v4.4.1
    ports: ["6379:6379"]
    volumes: [falkor_data:/data]

  knowledge-master:
    image: ghcr.io/subzone/knowledge-master:latest
    ports: ["9999:9999"]
    depends_on: [falkordb]
    command: km serve --port 9999

volumes:
  falkor_data:
```

## CI/CD Integration

Index your repo after every push:

```yaml
# GitHub Actions
- name: Update knowledge base
  run: |
    pip install knowledge-master
    km index . --type repo
```
