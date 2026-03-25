"""
Modelos SQLAlchemy — MVP 1 + MVP 2.
Tablas: documents, pages, blocks, patches, jobs, document_profiles.
"""

from app.models.document import Document
from app.models.page import Page
from app.models.block import Block
from app.models.patch import Patch
from app.models.job import Job
from app.models.style_profile import DocumentProfile

__all__ = ["Document", "Page", "Block", "Patch", "Job", "DocumentProfile"]
