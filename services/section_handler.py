"""
Record Section Handling Service.

Handles section definitions, selection validation, and section ordering.
"""

# Canonical order of sections matching collegiate lab record structure
ALL_SECTIONS = ["AIM", "ALGORITHM", "PROGRAM", "OUTPUT", "RESULT"]

# Sections synthesized via AI / algorithmic parsing
AI_GENERATED_SECTIONS = {"AIM", "ALGORITHM", "RESULT"}

# Sections requiring raw user source code
SOURCE_REQUIRED_SECTIONS = {"AIM", "ALGORITHM", "PROGRAM", "RESULT"}


def validate_sections(sections: list, has_code: bool) -> tuple[bool, str | None]:
    """
    Validates selected sections and code prerequisites.

    Rules:
    - At least one section must be selected.
    - If the user selects PROGRAM, there must be source code available.
    - If AI generation sections (AIM, ALGORITHM, RESULT) are selected, source code must be available.
    """
    if not sections or not isinstance(sections, list):
        return False, "At least one section must be selected to proceed."

    # Validate against known section identifiers
    invalid_sections = [s for s in sections if s not in ALL_SECTIONS]
    if invalid_sections:
        return False, f"Unknown section(s) specified: {', '.join(invalid_sections)}"

    # Rule: If user selects PROGRAM, source code must be present
    if "PROGRAM" in sections and not has_code:
        return False, "Source code is required when the PROGRAM section is selected. Please upload or paste your program."

    # Rule: AI generation requires source code
    ai_selected = [s for s in sections if s in AI_GENERATED_SECTIONS]
    if ai_selected and not has_code:
        return False, f"Source code is required to generate {', '.join(ai_selected)}. Please upload or paste your program."

    return True, None


def normalize_sections(sections: list) -> list[str]:
    """
    Filters and preserves standard laboratory canonical sequence.
    """
    selected_set = set(sections)
    return [s for s in ALL_SECTIONS if s in selected_set]
