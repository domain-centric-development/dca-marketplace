"""The domain types a story's change touched: its changed production files in the domain layer, each named by its
file. Where the domain layer is, the profile says (`layer.domain`, blank-separated globs from the project root); in a
project with the method's configuration (`dca.profile.yaml`) it is every folder named `domain` (or `<Project>.Domain`),
the layer the method names. Without either, the factory knows no layer and names no type."""

from __future__ import annotations

import fnmatch
import os
import typing

#: The method's domain layer, where its configuration is there and the profile names none.
METHOD_DOMAIN_LAYER = ("domain",)
#: Files that hold no type of their own, by their stem.
NO_TYPE = {"package-info", "module-info", "__init__", "index", "mod", "lib", "assemblyinfo", "globalusings"}
#: Extensions of source files a type lives in.
SOURCES = (".java", ".kt", ".cs", ".fs", ".py", ".ts", ".js", ".go", ".rs", ".scala", ".swift", ".rb", ".php")


def domain_globs(cwd: str, profile: typing.Mapping[str, typing.Any]) -> typing.Optional[typing.List[str]]:
    """The profile's `layer.domain` globs — or None where it names none (the method's layer then, if any)."""
    value = str(profile.get("layer.domain", "") or "").strip()
    return value.split() if value else None


def in_domain(path: str, globs: typing.Optional[typing.List[str]], method: bool) -> bool:
    """Whether a path lies in the domain layer: matched by a glob of the profile, else — in a project of the method —
    under a folder named like the method's domain layer."""
    if globs is not None:
        return any(fnmatch.fnmatch(path, glob) for glob in globs)
    if not method:
        return False
    return any(part.lower() in METHOD_DOMAIN_LAYER or part.lower().rsplit(".", 1)[-1] in METHOD_DOMAIN_LAYER
               for part in path.split("/")[:-1])


def is_test(path: str) -> bool:
    """A test source, in any stack's habit: a folder whose name begins with `test` or ends with `tests`, or a file
    named as a test."""
    parts = path.split("/")
    stem = os.path.splitext(parts[-1])[0]
    return (any(p.lower().startswith("test") or p.lower().endswith("tests") for p in parts[:-1])
            or stem.endswith(("Test", "Tests", "Spec", "_test", ".test", ".spec")) or stem.startswith("test_"))


def changed_domain_types(cwd: str, paths: typing.Iterable[str],
                         profile: typing.Mapping[str, typing.Any]) -> typing.List[typing.Tuple[str, str]]:
    """(type name, path) for every changed production file in the domain layer that holds a type."""
    globs = domain_globs(cwd, profile)
    method = os.path.isfile(os.path.join(cwd, "dca.profile.yaml"))
    found = []
    for path in sorted(set(p.replace("\\", "/") for p in paths)):
        stem, extension = os.path.splitext(os.path.basename(path))
        if extension.lower() not in SOURCES or stem.lower() in NO_TYPE or is_test(path):
            continue
        if in_domain(path, globs, method) and os.path.isfile(os.path.join(cwd, path)):
            found.append((stem, path))
    return found
