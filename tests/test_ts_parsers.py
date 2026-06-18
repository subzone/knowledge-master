"""Tests for tree-sitter based language parsers."""
import tempfile
from pathlib import Path

from knowledge_master.ts_parsers import (
    extract_typescript_graph,
    extract_go_graph,
    extract_rust_graph,
    resolve_ts_import,
)


def test_typescript_import_extraction():
    with tempfile.NamedTemporaryFile(suffix=".ts", mode="w", delete=False) as f:
        f.write('import { useState } from "react";\n')
        f.write('import { helper } from "./utils";\n')
        f.write("export function App() { return null; }\n")
        f.flush()
        result = extract_typescript_graph(f.name)

    assert len(result["imports"]) == 2
    assert result["imports"][0]["module"] == "react"
    assert result["imports"][1]["module"] == "./utils"
    assert len(result["exports"]) >= 1
    assert any(e["name"] == "App" for e in result["exports"])


def test_typescript_require_extraction():
    with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
        f.write('const fs = require("fs");\n')
        f.flush()
        result = extract_typescript_graph(f.name)

    assert len(result["imports"]) >= 1
    assert result["imports"][0]["module"] == "fs"


def test_go_import_extraction():
    with tempfile.NamedTemporaryFile(suffix=".go", mode="w", delete=False) as f:
        f.write('package main\n\nimport (\n\t"fmt"\n\t"os"\n)\n\nfunc Main() {}\n')
        f.flush()
        result = extract_go_graph(f.name)

    assert len(result["imports"]) >= 2
    modules = [i["module"] for i in result["imports"]]
    assert "fmt" in modules
    assert "os" in modules


def test_go_exported_functions():
    with tempfile.NamedTemporaryFile(suffix=".go", mode="w", delete=False) as f:
        f.write('package pkg\n\nfunc PublicFunc() {}\nfunc privateFunc() {}\n')
        f.flush()
        result = extract_go_graph(f.name)

    names = [e["name"] for e in result["exports"]]
    assert "PublicFunc" in names
    assert "privateFunc" not in names


def test_rust_use_extraction():
    with tempfile.NamedTemporaryFile(suffix=".rs", mode="w", delete=False) as f:
        f.write("use std::collections::HashMap;\nuse crate::utils;\n\npub fn hello() {}\nfn private() {}\n")
        f.flush()
        result = extract_rust_graph(f.name)

    assert len(result["imports"]) >= 2
    modules = [i["module"] for i in result["imports"]]
    assert "std" in modules
    assert any(e["name"] == "hello" for e in result["exports"])
    assert not any(e["name"] == "private" for e in result["exports"])


def test_rust_mod_detection():
    with tempfile.NamedTemporaryFile(suffix=".rs", mode="w", delete=False) as f:
        f.write("mod parser;\nmod utils;\n")
        f.flush()
        result = extract_rust_graph(f.name)

    mod_imports = [i for i in result["imports"] if i.get("is_mod")]
    assert len(mod_imports) == 2
    assert mod_imports[0]["module"] == "parser"


def test_ts_import_resolution():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "src").mkdir()
        (Path(tmp) / "src" / "utils.ts").write_text("export const x = 1;")
        (Path(tmp) / "src" / "index.ts").write_text("")

        result = resolve_ts_import("./utils", "src/index.ts", tmp)
        assert result == "src/utils.ts"

        # External package — should return None
        result = resolve_ts_import("react", "src/index.ts", tmp)
        assert result is None
