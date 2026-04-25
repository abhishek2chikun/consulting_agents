"""M&A consultant — V2 stub (M8.1).

V1 ships only the skeleton: a one-node graph that writes a
placeholder ``final_report.md`` explaining V1 limits and immediately
marks the run completed. The full M&A pipeline (deal-sourcing,
target list, valuation triangulation, synergy modelling, IC memo)
lands in V2.

Selecting "M&A" in the UI dispatches to :func:`run_ma_stub` instead
of the market-entry framing → research → synthesis → audit graph.
No questionnaire is produced; the run finishes in seconds with a
single artifact.
"""

from __future__ import annotations

from .runner import run_ma_stub

__all__ = ["run_ma_stub"]
