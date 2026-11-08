"""The factory's pipeline as one package — `story-gate.py` and `factory-cli.py` beside it are its entry points.

Built the way it teaches (WP-152; the map and the glossaries in the plugin's `docs/`):

    building_blocks   the markers of DCA's tactical patterns and ports, outside every context
    delivery/         the bounded context delivery: backlog, decisions, delivery, description, cost — in layers
    spec/             the bounded context spec: what holds, merged from a story's delta; `spec/api` its open host
    sharedkernel/     what the contexts read alike: a project's markdown
    web/              the host across the contexts: the page and its server
    infrastructure/   the composition root: each use case with its adapters

and beside them the version stamp `contract` (`CONTRACT`, `VERSION`), which `factory.sh` and an installed copy of any
release read by its name. No other module sits at the top.

stdlib only.
"""

import os
import sys
import types


def _bytecode_by_content() -> None:
    """The package's bytecode, kept under its source's digest instead of its path. The factory runs from many copies
    of one package — `.agents/factory/` in each project and in each story's worktree, a copy wherever symlinks are
    unavailable — and Python keeps bytecode per path: every new copy compiled every module it imported again, and the
    cache grew by a tree per copy. Keyed by content, a copy finds what any other copy compiled. Only where an entry
    point has put the bytecode in the user's cache (`sys.pycache_prefix`), and only for the package's own files."""
    prefix = sys.pycache_prefix
    if not prefix:
        return
    import hashlib
    import importlib.machinery
    import marshal

    root = os.path.dirname(os.path.abspath(__file__))
    store = os.path.join(prefix, "by-content", f"{sys.implementation.cache_tag}-o{sys.flags.optimize}")

    class ByContent(importlib.machinery.SourceFileLoader):
        def get_code(self, fullname: str) -> types.CodeType:
            path = self.get_filename(fullname)
            source = self.get_data(path)
            digest = hashlib.sha256(source).hexdigest()
            kept = os.path.join(store, digest[:2], digest)
            try:
                with open(kept, "rb") as handle:
                    code = marshal.loads(handle.read())
                if isinstance(code, types.CodeType):
                    return _named(code, path)                  # a traceback names this copy, not the one that compiled
            except (OSError, ValueError, EOFError, TypeError):
                pass
            code = self.source_to_code(source, path)
            if not sys.dont_write_bytecode:
                try:
                    os.makedirs(os.path.dirname(kept), exist_ok=True)
                    written = f"{kept}.{os.getpid()}"             # processes in parallel: each writes its own, then swaps
                    with open(written, "wb") as handle:
                        handle.write(marshal.dumps(code))
                    os.replace(written, kept)
                except OSError:
                    pass
            return code

    def _named(code: types.CodeType, path: str) -> types.CodeType:
        return code.replace(co_filename=path, co_consts=tuple(
            _named(const, path) if isinstance(const, types.CodeType) else const for const in code.co_consts))

    sources = (ByContent, importlib.machinery.SOURCE_SUFFIXES)

    def finder(path: str) -> importlib.machinery.FileFinder:
        folder = os.path.abspath(path)
        if folder != root and not folder.startswith(root + os.sep):
            raise ImportError("not the factory's package")
        return importlib.machinery.FileFinder(path, sources)

    sys.path_hooks.insert(0, finder)
    for known in [p for p in sys.path_importer_cache if os.path.abspath(p).startswith(root)]:
        del sys.path_importer_cache[known]


_bytecode_by_content()


def utf8_streams() -> None:
    """The lines carry `—` and `→`; a Windows console's code page cannot encode `→`, and the print raises. And every
    line ends in `\n` alone: on Windows a text stream writes `\r\n`, and whoever reads the output — the runner,
    factory.sh's `$(…)` — would keep the `\r` on the last field of every line ("plan\r" names no stage)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", newline="\n")
