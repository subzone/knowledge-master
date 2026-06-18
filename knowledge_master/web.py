"""Web UI for Knowledge Master — FastAPI + htmx (no JS build step, works everywhere)."""

import json
from pathlib import Path

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

from . import embeddings, store
from .parsers import git_repo, markdown

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Knowledge Master</title>
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d1117; color: #e6edf3; padding: 2rem; max-width: 1200px; margin: 0 auto; }
  h1 { color: #58a6ff; margin-bottom: 1rem; }
  h2 { color: #8b949e; margin: 1.5rem 0 0.5rem; font-size: 1.1rem; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.2rem; margin-bottom: 1rem; }
  input[type=text], input[type=number] { background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 0.6rem 1rem; border-radius: 6px; width: 100%; font-size: 1rem; }
  input:focus { outline: none; border-color: #58a6ff; }
  button, .btn { background: #238636; color: #fff; border: none; padding: 0.6rem 1.2rem; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
  button:hover { background: #2ea043; }
  .btn-danger { background: #da3633; }
  .btn-danger:hover { background: #f85149; }
  .result { border-left: 3px solid #58a6ff; padding: 0.8rem 1rem; margin: 0.5rem 0; background: #0d1117; border-radius: 4px; }
  .result .score { color: #58a6ff; font-weight: bold; }
  .result .source { color: #8b949e; font-size: 0.85rem; }
  .result .text { margin-top: 0.3rem; font-size: 0.9rem; white-space: pre-wrap; }
  .stat { display: inline-block; background: #21262d; padding: 0.4rem 0.8rem; border-radius: 4px; margin: 0.2rem; }
  .flex { display: flex; gap: 0.5rem; align-items: center; }
  .source-item { display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid #21262d; }
  .msg { padding: 0.6rem 1rem; border-radius: 6px; margin: 0.5rem 0; }
  .msg-ok { background: #1b4332; color: #95d5b2; }
  .msg-err { background: #3d1f1f; color: #fca5a5; }
  .tabs { display: flex; gap: 0; margin-bottom: 1.5rem; }
  .tab { padding: 0.7rem 1.5rem; background: #21262d; border: 1px solid #30363d; cursor: pointer; color: #8b949e; }
  .tab:first-child { border-radius: 6px 0 0 6px; }
  .tab:last-child { border-radius: 0 6px 6px 0; }
  .tab.active, .tab:target { background: #161b22; color: #58a6ff; border-color: #58a6ff; }
  #results, #index-result, #sources { min-height: 50px; }
  .progress-bar { width: 100%; height: 24px; background: #21262d; border-radius: 4px; overflow: hidden; margin: 0.5rem 0; }
  .progress-fill { height: 100%; background: #238636; transition: width 0.3s; display: flex; align-items: center; padding-left: 0.5rem; font-size: 0.75rem; color: #fff; }
  .browse-row { padding: 0.4rem 1.2rem; cursor: pointer; color: #e6edf3; display: flex; align-items: center; gap: 0.5rem; }
  .browse-row:hover { background: #21262d; }
  .git-badge { background: #238636; color: #fff; font-size: 0.7rem; padding: 0.1rem 0.4rem; border-radius: 3px; margin-left: 0.5rem; }
  .htmx-indicator { display: none; }
  .htmx-request .htmx-indicator { display: inline; }
</style>
</head>
<body>
<h1>⚡ Knowledge Master</h1>
<div style="margin-bottom:1rem"><a href="/graph" class="btn" style="background:#238636;color:#fff;text-decoration:none;padding:0.5rem 1rem;border-radius:6px;">🕸️ View Knowledge Graph</a></div>
<div id="stats" hx-get="/api/stats" hx-trigger="load" hx-swap="innerHTML"></div>

<h2>🔍 Search</h2>
<div class="card">
  <form class="flex" hx-post="/api/search" hx-target="#results" hx-swap="innerHTML">
    <input type="text" name="query" placeholder="Search your knowledge base..." required style="flex:1">
    <input type="number" name="top_k" value="10" style="width:80px" min="1" max="50">
    <button type="submit">Search</button>
  </form>
  <div id="results" style="margin-top:1rem"></div>
</div>

<h2>📥 Index New Source</h2>
<div class="card">
  <form class="flex" id="index-form" onsubmit="startIndex(event)">
    <input type="text" name="path" id="path-input" placeholder="Path to git repo or docs directory" required style="flex:1">
    <select name="type" id="type-input" style="background:#0d1117;border:1px solid #30363d;color:#e6edf3;padding:0.6rem;border-radius:6px;">
      <option value="auto">Auto-detect</option>
      <option value="repo">Git Repo</option>
      <option value="docs">Documents</option>
    </select>
    <button type="submit" id="index-btn">Index</button>
    <button type="button" onclick="openBrowser()" style="background:#58a6ff;font-size:1.2rem;padding:0.6rem 0.9rem;">+</button>
  </form>
  <div id="index-result" style="margin-top:0.5rem"></div>
</div>

<!-- File Browser Modal -->
<div id="browser-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:100;align-items:center;justify-content:center;">
  <div style="background:#161b22;border:1px solid #30363d;border-radius:12px;width:600px;max-height:80vh;display:flex;flex-direction:column;">
    <div style="padding:1rem 1.2rem;border-bottom:1px solid #30363d;display:flex;justify-content:space-between;align-items:center;">
      <h3 style="color:#e6edf3;font-size:1rem;">Browse Files</h3>
      <button onclick="closeBrowser()" style="background:none;border:none;color:#8b949e;font-size:1.2rem;cursor:pointer;">✕</button>
    </div>
    <div id="browser-path" style="padding:0.5rem 1.2rem;color:#58a6ff;font-size:0.85rem;font-family:monospace;border-bottom:1px solid #21262d;"></div>
    <div id="browser-list" style="overflow-y:auto;flex:1;padding:0.5rem 0;"></div>
    <div style="padding:1rem 1.2rem;border-top:1px solid #30363d;display:flex;gap:0.5rem;justify-content:flex-end;">
      <button onclick="selectCurrent()" style="background:#238636;color:#fff;border:none;padding:0.5rem 1.2rem;border-radius:6px;cursor:pointer;">Select This Folder</button>
    </div>
  </div>
</div>

<script>
let currentBrowsePath = '';
function openBrowser() {
  document.getElementById('browser-modal').style.display = 'flex';
  browseTo('~');
}
function closeBrowser() { document.getElementById('browser-modal').style.display = 'none'; }
function selectCurrent() {
  document.getElementById('path-input').value = currentBrowsePath;
  closeBrowser();
}
function selectPath(p) {
  document.getElementById('path-input').value = p;
  closeBrowser();
}
async function browseTo(path) {
  const res = await fetch('/api/browse?path=' + encodeURIComponent(path));
  const data = await res.json();
  currentBrowsePath = data.current;
  document.getElementById('browser-path').textContent = data.current;
  const list = document.getElementById('browser-list');
  list.innerHTML = '';
  if (data.parent) {
    const row = document.createElement('div');
    row.className = 'browse-row';
    row.textContent = '⬆ ..';
    row.onclick = function() { browseTo(data.parent); };
    list.appendChild(row);
  }
  data.items.forEach(function(item) {
    const row = document.createElement('div');
    row.className = 'browse-row';
    const icon = item.is_git ? '📦' : item.is_dir ? '📁' : '📄';
    row.innerHTML = icon + ' ' + item.name + (item.is_git ? ' <span class="git-badge">git</span>' : '');
    row.onclick = function() {
      if (item.is_dir) { browseTo(item.path); }
      else { selectPath(item.path); }
    };
    list.appendChild(row);
  });
}
function startIndex(e) {
  e.preventDefault();
  var path = document.getElementById('path-input').value;
  var type = document.getElementById('type-input').value;
  var btn = document.getElementById('index-btn');
  var result = document.getElementById('index-result');
  btn.disabled = true;
  btn.textContent = 'Indexing...';
  result.innerHTML = '<div class="progress-bar"><div class="progress-fill" id="pbar" style="width:0%">0%</div></div><div id="pfile" style="font-size:0.8rem;color:#8b949e;margin-top:0.3rem;"></div>';
  var es = new EventSource('/api/index_stream?path=' + encodeURIComponent(path) + '&type=' + encodeURIComponent(type));
  es.onmessage = function(ev) {
    var d = JSON.parse(ev.data);
    if (d.done) {
      es.close();
      btn.disabled = false;
      btn.textContent = 'Index';
      result.innerHTML = '<div class="msg msg-ok">' + d.message + '</div>';
      htmx.ajax('GET', '/api/sources', {target:'#sources'});
      htmx.ajax('GET', '/api/stats', {target:'#stats'});
    } else if (d.error) {
      es.close();
      btn.disabled = false;
      btn.textContent = 'Index';
      result.innerHTML = '<div class="msg msg-err">' + d.error + '</div>';
    } else {
      var pct = Math.round(d.current / d.total * 100);
      document.getElementById('pbar').style.width = pct + '%';
      document.getElementById('pbar').textContent = pct + '% (' + d.current + '/' + d.total + ')';
      document.getElementById('pfile').textContent = d.file;
    }
  };
  es.onerror = function() { es.close(); btn.disabled = false; btn.textContent = 'Index'; };
}
</script>

<h2>📋 Indexed Sources</h2>
<div class="card">
  <div id="sources" hx-get="/api/sources" hx-trigger="load" hx-swap="innerHTML"></div>
</div>
</body>
</html>"""


GRAPH_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Knowledge Graph</title>
<script src="https://unpkg.com/d3@7.9.0/dist/d3.min.js"></script>
<style>
  * { margin: 0; padding: 0; }
  body { background: #0d1117; overflow: hidden; font-family: -apple-system, sans-serif; }
  svg { width: 100vw; height: 100vh; }
  .controls { position: fixed; top: 1rem; left: 1rem; z-index: 10; display: flex; gap: 0.5rem; }
  .controls button, .controls a { background: #21262d; color: #e6edf3; border: 1px solid #30363d; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; text-decoration: none; font-size: 0.85rem; }
  .controls button:hover, .controls a:hover { background: #30363d; }
  .tooltip { position: fixed; background: #161b22; border: 1px solid #30363d; color: #e6edf3; padding: 0.6rem 1rem; border-radius: 6px; font-size: 0.8rem; pointer-events: none; display: none; max-width: 400px; white-space: pre-wrap; }
</style>
</head>
<body>
<div class="controls">
  <a href="/">← Back</a>
  <button onclick="resetZoom()">Reset Zoom</button>
</div>
<div class="tooltip" id="tooltip"></div>
<svg></svg>
<script>
const colors = { Repo: '#58a6ff', Document: '#7ee787', Chunk: '#484f58', Person: '#d2a8ff', File: '#ffa657', Tech: '#f97583', Service: '#ffa657', Convention: '#d2a8ff' };
const sizes = { Repo: 16, Person: 14, Document: 8, Chunk: 4, File: 6, Tech: 12, Service: 14, Convention: 10 };

let simulation, svg, g, zoom;

async function loadGraph() {
  const res = await fetch('/api/graph');
  const data = await res.json();

  svg = d3.select('svg');
  const width = window.innerWidth, height = window.innerHeight;

  zoom = d3.zoom().scaleExtent([0.1, 8]).on('zoom', e => g.attr('transform', e.transform));
  svg.call(zoom);
  g = svg.append('g');

  simulation = d3.forceSimulation(data.nodes)
    .force('link', d3.forceLink(data.links).id(d => d.id).distance(60))
    .force('charge', d3.forceManyBody().strength(-120))
    .force('center', d3.forceCenter(width/2, height/2))
    .force('collision', d3.forceCollide().radius(d => sizes[d.type] + 2));

  const link = g.selectAll('line').data(data.links).join('line')
    .attr('stroke', '#30363d').attr('stroke-width', 1).attr('stroke-opacity', 0.6);

  const linkLabel = g.selectAll('.link-label').data(data.links).join('text')
    .attr('class', 'link-label').attr('fill', '#484f58').attr('font-size', '7px')
    .attr('text-anchor', 'middle').text(d => d.type);

  const node = g.selectAll('circle').data(data.nodes).join('circle')
    .attr('r', d => sizes[d.type] || 6)
    .attr('fill', d => colors[d.type] || '#8b949e')
    .attr('stroke', '#0d1117').attr('stroke-width', 1.5)
    .call(d3.drag().on('start', dragstart).on('drag', dragged).on('end', dragend));

  const label = g.selectAll('.label').data(data.nodes.filter(d => d.type !== 'Chunk')).join('text')
    .attr('class', 'label').attr('fill', '#8b949e').attr('font-size', '9px')
    .attr('dx', d => sizes[d.type] + 4).attr('dy', 3).text(d => d.label);

  const tooltip = document.getElementById('tooltip');
  node.on('mouseover', (e, d) => {
    tooltip.style.display = 'block';
    tooltip.style.left = e.clientX + 12 + 'px';
    tooltip.style.top = e.clientY + 12 + 'px';
    let info = `[${d.type}] ${d.label}`;
    if (d.text) info += '\\n\\n' + d.text.slice(0, 200);
    tooltip.textContent = info;
  }).on('mouseout', () => tooltip.style.display = 'none');

  simulation.on('tick', () => {
    link.attr('x1', d=>d.source.x).attr('y1', d=>d.source.y).attr('x2', d=>d.target.x).attr('y2', d=>d.target.y);
    linkLabel.attr('x', d=>(d.source.x+d.target.x)/2).attr('y', d=>(d.source.y+d.target.y)/2);
    node.attr('cx', d=>d.x).attr('cy', d=>d.y);
    label.attr('x', d=>d.x).attr('y', d=>d.y);
  });
}

function dragstart(e,d) { if(!e.active) simulation.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; }
function dragged(e,d) { d.fx=e.x; d.fy=e.y; }
function dragend(e,d) { if(!e.active) simulation.alphaTarget(0); d.fx=null; d.fy=null; }
function resetZoom() { svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity); }

loadGraph();
</script>
</body>
</html>"""


def create_app() -> FastAPI:
    app = FastAPI(title="Knowledge Master", docs_url="/docs")

    from .api import router as api_router
    app.include_router(api_router)

    @app.get("/", response_class=HTMLResponse)
    async def home():
        return HTML_TEMPLATE

    @app.get("/graph", response_class=HTMLResponse)
    async def graph_page():
        return GRAPH_PAGE

    @app.get("/api/graph")
    async def graph_data():
        graph = store.get_graph()
        nodes = []
        links = []
        seen = set()

        # Get repos
        result = graph.query("MATCH (r:Repo) RETURN id(r), r.name, r.path")
        for nid, name, path in (result.result_set or []):
            nodes.append({"id": f"repo_{nid}", "type": "Repo", "label": name or path or "repo"})
            seen.add(f"repo_{nid}")

        # Get people
        result = graph.query("MATCH (p:Person) RETURN id(p), p.name, p.email")
        for nid, name, email in (result.result_set or []):
            nodes.append({"id": f"person_{nid}", "type": "Person", "label": name or email})
            seen.add(f"person_{nid}")

        # Get documents
        result = graph.query("MATCH (d:Document) RETURN id(d), d.path, d.type")
        for nid, path, dtype in (result.result_set or []):
            label = path.split("/")[-1] if path else "doc"
            nodes.append({"id": f"doc_{nid}", "type": "Document", "label": label})
            seen.add(f"doc_{nid}")

        # Get techs
        result = graph.query("MATCH (t:Tech) RETURN id(t), t.name, t.category")
        for nid, name, cat in (result.result_set or []):
            nodes.append({"id": f"tech_{nid}", "type": "Tech", "label": name, "category": cat or ""})
            seen.add(f"tech_{nid}")

        # Get services
        result = graph.query("MATCH (s:Service) RETURN id(s), s.name, s.source")
        for nid, name, source in (result.result_set or []):
            nodes.append({"id": f"svc_{nid}", "type": "Service", "label": name, "source": source or ""})
            seen.add(f"svc_{nid}")

        # Get conventions
        result = graph.query("MATCH (c:Convention) RETURN id(c), c.name, c.category")
        for nid, name, cat in (result.result_set or []):
            nodes.append({"id": f"conv_{nid}", "type": "Convention", "label": name, "category": cat or ""})
            seen.add(f"conv_{nid}")

        # Get chunks (limit)
        result = graph.query("MATCH (c:Chunk) RETURN id(c), c.source, c.text LIMIT 50")
        for nid, source, text in (result.result_set or []):
            nodes.append({"id": f"chunk_{nid}", "type": "Chunk", "label": "", "text": text or ""})
            seen.add(f"chunk_{nid}")

        # Edges: Document -> Repo
        result = graph.query("MATCH (d:Document)-[:IN_REPO]->(r:Repo) RETURN id(d), id(r)")
        for did, rid in (result.result_set or []):
            links.append({"source": f"doc_{did}", "target": f"repo_{rid}", "type": "IN_REPO"})

        # Edges: Chunk -> Document
        result = graph.query("MATCH (c:Chunk)-[:PART_OF]->(d:Document) RETURN id(c), id(d) LIMIT 100")
        for cid, did in (result.result_set or []):
            if f"chunk_{cid}" in seen and f"doc_{did}" in seen:
                links.append({"source": f"chunk_{cid}", "target": f"doc_{did}", "type": "PART_OF"})

        # Edges: Person -> Document
        result = graph.query("MATCH (p:Person)-[:AUTHORED]->(d:Document) RETURN id(p), id(d)")
        for pid, did in (result.result_set or []):
            links.append({"source": f"person_{pid}", "target": f"doc_{did}", "type": "AUTHORED"})

        # Edges: Repo -> Tech
        result = graph.query("MATCH (r:Repo)-[:USES_TECH]->(t:Tech) RETURN id(r), id(t)")
        for rid, tid in (result.result_set or []):
            links.append({"source": f"repo_{rid}", "target": f"tech_{tid}", "type": "USES_TECH"})

        # Edges: Repo -> Service
        result = graph.query("MATCH (r:Repo)-[:DEFINES_SERVICE]->(s:Service) RETURN id(r), id(s)")
        for rid, sid in (result.result_set or []):
            links.append({"source": f"repo_{rid}", "target": f"svc_{sid}", "type": "DEFINES_SERVICE"})

        # Edges: Service -> Service (depends_on)
        result = graph.query("MATCH (a:Service)-[:DEPENDS_ON]->(b:Service) RETURN id(a), id(b)")
        for aid, bid in (result.result_set or []):
            links.append({"source": f"svc_{aid}", "target": f"svc_{bid}", "type": "DEPENDS_ON"})

        # Edges: Repo -> Convention
        result = graph.query("MATCH (r:Repo)-[:FOLLOWS]->(c:Convention) RETURN id(r), id(c)")
        for rid, cid in (result.result_set or []):
            links.append({"source": f"repo_{rid}", "target": f"conv_{cid}", "type": "FOLLOWS"})

        return {"nodes": nodes, "links": links}

    @app.get("/api/browse")
    async def browse(path: str = "~"):
        """Browse local filesystem for selecting folders to index."""
        target = Path(path).expanduser().resolve()
        if not target.exists() or not target.is_dir():
            target = Path.home()

        items = []
        try:
            for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                if entry.name.startswith(".") and entry.name != ".git":
                    continue
                if entry.name in ("node_modules", "__pycache__", "venv", ".venv", "target", "dist", "build"):
                    continue
                if entry.is_dir():
                    is_git = (entry / ".git").exists()
                    items.append({"name": entry.name, "path": str(entry), "is_dir": True, "is_git": is_git})
                elif entry.suffix in (".md", ".txt", ".pdf", ".docx", ".xlsx"):
                    items.append({"name": entry.name, "path": str(entry), "is_dir": False, "is_git": False})
        except PermissionError:
            pass

        parent = str(target.parent) if target != target.parent else None
        return {"current": str(target), "parent": parent, "items": items[:100]}

    @app.get("/api/stats", response_class=HTMLResponse)
    async def stats():
        graph = store.get_graph()
        s = store.get_stats(graph)
        return f"""<div>
            <span class="stat">📄 {s['chunks']} chunks</span>
            <span class="stat">📁 {s['documents']} documents</span>
            <span class="stat">📦 {s['repos']} repos</span>
        </div>"""

    @app.post("/api/search", response_class=HTMLResponse)
    async def search(query: str = Form(...), top_k: int = Form(10)):
        graph = store.get_graph()
        vec = embeddings.embed(query)
        results = store.graph_context_search(graph, vec, top_k)
        if not results:
            return '<div class="msg msg-err">No results found.</div>'
        html = ""
        for r in results:
            ctx = ""
            if r.get("repo"):
                ctx += f" · repo:{r['repo']}"
            if r.get("author"):
                ctx += f" · by:{r['author']}"
            text = (r.get("text") or "")[:300]
            html += f"""<div class="result">
                <span class="score">{r.get('score',0):.3f}</span>
                <span class="source">{r.get('source','')}{ctx}</span>
                <div class="text">{text}</div>
            </div>"""
        return html

    @app.post("/api/index", response_class=HTMLResponse)
    async def index_source(path: str = Form(...), type: str = Form("auto")):
        path = str(Path(path).expanduser().resolve())
        if not Path(path).exists():
            return f'<div class="msg msg-err">Path not found: {path}</div>'

        graph = store.get_graph()
        store.init_schema(graph)

        if type == "auto":
            type = "repo" if (Path(path) / ".git").exists() else "docs"

        try:
            if type == "repo":
                result = git_repo.index_repo(path, graph)
            else:
                result = markdown.index_directory(path, graph)
            return f'<div class="msg msg-ok">✓ Indexed: {json.dumps(result)}</div>'
        except Exception as e:
            return f'<div class="msg msg-err">Error: {e}</div>'


    @app.get("/api/index_stream")
    async def index_stream(path: str, type: str = "auto"):
        """SSE endpoint for indexing with progress."""
        from starlette.responses import StreamingResponse
        import queue
        import threading

        path = str(Path(path).expanduser().resolve())

        def generate():
            if not Path(path).exists():
                yield f"data: {json.dumps({'error': 'Path not found: ' + path})}\n\n"
                return

            graph = store.get_graph()
            store.init_schema(graph)
            resolved_type = type
            if resolved_type == "auto":
                resolved_type = "repo" if (Path(path) / ".git").exists() else "docs"

            q = queue.Queue()

            def progress_cb(current, total, filepath):
                q.put({"current": current, "total": total, "file": filepath})

            def run_index():
                try:
                    if resolved_type == "repo":
                        result = git_repo.index_repo(path, graph, on_progress=progress_cb)
                    else:
                        result = markdown.index_directory(path, graph)
                        result = result or {}
                    q.put({"done": True, "message": "Indexed " + str(result.get('files_indexed', 0)) + " files"})
                except Exception as e:
                    q.put({"error": str(e)})

            t = threading.Thread(target=run_index)
            t.start()

            while True:
                try:
                    msg = q.get(timeout=30)
                    yield f"data: {json.dumps(msg)}\n\n"
                    if msg.get("done") or msg.get("error"):
                        break
                except queue.Empty:
                    yield f"data: {json.dumps({'error': 'Timeout'})}\n\n"
                    break

            t.join(timeout=5)

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/api/sources", response_class=HTMLResponse)
    async def sources():
        graph = store.get_graph()
        # Get repos
        repos = graph.query("MATCH (r:Repo) RETURN r.name, r.path")
        # Get standalone docs
        docs = graph.query(
            "MATCH (d:Document) WHERE NOT (d)-[:IN_REPO]->() RETURN d.path, d.type LIMIT 50"
        )
        html = ""
        for name, path in (repos.result_set or []):
            html += f"""<div class="source-item">
                <span>📦 <b>{name or path}</b> <span class="source">{path}</span></span>
                <button class="btn-danger" hx-delete="/api/source?name={name}" hx-target="#sources" hx-swap="innerHTML" hx-confirm="Delete {name} and all its chunks?">Remove</button>
            </div>"""
        for dpath, dtype in (docs.result_set or []):
            html += f"""<div class="source-item">
                <span>📄 {dpath} <span class="source">({dtype})</span></span>
                <button class="btn-danger" hx-delete="/api/source?path={dpath}" hx-target="#sources" hx-swap="innerHTML" hx-confirm="Delete {dpath}?">Remove</button>
            </div>"""
        if not html:
            html = '<div class="msg">No sources indexed yet. Add one above.</div>'
        return html

    @app.delete("/api/source", response_class=HTMLResponse)
    async def delete_source(name: str = None, path: str = None):
        graph = store.get_graph()
        if name:
            graph.query(
                """MATCH (r:Repo {name: $name})
                   OPTIONAL MATCH (d:Document)-[:IN_REPO]->(r)
                   OPTIONAL MATCH (c:Chunk)-[:PART_OF]->(d)
                   DELETE c, d, r""",
                params={"name": name},
            )
        elif path:
            graph.query(
                """MATCH (d:Document {path: $path})
                   OPTIONAL MATCH (c:Chunk)-[:PART_OF]->(d)
                   DELETE c, d""",
                params={"path": path},
            )
        # Return updated sources list
        repos = graph.query("MATCH (r:Repo) RETURN r.name, r.path")
        docs = graph.query(
            "MATCH (d:Document) WHERE NOT (d)-[:IN_REPO]->() RETURN d.path, d.type LIMIT 50"
        )
        html = ""
        for n, p in (repos.result_set or []):
            html += f"""<div class="source-item">
                <span>📦 <b>{n or p}</b></span>
                <button class="btn-danger" hx-delete="/api/source?name={n}" hx-target="#sources" hx-swap="innerHTML">Remove</button>
            </div>"""
        for dp, dt in (docs.result_set or []):
            html += f"""<div class="source-item">
                <span>📄 {dp} ({dt})</span>
                <button class="btn-danger" hx-delete="/api/source?path={dp}" hx-target="#sources" hx-swap="innerHTML">Remove</button>
            </div>"""
        return html or '<div class="msg">No sources indexed.</div>'

    return app
