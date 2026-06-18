"""Tree-sitter based import graph extraction for TypeScript, Go, and Rust."""

import os
from pathlib import Path

from tree_sitter import Language, Parser
import tree_sitter_typescript as ts_ts
import tree_sitter_go as ts_go
import tree_sitter_rust as ts_rust
import tree_sitter_javascript as ts_js

# Initialize languages
TYPESCRIPT = Language(ts_ts.language_typescript())
TSX = Language(ts_ts.language_tsx())
JAVASCRIPT = Language(ts_js.language())
GO = Language(ts_go.language())
RUST = Language(ts_rust.language())


def extract_typescript_graph(file_path: str) -> dict:
    """Extract imports and exports from a TypeScript/JavaScript file."""
    source = Path(file_path).read_bytes()
    lang = TSX if file_path.endswith(".tsx") else (JAVASCRIPT if file_path.endswith(".js") else TYPESCRIPT)
    parser = Parser(lang)
    tree = parser.parse(source)

    imports = []
    exports = []

    for node in _walk(tree.root_node):
        # import { X } from './module'  |  import X from 'module'
        if node.type == "import_statement":
            source_node = node.child_by_field_name("source")
            if source_node:
                module = source_node.text.decode().strip("'\"")
                names = []
                for child in node.children:
                    if child.type == "import_clause":
                        for spec in _walk(child):
                            if spec.type == "identifier":
                                names.append(spec.text.decode())
                            elif spec.type == "import_specifier":
                                name_node = spec.child_by_field_name("name")
                                if name_node:
                                    names.append(name_node.text.decode())
                imports.append({"module": module, "names": names})

        # require('module')
        elif node.type == "call_expression":
            func = node.child_by_field_name("function")
            if func and func.text == b"require":
                args = node.child_by_field_name("arguments")
                if args and args.child_count > 1:
                    arg = args.children[1]
                    if arg.type == "string":
                        imports.append({"module": arg.text.decode().strip("'\""), "names": []})

        # export function/class/const
        elif node.type in ("export_statement", "export_default_declaration"):
            decl = node.child_by_field_name("declaration")
            if decl:
                name_node = decl.child_by_field_name("name")
                if name_node:
                    exports.append({"name": name_node.text.decode(), "type": decl.type, "line": decl.start_point[0] + 1})
            # export { x, y }
            for child in node.children:
                if child.type == "export_clause":
                    for spec in _walk(child):
                        if spec.type == "export_specifier":
                            name_node = spec.child_by_field_name("name")
                            if name_node:
                                exports.append({"name": name_node.text.decode(), "type": "re-export", "line": spec.start_point[0] + 1})

        # Top-level function/class declarations
        elif node.type in ("function_declaration", "class_declaration") and node.parent.type in ("program", "export_statement"):
            name_node = node.child_by_field_name("name")
            if name_node:
                exports.append({"name": name_node.text.decode(), "type": node.type, "line": node.start_point[0] + 1})

    return {"imports": imports, "exports": exports, "path": file_path}


def extract_go_graph(file_path: str) -> dict:
    """Extract imports and exports from a Go file."""
    source = Path(file_path).read_bytes()
    parser = Parser(GO)
    tree = parser.parse(source)

    imports = []
    exports = []

    for node in _walk(tree.root_node):
        # import "pkg" or import ( "pkg1"; "pkg2" )
        if node.type == "import_declaration":
            for child in _walk(node):
                if child.type == "import_spec":
                    path_node = child.child_by_field_name("path")
                    if path_node:
                        module = path_node.text.decode().strip('"')
                        imports.append({"module": module, "names": []})
                elif child.type == "interpreted_string_literal":
                    imports.append({"module": child.text.decode().strip('"'), "names": []})

        # Exported functions (capitalized)
        elif node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode()
                if name[0].isupper():  # Go exports are capitalized
                    exports.append({"name": name, "type": "function", "line": node.start_point[0] + 1})

        # Exported types
        elif node.type == "type_declaration":
            for spec in node.children:
                if spec.type == "type_spec":
                    name_node = spec.child_by_field_name("name")
                    if name_node:
                        name = name_node.text.decode()
                        if name[0].isupper():
                            exports.append({"name": name, "type": "type", "line": spec.start_point[0] + 1})

    return {"imports": imports, "exports": exports, "path": file_path}


def extract_rust_graph(file_path: str) -> dict:
    """Extract use statements and pub items from a Rust file."""
    source = Path(file_path).read_bytes()
    parser = Parser(RUST)
    tree = parser.parse(source)

    imports = []
    exports = []

    for node in _walk(tree.root_node):
        # use std::collections::HashMap;  |  use crate::module::Item;
        if node.type == "use_declaration":
            path_text = ""
            for child in _walk(node):
                if child.type in ("scoped_identifier", "identifier", "use_wildcard", "scoped_use_list"):
                    path_text = child.text.decode()
                    break
            if path_text:
                module = path_text.split("::")[0]
                names = path_text.split("::")[-1:] if "::" in path_text else []
                imports.append({"module": module, "path": path_text, "names": names})

        # mod declarations
        elif node.type == "mod_item":
            name_node = node.child_by_field_name("name")
            if name_node:
                imports.append({"module": name_node.text.decode(), "names": [], "is_mod": True})

        # pub fn / pub struct / pub enum
        elif node.type in ("function_item", "struct_item", "enum_item", "impl_item"):
            is_pub = any(c.type == "visibility_modifier" for c in node.children)
            name_node = node.child_by_field_name("name")
            if name_node and is_pub:
                exports.append({"name": name_node.text.decode(), "type": node.type.replace("_item", ""), "line": node.start_point[0] + 1})

    return {"imports": imports, "exports": exports, "path": file_path}


def resolve_ts_import(module: str, source_file: str, repo_root: str) -> str | None:
    """Resolve a TypeScript/JS import to a file path."""
    if not module.startswith("."):
        return None  # external package

    source_dir = Path(os.path.join(repo_root, source_file)).parent
    candidate = source_dir / module

    for suffix in [".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx", "/index.js"]:
        path = str(candidate) + suffix
        if os.path.exists(path):
            return os.path.relpath(path, repo_root)
    return None


def resolve_go_import(module: str, repo_root: str, go_module: str = "") -> str | None:
    """Resolve a Go import to a directory in the repo."""
    if go_module and module.startswith(go_module):
        relative = module[len(go_module):].lstrip("/")
        candidate = os.path.join(repo_root, relative)
        if os.path.isdir(candidate):
            return relative
    return None


def _walk(node):
    """Recursively walk tree-sitter nodes."""
    yield node
    for child in node.children:
        yield from _walk(child)
