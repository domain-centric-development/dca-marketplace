"""The installed pipeline by content: the files the install puts into `.agents/factory/`, and one SHA-256 over their
digests — the stamp's `sha256:` line, which the install writes and the runner compares before every gate it runs."""

from __future__ import annotations

import hashlib
import os
import typing

STAMP = ".agents/factory/gate.installed"
#: The files the install puts into .agents/factory/, in the stamp's order; a name ending in `/` is a folder — the
#: package, the workflow's files: every module (`.py`), stage and rule (`.md`) in it and below.
PIPELINE_FILES = ("story-gate.py", "factory-cli.py", "observe.py", "factory.sh", "dca_factory/", "workflow/")
#: What the gate runs on: alike by content in the runner's folder and the gate's, the gate may run in the runner.
GATE_FILES = ("story-gate.py", "dca_factory/", "workflow/")


def hashing() -> bool:
    """FACTORY_SHA256=none forces the names-only path, which is how that path is exercised by a test."""
    return os.environ.get("FACTORY_SHA256", "") != "none"


def file_sha(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return ""


def package_modules(folder: str) -> typing.List[str]:
    """Every module of the package under <folder>, its subpackages' too — and every file of the workflow beside it —
    by its path below the folder with `/`, in the order the install's hash lists them (the C locale's, as Python
    sorts)."""
    found: typing.List[str] = []
    for top, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        below = os.path.relpath(top, folder).replace(os.sep, "/")
        found += [name if below == "." else f"{below}/{name}" for name in files if name.endswith((".py", ".md"))]
    return sorted(found)


def pipeline_digest(folder: str, names: typing.Sequence[str] = PIPELINE_FILES) -> typing.Optional[str]:
    """One SHA-256 over the digests of <names> in <folder>, a missing one named as missing; None where no hash is
    taken (FACTORY_SHA256=none)."""
    if not hashing():
        return None
    listing = ""
    for name in names:
        path = os.path.join(folder, name)
        if name.endswith("/"):
            if not os.path.isdir(path):
                listing += f"missing  {name}\n"
                continue
            for module in package_modules(path):
                listing += f"{file_sha(os.path.join(path, module))}  {name}{module}\n"
        elif os.path.isfile(path):
            listing += f"{file_sha(path)}  {name}\n"
        else:
            listing += f"missing  {name}\n"
    return hashlib.sha256(listing.encode("utf-8")).hexdigest()
