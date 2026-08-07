"""Benchmark-only deterministic diagnostics.

The benchmark package does not generate story meaning.  It records the
provenance and structural signals needed to review Codex-generated prose
without turning a heuristic into a literary score.
"""

from novel_authoring.benchmark.real_ab import (
    anti_leak_audit,
    compare_prose,
    template_diagnostics,
)

__all__ = ["anti_leak_audit", "compare_prose", "template_diagnostics"]
