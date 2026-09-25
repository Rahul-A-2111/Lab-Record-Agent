"""
Services Package for Lab Record Agent.
"""

from .source_handler import detect_language, extract_code_meta
from .section_handler import (
    ALL_SECTIONS,
    AI_GENERATED_SECTIONS,
    SOURCE_REQUIRED_SECTIONS,
    validate_sections,
    normalize_sections,
)
from .ai_generator import generate_record_content
from .document_generator import generate_docx
from .template_handler import (
    get_all_templates,
    parse_and_save_docx_template,
    delete_template,
)
from .record_manager import (
    get_all_records,
    save_record,
    delete_record,
)

__all__ = [
    "detect_language",
    "extract_code_meta",
    "ALL_SECTIONS",
    "AI_GENERATED_SECTIONS",
    "SOURCE_REQUIRED_SECTIONS",
    "validate_sections",
    "normalize_sections",
    "generate_record_content",
    "generate_docx",
    "get_all_templates",
    "parse_and_save_docx_template",
    "delete_template",
    "get_all_records",
    "save_record",
    "delete_record",
]
