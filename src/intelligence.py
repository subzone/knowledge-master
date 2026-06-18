"""Intelligence extraction — detect tech stack, patterns, conventions, service topology."""

import json
import os
import re
from pathlib import Path


def extract_tech_stack(repo_path: str, graph):
    """Detect technologies from dependency files and create Tech nodes + relationships."""
    repo_name = Path(repo_path).name
    techs = set()

    # Python
    req = _read(repo_path, "requirements.txt")
    if req:
        techs.add(("Python", "language"))
        for line in req.splitlines():
            pkg = re.split(r"[=<>!~]", line.strip())[0].strip()
            if pkg and not pkg.startswith("#"):
                techs.add((pkg, "python-package"))

    pyproject = _read(repo_path, "pyproject.toml")
    if pyproject:
        techs.add(("Python", "language"))
        for m in re.findall(r'"([a-zA-Z0-9_-]+)(?:[=<>!~]|$)', pyproject):
            techs.add((m, "python-package"))

    # Node.js
    pkg_json = _read(repo_path, "package.json")
    if pkg_json:
        techs.add(("Node.js", "runtime"))
        try:
            pkg = json.loads(pkg_json)
            for dep in list(pkg.get("dependencies", {})) + list(pkg.get("devDependencies", {})):
                techs.add((dep, "npm-package"))
        except json.JSONDecodeError:
            pass

    # Rust
    cargo = _read(repo_path, "Cargo.toml")
    if cargo:
        techs.add(("Rust", "language"))
        for m in re.findall(r'^\s*([a-zA-Z0-9_-]+)\s*=', cargo, re.MULTILINE):
            if m not in ("name", "version", "edition", "authors", "description", "license", "repository"):
                techs.add((m, "rust-crate"))

    # Go
    gomod = _read(repo_path, "go.mod")
    if gomod:
        techs.add(("Go", "language"))
        for m in re.findall(r'^\s+([\w./-]+)', gomod, re.MULTILINE):
            techs.add((m.split("/")[-1], "go-module"))

    # Docker
    if _exists(repo_path, "Dockerfile") or _exists(repo_path, "docker-compose.yml"):
        techs.add(("Docker", "infrastructure"))

    # Kubernetes
    for f in Path(repo_path).rglob("*.yaml"):
        content = f.read_text(errors="ignore")[:500]
        if "apiVersion:" in content and "kind:" in content:
            techs.add(("Kubernetes", "infrastructure"))
            break

    # Terraform
    if any(Path(repo_path).rglob("*.tf")):
        techs.add(("Terraform", "infrastructure"))

    # Store in graph
    for name, category in techs:
        graph.query(
            "MERGE (t:Tech {name: $name}) SET t.category = $cat",
            params={"name": name, "cat": category},
        )
        graph.query(
            """MATCH (r:Repo {name: $repo}), (t:Tech {name: $tech})
               MERGE (r)-[:USES_TECH]->(t)""",
            params={"repo": repo_name, "tech": name},
        )

    return list(techs)


def extract_services(repo_path: str, graph):
    """Parse docker-compose and K8s manifests to build service dependency graph."""
    repo_name = Path(repo_path).name
    services = []

    # Docker Compose
    for compose_file in ("docker-compose.yml", "docker-compose.yaml", "compose.yml"):
        content = _read(repo_path, compose_file)
        if not content:
            continue
        # Simple YAML parsing for services (avoid PyYAML dep)
        in_services = False
        current_svc = None
        svc_indent = None
        for line in content.splitlines():
            if not line.strip() or line.strip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip())
            stripped = line.strip()
            if stripped == "services:":
                in_services = True
                svc_indent = indent + 2
                continue
            if in_services:
                if indent <= indent - 2 and stripped and indent == 0 and not stripped.startswith("#"):
                    break
                if indent == svc_indent and stripped.endswith(":") and not stripped.startswith("-"):
                    current_svc = stripped.rstrip(": ")
                    if not current_svc.startswith('"') and not current_svc.startswith("'"):
                        services.append(current_svc)
                        graph.query(
                            "MERGE (s:Service {name: $name}) SET s.source = 'docker-compose'",
                            params={"name": current_svc},
                        )
                        graph.query(
                            """MATCH (r:Repo {name: $repo}), (s:Service {name: $svc})
                               MERGE (r)-[:DEFINES_SERVICE]->(s)""",
                            params={"repo": repo_name, "svc": current_svc},
                        )
                # Detect depends_on
                if current_svc and "depends_on" in stripped:
                    pass  # next lines will have deps
                if current_svc and stripped.startswith("- ") and indent > svc_indent + 2:
                    dep = stripped.lstrip("- ").strip().rstrip(":")
                    if dep in services or dep:
                        graph.query(
                            "MERGE (s:Service {name: $name})",
                            params={"name": dep},
                        )
                        graph.query(
                            """MATCH (a:Service {name: $svc}), (b:Service {name: $dep})
                               MERGE (a)-[:DEPENDS_ON]->(b)""",
                            params={"svc": current_svc, "dep": dep},
                        )

    # K8s Deployments/Services
    for yaml_file in Path(repo_path).rglob("*.yaml"):
        content = yaml_file.read_text(errors="ignore")[:2000]
        if "kind: Deployment" in content or "kind: StatefulSet" in content:
            name_match = re.search(r'name:\s*(\S+)', content)
            if name_match:
                svc_name = name_match.group(1)
                services.append(svc_name)
                graph.query(
                    "MERGE (s:Service {name: $name}) SET s.source = 'kubernetes'",
                    params={"name": svc_name},
                )
                graph.query(
                    """MATCH (r:Repo {name: $repo}), (s:Service {name: $svc})
                       MERGE (r)-[:DEFINES_SERVICE]->(s)""",
                    params={"repo": repo_name, "svc": svc_name},
                )

    return services


def extract_conventions(repo_path: str, graph):
    """Analyze naming patterns, folder structure, and coding conventions."""
    repo_name = Path(repo_path).name
    conventions = []

    # File naming convention
    files = [f.name for f in Path(repo_path).rglob("*") if f.is_file() and not any(
        p in f.parts for p in (".git", "node_modules", "__pycache__", ".venv", "target")
    )]

    code_files = [f for f in files if Path(f).suffix in (".py", ".ts", ".js", ".rs", ".go")]
    if code_files:
        snake = sum(1 for f in code_files if "_" in Path(f).stem)
        kebab = sum(1 for f in code_files if "-" in Path(f).stem)
        camel = sum(1 for f in code_files if re.match(r'^[a-z]+[A-Z]', Path(f).stem))
        pascal = sum(1 for f in code_files if re.match(r'^[A-Z][a-z]+[A-Z]', Path(f).stem))
        total = len(code_files)

        if snake / total > 0.5:
            conventions.append(("snake_case files", "file-naming"))
        elif kebab / total > 0.3:
            conventions.append(("kebab-case files", "file-naming"))
        elif pascal / total > 0.3:
            conventions.append(("PascalCase files", "file-naming"))
        elif camel / total > 0.3:
            conventions.append(("camelCase files", "file-naming"))

    # Folder structure patterns
    dirs = set()
    for f in Path(repo_path).iterdir():
        if f.is_dir() and not f.name.startswith("."):
            dirs.add(f.name)

    if "src" in dirs:
        conventions.append(("src/ directory", "structure"))
    if "lib" in dirs:
        conventions.append(("lib/ directory", "structure"))
    if "tests" in dirs or "test" in dirs:
        conventions.append(("separate test directory", "testing"))
    if "docs" in dirs:
        conventions.append(("docs/ directory", "documentation"))
    if "infra" in dirs or "deploy" in dirs or "k8s" in dirs:
        conventions.append(("infra as code", "infrastructure"))

    # Detect patterns from code
    for py_file in list(Path(repo_path).rglob("*.py"))[:50]:
        content = py_file.read_text(errors="ignore")[:3000]
        if "class" in content and "Repository" in content:
            conventions.append(("Repository pattern", "design-pattern"))
        if "@app.route" in content or "@router" in content:
            conventions.append(("Route decorators", "design-pattern"))
        if "class" in content and ("Mixin" in content or "Base" in content):
            conventions.append(("Mixin/Base classes", "design-pattern"))

    # Deduplicate
    conventions = list(set(conventions))

    # Store in graph
    for name, category in conventions:
        graph.query(
            "MERGE (c:Convention {name: $name}) SET c.category = $cat",
            params={"name": name, "cat": category},
        )
        graph.query(
            """MATCH (r:Repo {name: $repo}), (c:Convention {name: $conv})
               MERGE (r)-[:FOLLOWS]->(c)""",
            params={"repo": repo_name, "conv": name},
        )

    return conventions


def extract_all(repo_path: str, graph):
    """Run all extraction passes on a repo."""
    techs = extract_tech_stack(repo_path, graph)
    services = extract_services(repo_path, graph)
    conventions = extract_conventions(repo_path, graph)
    return {
        "techs": len(techs),
        "services": len(services),
        "conventions": len(conventions),
    }


def _read(repo_path: str, filename: str) -> str | None:
    p = os.path.join(repo_path, filename)
    if os.path.exists(p):
        with open(p, "r", errors="ignore") as f:
            return f.read()
    return None


def _exists(repo_path: str, filename: str) -> bool:
    return os.path.exists(os.path.join(repo_path, filename))
