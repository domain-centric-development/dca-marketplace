"""Spec's open host service: what delivery calls, in the published language of the spec — a criterion as an entry
{key, rule, form, lines, tests} (and `feature` where a context's reading adds it), a delta as the plan's `## Spec
delta` reads, problems as sentences. The rules behind it are the model's (`LivingSpec`); the files are read and
written by the files adapter."""

from ..adapter.outgoing.files.spec_files import (  # noqa: F401 — the published reading and writing of the files
    context_files, context_folder, entry, feature_name, GLOSSARY_FILE, glossary_features,
    JOURNEYS_FILE, journeys_path, lint_context, lint_text, parse_spec, read_context, read_spec, render_spec,
    SCENARIOS_FILE, scenarios_path, trim)
from ..domain.model.criterion import CONTEXT_WIDE  # noqa: F401
from .published import (  # noqa: F401 — the published language and the rules behind it
    delta_problems, derived, merge, merge_context, place_name, placement_lines, placement_problems, read_delta,
    renamed_rules, rule_problems, selectors_of, story_entries, touches)

__all__ = [
    "context_files", "context_folder", "entry", "feature_name", "GLOSSARY_FILE", "glossary_features", "JOURNEYS_FILE",
    "journeys_path", "lint_context", "lint_text", "parse_spec", "read_context", "read_spec", "render_spec",
    "SCENARIOS_FILE", "scenarios_path", "trim", "CONTEXT_WIDE", "delta_problems", "derived", "merge", "merge_context",
    "place_name", "placement_lines", "placement_problems", "read_delta", "renamed_rules", "rule_problems", "selectors_of",
    "story_entries", "touches"]
