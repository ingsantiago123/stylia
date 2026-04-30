"""
Modelos SQLAlchemy — MVP 1 + MVP 2 + Plan v4.
Tablas: documents, pages, blocks, patches, jobs, document_profiles, llm_usage,
        section_summaries, term_registry, correction_batches,
        document_global_context, llm_audit_log.
"""

from app.models.document import Document
from app.models.page import Page
from app.models.block import Block
from app.models.patch import Patch
from app.models.job import Job
from app.models.style_profile import DocumentProfile
from app.models.llm_usage import LlmUsage
from app.models.section_summary import SectionSummary
from app.models.term_registry import TermRegistry
from app.models.correction_batch import CorrectionBatch
from app.models.paragraph_location import ParagraphLocation
from app.models.document_global_context import DocumentGlobalContext
from app.models.llm_audit_log import LlmAuditLog

__all__ = [
    "Document", "Page", "Block", "Patch", "Job",
    "DocumentProfile", "LlmUsage", "SectionSummary", "TermRegistry",
    "CorrectionBatch", "ParagraphLocation",
    "DocumentGlobalContext", "LlmAuditLog",
]
