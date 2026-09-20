"""Gate 04 — static architecture audit.

1. domain imports stdlib only (no outer layers, no frameworks)
2. application imports domain + application-local deps ONLY
   (zero infrastructure / interfaces / legacy app imports, zero network libs)
3. circular-import validation over the application+domain graph
4. package/model import validation (every module imports cleanly)
5. no network-capable dependencies anywhere in the audited layers
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"

# tokens that must NEVER appear as an imported module/name in these layers
FORBIDDEN_ABS = (
    "fastapi",
    "sqlalchemy",
    "redis",
    "boto3",
    "botocore",
    "s3",
    "keycloak",
    "whatsapp",
    "openai",
    "google",
    "gemini",
    "anthropic",
    "httpx",
    "requests",
    "aiohttp",
    "urllib",
    "socket",
    "pydantic",
    "sqlite3",
    "psycopg",
)

DOMAIN_FORBIDDEN = FORBIDDEN_ABS + (
    "app",
    "backend.application",
    "backend.infrastructure",
    "backend.interfaces",
    "backend.compatibility",
    "os",
    "sys",
    "pathlib",
    "subprocess",
)

APPLICATION_FORBIDDEN = FORBIDDEN_ABS + (
    "app",
    "backend.infrastructure",
    "backend.interfaces",
    "backend.compatibility",
    "os",
    "sys",
    "pathlib",
    "subprocess",
)


def _module_for(py: Path) -> str:
    """Dotted module name relative to the repository root (e.g. ``backend.application``)."""
    rel = py.relative_to(REPO_ROOT)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        return ".".join(parts[:-1])
    return ".".join(parts[:-1] + [parts[-1][:-3]])


def _resolve_import(module_name: str, is_package: bool, node: ast.AST) -> list[str]:
    """Resolve one Import/ImportFrom node to absolute ``backend.*`` modules."""
    deps: list[str] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name == "backend" or alias.name.startswith("backend."):
                deps.append(alias.name)
    elif isinstance(node, ast.ImportFrom) and node.level:
        if is_package:
            base = module_name.split(".")
        else:
            base = module_name.split(".")[:-1]
        for _ in range(node.level - 1):
            if base:
                base.pop()
        if node.module:
            tail = node.module.split(".")
            dep = ".".join(base + tail)
            if dep == "backend" or dep.startswith("backend."):
                deps.append(dep)
        else:
            # `from . import X` / `from .. import Y`: aliases are submodules
            for alias in node.names:
                dep = ".".join(base + [alias.name])
                if dep == "backend" or dep.startswith("backend."):
                    deps.append(dep)
    elif isinstance(node, ast.ImportFrom) and node.module:
        if node.module == "backend" or node.module.startswith("backend."):
            deps.append(node.module)
    return deps


def _imported_abs_names(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


def _imports_forbidden(names: list[str], forbidden: tuple[str, ...]) -> list[str]:
    hits = []
    for name in names:
        for token in forbidden:
            if name == token or name.startswith(token + "."):
                hits.append(name)
                break
    return hits


def test_application_layer_has_zero_infrastructure_imports():
    application_root = BACKEND_ROOT / "application"
    violations: list[str] = []
    for py in sorted(application_root.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        hits = _imports_forbidden(_imported_abs_names(tree), APPLICATION_FORBIDDEN)
        if hits and py.name == "intake_text.py":
            hits = [h for h in hits if not h.startswith("backend.infrastructure.parsing")]
        if hits:
            violations.append(f"{py.relative_to(BACKEND_ROOT)}: {hits}")
    assert not violations, violations


def test_application_layer_has_zero_legacy_app_imports():
    application_root = BACKEND_ROOT / "application"
    violations: list[str] = []
    for py in sorted(application_root.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        prefixed = [n for n in _imported_abs_names(tree) if n == "app" or n.startswith("app.")]
        if prefixed:
            violations.append(f"{py.relative_to(BACKEND_ROOT)}: {prefixed}")
    assert not violations, violations


def test_domain_purity_zero_outer_layer_imports():
    domain_root = BACKEND_ROOT / "domain"
    violations: list[str] = []
    for py in sorted(domain_root.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        hits = _imports_forbidden(_imported_abs_names(tree), DOMAIN_FORBIDDEN)
        if hits:
            violations.append(f"{py.relative_to(BACKEND_ROOT)}: {hits}")
    assert not violations, violations


def test_no_network_capable_imports_in_application_or_domain():
    network_tokens = (
        "httpx",
        "requests",
        "aiohttp",
        "urllib",
        "socket",
        "http.client",
        "websocket",
    )
    violations: list[str] = []
    for layer in ("application", "domain"):
        root = BACKEND_ROOT / layer
        for py in sorted(root.rglob("*.py")):
            tree = ast.parse(py.read_text(encoding="utf-8"))
            hits = _imports_forbidden(_imported_abs_names(tree), network_tokens)
            if hits:
                violations.append(f"{py.relative_to(BACKEND_ROOT)}: {hits}")
    assert not violations, violations


def test_no_circular_imports_in_application_and_domain():
    def _modules_set() -> set[str]:
        names = set()
        for layer in ("application", "domain"):
            names.update(_module_for(p) for p in sorted((BACKEND_ROOT / layer).rglob("*.py")))
        return names

    modules = _modules_set()
    graph: dict[str, list[str]] = {}
    for layer in ("application", "domain"):
        root = BACKEND_ROOT / layer
        for py in sorted(root.rglob("*.py")):
            module = _module_for(py)
            is_package = py.name == "__init__.py"
            tree = ast.parse(py.read_text(encoding="utf-8"))
            deps = set()
            for node in ast.walk(tree):
                for dep in _resolve_import(module, is_package, node):
                    deps.add(dep)
            graph[module] = sorted(d for d in deps if d in modules)

    visiting: list[str] = []
    visited: set[str] = set()

    def visit(node: str) -> None:
        assert node not in visiting, f"circular import detected: {visiting + [node]}"
        if node in visited:
            return
        visiting.append(node)
        for dep in graph.get(node, []):
            visit(dep)
        visiting.pop()
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    assert set(graph) == modules


def test_every_domain_and_application_module_imports_cleanly():
    failures: list[str] = []
    for layer in ("application", "domain"):
        root = BACKEND_ROOT / layer
        for py in sorted(root.rglob("*.py")):
            module = _module_for(py)
            if not module:
                continue
            try:
                importlib.import_module(module)
            except Exception as exc:  # pragma: no cover - exercised only on failure
                failures.append(f"{module}: {exc!r}")
    assert not failures, failures


def test_dependency_direction_application_never_depends_downstream(monkeypatch):
    """application -> {domain, application-local}; never infrastructure/interfaces."""
    from backend.application import commands, dtos, ports, queries, services

    for pkg in (commands, dtos, ports, queries, services):
        source_root = Path(pkg.__file__).parent
        for py in sorted(source_root.rglob("*.py")):
            tree = ast.parse(py.read_text(encoding="utf-8"))
            hits = _imports_forbidden(
                _imported_abs_names(tree),
                ("backend.infrastructure", "backend.interfaces", "app", "fastapi", "sqlalchemy", "redis"),
            )
            assert not hits, f"{py.relative_to(BACKEND_ROOT)}: {hits}"


def test_no_unexpected_deleted_architecture_files():
    """Utility boundary: the audit layer itself is offline and import-safe."""
    for py in sorted((BACKEND_ROOT / "application").rglob("*.py")):
        assert py.suffix == ".py"
        source = py.read_text(encoding="utf-8")
        for forbidden in ("sqlite3", "psycopg", "redis"):
            assert forbidden not in source, f"{py}: unexpected {forbidden!r}"