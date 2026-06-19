"""Static analysis — extract import graphs, symbols, and call relationships from code."""

import ast
import os
from pathlib import Path


def extract_python_graph(file_path: str) -> dict:
    """Extract imports, exports (top-level functions/classes), and calls from a Python file."""
    try:
        source = Path(file_path).read_text(errors="ignore")
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return {"imports": [], "exports": [], "calls": [], "path": file_path}

    imports = []
    exports = []
    calls = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({"module": alias.name, "alias": alias.asname, "names": []})
        elif isinstance(node, ast.ImportFrom):
            imports.append({
                "module": node.module or "",
                "names": [a.name for a in node.names],
                "level": node.level,
            })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.col_offset == 0:  # top-level function
                exports.append({"name": node.name, "type": "function", "line": node.lineno})
        elif isinstance(node, ast.ClassDef):
            if node.col_offset == 0:  # top-level class
                bases = [_node_name(b) for b in node.bases]
                exports.append({"name": node.name, "type": "class", "line": node.lineno, "bases": bases})

    return {"imports": imports, "exports": exports, "calls": calls, "path": file_path}


def resolve_import(module: str, level: int, source_file: str, repo_root: str) -> str | None:
    """Resolve an import to a file path within the repo."""
    if level > 0:
        # Relative import: go up `level` directories from source file's package
        source_dir = Path(os.path.join(repo_root, source_file)).parent
        for _ in range(level - 1):
            source_dir = source_dir.parent
        parts = module.split(".") if module else []
        candidate = source_dir / Path(*parts) if parts else source_dir
    else:
        # Absolute import — check if it's a local module
        parts = module.split(".")
        candidate = Path(repo_root) / Path(*parts)

    # Try as module.py or package/__init__.py
    as_file = str(candidate) + ".py"
    as_pkg = str(candidate / "__init__.py")

    if os.path.exists(as_file):
        return os.path.relpath(as_file, repo_root)
    if os.path.exists(as_pkg):
        return os.path.relpath(as_pkg, repo_root)

    return None


def build_import_graph(repo_path: str, graph):
    """Walk a repo, extract Python imports, store as IMPORTS edges between File nodes."""
    repo_path = str(Path(repo_path).resolve())
    repo_name = Path(repo_path).name
    py_files = list(Path(repo_path).rglob("*.py"))
    py_files = [f for f in py_files if not any(
        p in f.parts for p in (".venv", "venv", "node_modules", "__pycache__", ".git", "site-packages")
    )]

    file_exports = {}  # relative_path -> [exported symbols]
    file_imports = {}  # relative_path -> [import info]

    # Pass 1: collect exports and imports
    for py_file in py_files:
        relative = os.path.relpath(str(py_file), repo_path)
        result = extract_python_graph(str(py_file))
        file_exports[relative] = result["exports"]
        file_imports[relative] = result["imports"]

        # Store Function/Class nodes
        for export in result["exports"]:
            node_type = "Function" if export["type"] == "function" else "Class"
            graph.query(
                f"MERGE (s:{node_type} {{name: $name, file: $file, repo: $repo}}) SET s.line = $line",
                params={"name": export["name"], "file": relative, "repo": repo_name, "line": export["line"]},
            )
            # Link symbol to file
            graph.query(
                f"""MATCH (s:{node_type} {{name: $name, file: $file}}), (d:Document {{path: $file}})
                    MERGE (s)-[:DEFINED_IN]->(d)""",
                params={"name": export["name"], "file": relative},
            )

    # Pass 2: resolve imports to file paths, create IMPORTS edges
    edges_created = 0
    for source_file, imports in file_imports.items():
        for imp in imports:
            module = imp.get("module", "")
            level = imp.get("level", 0)
            names = imp.get("names", [])

            if module:
                # from module import X  or  import module
                target_file = resolve_import(module, level, source_file, repo_path)
                if target_file and target_file in file_exports:
                    graph.query(
                        """MERGE (src:Document {path: $src})
                           MERGE (dst:Document {path: $dst})
                           MERGE (src)-[:IMPORTS {names: $names}]->(dst)""",
                        params={"src": source_file, "dst": target_file, "names": names},
                    )
                    edges_created += 1
            elif level > 0 and names:
                # from . import module1, module2 — each name is a sibling module
                for name in names:
                    target_file = resolve_import(name, level, source_file, repo_path)
                    if target_file and target_file in file_exports:
                        graph.query(
                            """MERGE (src:Document {path: $src})
                               MERGE (dst:Document {path: $dst})
                               MERGE (src)-[:IMPORTS {names: $imp_names}]->(dst)""",
                            params={"src": source_file, "dst": target_file, "imp_names": [name]},
                        )
                        edges_created += 1

    return {"files_analyzed": len(py_files), "import_edges": edges_created, "symbols": sum(len(v) for v in file_exports.values())}


def _node_name(node) -> str:
    """Get string name from an AST node."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{_node_name(node.value)}.{node.attr}"
    return ""


def build_import_graph_all(repo_path: str, graph):
    """Build import graph for all supported languages in the repo."""
    repo_path = str(Path(repo_path).resolve())
    results = {"python": {}, "typescript": {}, "go": {}, "rust": {}, "java": {}, "csharp": {}, "terraform": {}}

    # Python (AST-based)
    results["python"] = build_import_graph(repo_path, graph)

    # TypeScript/JavaScript (tree-sitter)
    results["typescript"] = _build_ts_import_graph(repo_path, graph)

    # Go (tree-sitter)
    results["go"] = _build_go_import_graph(repo_path, graph)

    # Rust (tree-sitter)
    results["rust"] = _build_rust_import_graph(repo_path, graph)

    # Java (tree-sitter)
    results["java"] = _build_java_import_graph(repo_path, graph)

    # C# (tree-sitter)
    results["csharp"] = _build_csharp_import_graph(repo_path, graph)

    # Terraform (regex-based HCL)
    results["terraform"] = _build_terraform_graph(repo_path, graph)

    total_edges = sum(r.get("import_edges", 0) for r in results.values())
    total_symbols = sum(r.get("symbols", 0) for r in results.values())
    total_files = sum(r.get("files_analyzed", 0) for r in results.values())

    return {"files_analyzed": total_files, "import_edges": total_edges, "symbols": total_symbols, "by_language": results}


def _build_ts_import_graph(repo_path: str, graph) -> dict:
    """Build import graph for TypeScript/JavaScript files."""
    from .ts_parsers import extract_typescript_graph, resolve_ts_import

    skip = {".git", "node_modules", "dist", "build", ".venv", "__pycache__"}
    ts_files = []
    for ext in (".ts", ".tsx", ".js", ".jsx"):
        for f in Path(repo_path).rglob(f"*{ext}"):
            if not any(p in f.parts for p in skip):
                ts_files.append(f)

    if not ts_files:
        return {"files_analyzed": 0, "import_edges": 0, "symbols": 0}

    edges = 0
    symbols = 0
    for ts_file in ts_files:
        relative = os.path.relpath(str(ts_file), repo_path)
        try:
            result = extract_typescript_graph(str(ts_file))
        except Exception:
            continue

        # Store exports as symbols
        for export in result["exports"]:
            graph.query(
                "MERGE (f:Function {name: $name, file: $file}) SET f.line = $line, f.lang = 'typescript'",
                params={"name": export["name"], "file": relative, "line": export.get("line", 0)},
            )
            symbols += 1

        # Resolve imports and create edges
        for imp in result["imports"]:
            target = resolve_ts_import(imp["module"], relative, repo_path)
            if target:
                graph.query(
                    """MERGE (src:Document {path: $src})
                       MERGE (dst:Document {path: $dst})
                       MERGE (src)-[:IMPORTS {names: $names, lang: 'typescript'}]->(dst)""",
                    params={"src": relative, "dst": target, "names": imp.get("names", [])},
                )
                edges += 1

    return {"files_analyzed": len(ts_files), "import_edges": edges, "symbols": symbols}


def _build_go_import_graph(repo_path: str, graph) -> dict:
    """Build import graph for Go files."""
    from .ts_parsers import extract_go_graph, resolve_go_import

    skip = {".git", "vendor", "node_modules"}
    go_files = [f for f in Path(repo_path).rglob("*.go") if not any(p in f.parts for p in skip)]

    if not go_files:
        return {"files_analyzed": 0, "import_edges": 0, "symbols": 0}

    # Read go.mod for module name
    go_module = ""
    gomod = Path(repo_path) / "go.mod"
    if gomod.exists():
        for line in gomod.read_text().splitlines():
            if line.startswith("module "):
                go_module = line.split()[1]
                break

    edges = 0
    symbols = 0
    for go_file in go_files:
        relative = os.path.relpath(str(go_file), repo_path)
        try:
            result = extract_go_graph(str(go_file))
        except Exception:
            continue

        for export in result["exports"]:
            graph.query(
                "MERGE (f:Function {name: $name, file: $file}) SET f.line = $line, f.lang = 'go'",
                params={"name": export["name"], "file": relative, "line": export.get("line", 0)},
            )
            symbols += 1

        for imp in result["imports"]:
            target = resolve_go_import(imp["module"], repo_path, go_module)
            if target:
                graph.query(
                    """MERGE (src:Document {path: $src})
                       MERGE (dst:Document {path: $dst})
                       MERGE (src)-[:IMPORTS {names: $names, lang: 'go'}]->(dst)""",
                    params={"src": relative, "dst": target, "names": []},
                )
                edges += 1

    return {"files_analyzed": len(go_files), "import_edges": edges, "symbols": symbols}


def _build_rust_import_graph(repo_path: str, graph) -> dict:
    """Build import graph for Rust files."""
    from .ts_parsers import extract_rust_graph

    skip = {".git", "target", "node_modules"}
    rs_files = [f for f in Path(repo_path).rglob("*.rs") if not any(p in f.parts for p in skip)]

    if not rs_files:
        return {"files_analyzed": 0, "import_edges": 0, "symbols": 0}

    edges = 0
    symbols = 0
    for rs_file in rs_files:
        relative = os.path.relpath(str(rs_file), repo_path)
        try:
            result = extract_rust_graph(str(rs_file))
        except Exception:
            continue

        for export in result["exports"]:
            graph.query(
                "MERGE (f:Function {name: $name, file: $file}) SET f.line = $line, f.lang = 'rust'",
                params={"name": export["name"], "file": relative, "line": export.get("line", 0)},
            )
            symbols += 1

        # Rust mod resolution: mod foo -> foo.rs or foo/mod.rs
        for imp in result["imports"]:
            if imp.get("is_mod"):
                mod_name = imp["module"]
                src_dir = Path(os.path.join(repo_path, relative)).parent
                for candidate in [src_dir / f"{mod_name}.rs", src_dir / mod_name / "mod.rs"]:
                    if candidate.exists():
                        target = os.path.relpath(str(candidate), repo_path)
                        graph.query(
                            """MERGE (src:Document {path: $src})
                               MERGE (dst:Document {path: $dst})
                               MERGE (src)-[:IMPORTS {names: [], lang: 'rust'}]->(dst)""",
                            params={"src": relative, "dst": target},
                        )
                        edges += 1
                        break

    return {"files_analyzed": len(rs_files), "import_edges": edges, "symbols": symbols}


def _build_java_import_graph(repo_path: str, graph) -> dict:
    """Build import graph for Java files."""
    from .ts_parsers import extract_java_graph

    skip = {".git", "node_modules", "target", "build", ".gradle"}
    java_files = [f for f in Path(repo_path).rglob("*.java") if not any(p in f.parts for p in skip)]

    if not java_files:
        return {"files_analyzed": 0, "import_edges": 0, "symbols": 0}

    symbols = 0
    for java_file in java_files:
        relative = os.path.relpath(str(java_file), repo_path)
        try:
            result = extract_java_graph(str(java_file))
        except Exception:
            continue
        for export in result["exports"]:
            graph.query(
                "MERGE (f:Function {name: $name, file: $file}) SET f.line = $line, f.lang = 'java'",
                params={"name": export["name"], "file": relative, "line": export.get("line", 0)},
            )
            symbols += 1

    return {"files_analyzed": len(java_files), "import_edges": 0, "symbols": symbols}


def _build_csharp_import_graph(repo_path: str, graph) -> dict:
    """Build import graph for C# files."""
    from .ts_parsers import extract_csharp_graph

    skip = {".git", "node_modules", "bin", "obj", "packages"}
    cs_files = [f for f in Path(repo_path).rglob("*.cs") if not any(p in f.parts for p in skip)]

    if not cs_files:
        return {"files_analyzed": 0, "import_edges": 0, "symbols": 0}

    symbols = 0
    for cs_file in cs_files:
        relative = os.path.relpath(str(cs_file), repo_path)
        try:
            result = extract_csharp_graph(str(cs_file))
        except Exception:
            continue
        for export in result["exports"]:
            graph.query(
                "MERGE (f:Function {name: $name, file: $file}) SET f.line = $line, f.lang = 'csharp'",
                params={"name": export["name"], "file": relative, "line": export.get("line", 0)},
            )
            symbols += 1

    return {"files_analyzed": len(cs_files), "import_edges": 0, "symbols": symbols}


def _build_terraform_graph(repo_path: str, graph) -> dict:
    """Build module dependency graph for Terraform files."""
    from .ts_parsers import extract_terraform_graph

    skip = {".git", ".terraform", "node_modules"}
    tf_files = [f for f in Path(repo_path).rglob("*.tf") if not any(p in f.parts for p in skip)]

    if not tf_files:
        return {"files_analyzed": 0, "import_edges": 0, "symbols": 0}

    edges = 0
    symbols = 0
    for tf_file in tf_files:
        relative = os.path.relpath(str(tf_file), repo_path)
        try:
            result = extract_terraform_graph(str(tf_file))
        except Exception:
            continue

        for export in result["exports"]:
            graph.query(
                "MERGE (f:Function {name: $name, file: $file}) SET f.line = $line, f.lang = 'terraform'",
                params={"name": export["name"], "file": relative, "line": export.get("line", 0)},
            )
            symbols += 1

        # Module source → file edge (if local path)
        for imp in result["imports"]:
            module_source = imp["module"]
            if module_source.startswith("./") or module_source.startswith("../"):
                target_dir = os.path.normpath(os.path.join(os.path.dirname(relative), module_source))
                graph.query(
                    """MERGE (src:Document {path: $src})
                       MERGE (dst:Document {path: $dst})
                       MERGE (src)-[:IMPORTS {names: $names, lang: 'terraform'}]->(dst)""",
                    params={"src": relative, "dst": target_dir, "names": imp.get("names", [])},
                )
                edges += 1

    return {"files_analyzed": len(tf_files), "import_edges": edges, "symbols": symbols}
