"""
Template Handler Service.

Manages built-in university templates and custom uploaded Word (.docx) templates.
Extracts font families, font sizes, margins, and borders from user-uploaded .docx files.
"""

import os
import json
import uuid
from docx import Document

DEFAULT_TEMPLATES = [
    {
        "id": "tpl_anna_univ",
        "name": "Collegiate Standard (Anna Univ / VTU)",
        "description": "Times New Roman, 14pt Headings, 12pt Content, Double Line Border",
        "font_family": "Times New Roman",
        "heading_size": 14,
        "content_size": 12,
        "border": "double",
        "line_spacing": "1.5",
        "is_default": True,
        "filename": None,
    },
    {
        "id": "tpl_modern_tech",
        "name": "Modern Technical (Calibri / IEEE)",
        "description": "Calibri, 13pt Bold Headings, 11pt Content, Clean Single Border",
        "font_family": "Calibri",
        "heading_size": 13,
        "content_size": 11,
        "border": "single",
        "line_spacing": "1.15",
        "is_default": True,
        "filename": None,
    },
    {
        "id": "tpl_minimal",
        "name": "Minimalist Academic (Arial)",
        "description": "Arial, 13pt Headings, 11pt Content, No Page Border",
        "font_family": "Arial",
        "heading_size": 13,
        "content_size": 11,
        "border": "none",
        "line_spacing": "1.15",
        "is_default": True,
        "filename": None,
    },
]


def _get_templates_file(storage_dir: str) -> str:
    return os.path.join(storage_dir, "templates.json")


def get_all_templates(storage_dir: str) -> list[dict]:
    """
    Returns list of all templates: default built-ins + user uploaded.
    """
    templates = list(DEFAULT_TEMPLATES)
    t_file = _get_templates_file(storage_dir)

    if os.path.exists(t_file):
        try:
            with open(t_file, "r", encoding="utf-8") as f:
                user_templates = json.load(f)
                if isinstance(user_templates, list):
                    templates.extend(user_templates)
        except Exception:
            pass

    return templates


def parse_and_save_docx_template(file_storage, filename: str, storage_dir: str) -> dict:
    """
    Saves an uploaded sample Word (.docx) document, extracts its typography
    and layout formatting, and saves it into templates.json.
    """
    templates_dir = os.path.join(storage_dir, "templates")
    os.makedirs(templates_dir, exist_ok=True)

    template_id = f"tpl_user_{uuid.uuid4().hex[:8]}"
    clean_filename = f"{template_id}_{filename}"
    saved_path = os.path.join(templates_dir, clean_filename)

    file_storage.save(saved_path)

    # Extract styling from the uploaded docx
    extracted_styles = _extract_docx_styles(saved_path)

    base_name = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()

    template_entry = {
        "id": template_id,
        "name": f"{base_name} (Uploaded)",
        "description": f"Extracted from {filename}: {extracted_styles['font_family']}, {extracted_styles['heading_size']}pt / {extracted_styles['content_size']}pt",
        "font_family": extracted_styles["font_family"],
        "heading_size": extracted_styles["heading_size"],
        "content_size": extracted_styles["content_size"],
        "border": extracted_styles["border"],
        "line_spacing": extracted_styles["line_spacing"],
        "is_default": False,
        "filename": filename,
        "saved_path": saved_path,
    }

    # Persist in templates.json
    t_file = _get_templates_file(storage_dir)
    user_templates = []
    if os.path.exists(t_file):
        try:
            with open(t_file, "r", encoding="utf-8") as f:
                user_templates = json.load(f)
                if not isinstance(user_templates, list):
                    user_templates = []
        except Exception:
            user_templates = []

    user_templates.append(template_entry)

    with open(t_file, "w", encoding="utf-8") as f:
        json.dump(user_templates, f, indent=2)

    return template_entry


def delete_template(template_id: str, storage_dir: str) -> bool:
    """
    Deletes a user-uploaded template.
    """
    t_file = _get_templates_file(storage_dir)
    if not os.path.exists(t_file):
        return False

    try:
        with open(t_file, "r", encoding="utf-8") as f:
            user_templates = json.load(f)

        filtered = [t for t in user_templates if t.get("id") != template_id]
        with open(t_file, "w", encoding="utf-8") as f:
            json.dump(filtered, f, indent=2)
        return True
    except Exception:
        return False


def _extract_docx_styles(docx_path: str) -> dict:
    """
    Inspects a .docx file and extracts typography characteristics.
    """
    font_family = "Times New Roman"
    heading_size = 14
    content_size = 12
    border = "single"
    line_spacing = "1.15"

    try:
        doc = Document(docx_path)

        # 1. Check Normal Style
        try:
            normal = doc.styles["Normal"]
            if normal.font.name:
                font_family = normal.font.name
            if normal.font.size:
                content_size = round(normal.font.size.pt, 1)
        except Exception:
            pass

        # 2. Check Heading 1 Style
        try:
            h1 = doc.styles["Heading 1"]
            if h1.font.size:
                heading_size = round(h1.font.size.pt, 1)
        except Exception:
            pass

        # 3. Fallback scan through paragraphs
        for p in doc.paragraphs[:15]:
            if p.runs:
                for r in p.runs:
                    if r.font.name and not font_family:
                        font_family = r.font.name
                    if r.font.size and content_size == 12:
                        content_size = round(r.font.size.pt, 1)
                    if font_family and content_size:
                        break

        # Check section borders from XML if present
        for section in doc.sections:
            sect_xml = section._sectPr.xml
            if "w:pgBorders" in sect_xml:
                if 'w:val="double"' in sect_xml:
                    border = "double"
                else:
                    border = "single"
                break
    except Exception:
        pass

    return {
        "font_family": font_family or "Times New Roman",
        "heading_size": heading_size,
        "content_size": content_size,
        "border": border,
        "line_spacing": line_spacing,
    }
