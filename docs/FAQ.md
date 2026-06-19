# FAQ / Troubleshooting

## Installation

### `km: command not found` after install

Your `~/.local/bin` isn't in PATH. Fix:

```bash
export PATH="$HOME/.local/bin:$PATH"
# Add to your shell profile (~/.bashrc or ~/.zshrc) to persist:
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
```

### `No module named typer` or similar import errors

You have a broken install (likely from Homebrew). Fix:

```bash
brew uninstall knowledge-master 2>/dev/null
rm -f /home/linuxbrew/.linuxbrew/bin/km /home/linuxbrew/.linuxbrew/bin/km-server
pipx uninstall knowledge-master
pipx install knowledge-master
```

---

## Starting (`km start`)

### `Error 61 connecting to localhost:6379 — Connection refused`

FalkorDB container isn't running. Common causes:

**1. Docker isn't running:**
```bash
# macOS
colima start  # or open Docker Desktop

# Linux
sudo systemctl start docker
```

**2. Image didn't pull (first-time):**
```bash
docker pull falkordb/falkordb:v4.4.1
km start
```

**3. Port 6379 already in use (another Redis):**
```bash
lsof -i :6379  # check what's using it
# Use a different port:
export KM_FALKORDB_PORT=6380
docker run -d --name km-falkordb -p 127.0.0.1:6380:6379 falkordb/falkordb:v4.4.1
```

**4. Container exists but stopped:**
```bash
docker rm km-falkordb
km start
```

### `Ollama not found`

`km start` will offer to install it automatically. If that fails:

```bash
# macOS
brew install ollama && ollama serve

# Linux
curl -fsSL https://ollama.com/install.sh | sh
ollama serve  # run in background or separate terminal
```

### `km start` succeeds but `km index` fails with connection error

Ollama needs to be running as a server. In a separate terminal:

```bash
ollama serve
```

---

## Indexing

### `skip file.py: the input length exceeds the context length`

Normal — files larger than 8192 tokens are skipped. This affects large generated files, lock files, bundled JS. Your actual source code is rarely this large.

### Indexing is slow

First run is slowest (embedding model loads into memory). Subsequent runs use deduplication — unchanged files are skipped. Expect:
- ~100 files/minute on first index
- Near-instant on re-index (unchanged files skipped via content hash)

---

## MCP / AI Tool Integration

### AI tool doesn't see Knowledge Master tools

1. Run `km setup <tool>` (e.g., `km setup cursor`)
2. **Restart your AI tool** (quit fully and reopen)
3. Verify: `km status` should show green

### `km-server` not found when AI tool launches it

The AI tool can't find the binary. Use `km setup` which writes the full path:

```bash
km setup cursor  # writes absolute path to config
```

Or manually set the full path in your AI tool's MCP config:

```bash
which km-server
# Use that full path in the config
```

---

## Configuration

### How do I change the embedding model?

```bash
export KM_EMBED_MODEL=mxbai-embed-large
ollama pull mxbai-embed-large
```

### How do I change the FalkorDB port?

```bash
export KM_FALKORDB_PORT=6380
```

### Where is my data stored?

In a Docker volume called `km-falkordb-data`. To find it:

```bash
docker volume inspect km-falkordb-data
```

### How do I reset everything?

```bash
km stop
docker volume rm km-falkordb-data
km start
```

---

## Common errors

| Error | Fix |
|---|---|
| `Connection refused :6379` | `km start` (Docker not running or image not pulled) |
| `No module named X` | `pipx reinstall knowledge-master` |
| `km: command not found` | Add `~/.local/bin` to PATH |
| `Ollama not found` | Install Ollama: https://ollama.com |
| `context length exceeded` | Normal — large files are skipped |
| `pull access denied` | Check Docker login or try `docker pull falkordb/falkordb:v4.4.1` manually |
