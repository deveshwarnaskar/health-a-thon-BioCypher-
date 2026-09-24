"""Reporting adapters (Gate 10N).

Provides deterministic PDF and PNG renderers conforming to IDocumentRenderer.
"""

from .report_renderer import ClinicalPdfRenderer, PatientPdfRenderer, PngChartRenderer

__all__ = [
    "ClinicalPdfRenderer",
    "PatientPdfRenderer",
    "PngChartRenderer",
]