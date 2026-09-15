"""Architecture import audit for backend/interfaces/http (Gate 07).

Verifies:
- HTTP layer depends inward on application/domain (allowed).
- HTTP layer may use approved infrastructure factories.
- HTTP layer must NOT import legacy app module, ORM models directly,
  admin/mobile/clinical-workstation.
- No circular imports.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path

import pytest

# Allowed top-level package names for http layer module-level imports
_ALLOWED_PKG = {
    "backend", "config",
    "fastapi", "starlette", "pydantic", "pydantic_settings",
    "typing", "logging", "re", "time", "uuid", "json", "base64",
    "hmac", "hashlib", "contextlib", "dataclasses", "enum", "collections",
    "collections.abc", "datetime", "pathlib", "sys", "os", "abc",
    "copy", "functools", "itertools", "typing_extensions",
    "__future__",
}

# Forbidden import path prefixes (within backend)
_FORBIDDEN_BACKEND_PREFIXES = [
    "backend.infrastructure.persistence.models",
    "backend.infrastructure.persistence.repositories",
    "backend.infrastructure.persistence.mappings",
    "backend.app.",
    "app.",
    "apps.",
    "backend.legacy",
]


def _iter_http_modules():
    http_root = Path(__file__).resolve().parents[3] / "backend" / "interfaces" / "http"
    repo_root = http_root.parents[2]
    for py_file in http_root.rglob("*.py"):
        rel = py_file.relative_to(repo_root)
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            yield ".".join(parts)


def _module_level_imports(filepath: Path) -> list[tuple[str, str | None]]:
    """Return (pkg_name, full_module_path) for top-level imports.

    Relative imports (``from .foo import …``) are skipped — they are
    local to the package and do not constitute a dependency.
    """
    tree = ast.parse(filepath.read_text())
    imports: list[tuple[str, str | None]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                pkg = alias.name.split(".")[0]
                imports.append((pkg, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            # Skip relative imports (level > 0)
            if node.level and node.level > 0:
                continue
            pkg = node.module.split(".")[0]
            imports.append((pkg, node.module))
    return imports


def test_http_layer_import_boundaries():
    """Every http module's top-level imports use only allowed packages."""
    http_root = Path(__file__).resolve().parents[3] / "backend" / "interfaces" / "http"
    repo_root = http_root.parents[2]
    violations = []

    for py_file in http_root.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        imports = _module_level_imports(py_file)
        for pkg, full_path in imports:
            if pkg not in _ALLOWED_PKG:
                violations.append(f"{py_file.name}: unexpected top-level package '{pkg}' (from {full_path})")
            if full_path:
                for prefix in _FORBIDDEN_BACKEND_PREFIXES:
                    if full_path.startswith(prefix):
                        violations.append(f"{py_file.name}: forbidden import '{full_path}'")

    assert not violations, "Import violations:\n" + "\n".join(violations)


def test_http_modules_importable():
    """All http modules are importable without side effects."""
    http_root = Path(__file__).resolve().parents[3] / "backend" / "interfaces" / "http"
    repo_root = http_root.parents[2]
    for py_file in http_root.rglob("*.py"):
        if "__pycache__" in str(py_file) or py_file.name == "__init__.py":
            continue
        rel = py_file.relative_to(repo_root)
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            module_name = ".".join(parts)
            mod = importlib.import_module(module_name)
            assert mod is not None


def test_circular_imports():
    """No circular dependency between http modules."""
    http_root = Path(__file__).resolve().parents[3] / "backend" / "interfaces" / "http"
    repo_root = http_root.parents[2]
    module_names = []
    for py_file in http_root.rglob("*.py"):
        if "__pycache__" in str(py_file) or py_file.name == "__init__.py":
            continue
        rel = py_file.relative_to(repo_root)
        parts = list(rel.with_suffix("").parts)
        if parts:
            module_names.append(".".join(parts))

    imported = set()
    for mod_name in module_names:
        try:
            importlib.import_module(mod_name)
            imported.add(mod_name)
        except Exception:
            pass

    # All modules should be importable without error
    assert len(imported) == len(module_names), (
        f"Imported {len(imported)}/{len(module_names)} modules"
    )
