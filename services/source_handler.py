"""
Source Code Handling Service.

Handles language detection, source code normalization, and structural inspection.
"""

import os
import re

EXTENSION_MAP = {
    "java": "Java",
    "py": "Python",
    "c": "C",
    "cpp": "C++",
    "cc": "C++",
    "cxx": "C++",
    "h": "C/C++ Header",
    "hpp": "C++ Header",
    "txt": "Plain Text",
}


def detect_language(filename: str | None = None, code: str | None = None) -> str:
    """
    Detects the programming language from filename extension or code syntax.
    """
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[1].lower()
        if ext in EXTENSION_MAP and ext != "txt":
            return EXTENSION_MAP[ext]

    if not code:
        return "Unknown"

    # Heuristic content detection for pasted code or .txt files
    code_sample = code[:2000]

    # Java patterns
    if re.search(r"\bpublic\s+(?:class|interface|enum)\b", code_sample) or \
       "System.out.print" in code_sample or \
       "public static void main" in code_sample or \
       re.search(r"\bimport\s+java\.", code_sample):
        return "Java"

    # Python patterns
    if re.search(r"^\s*def\s+\w+\s*\(", code, re.MULTILINE) or \
       re.search(r"^\s*import\s+\w+", code, re.MULTILINE) or \
       re.search(r"^\s*from\s+\w+\s+import", code, re.MULTILINE) or \
       "if __name__ == '__main__':" in code_sample or \
       'if __name__ == "__main__":' in code_sample:
        return "Python"

    # C++ patterns
    if "#include <iostream>" in code_sample or \
       "#include <vector>" in code_sample or \
       "std::cout" in code_sample or \
       "using namespace std;" in code_sample or \
       "cout <<" in code_sample or \
       "cin >>" in code_sample:
        return "C++"

    # C patterns
    if "#include <stdio.h>" in code_sample or \
       "#include <stdlib.h>" in code_sample or \
       "printf(" in code_sample or \
       "scanf(" in code_sample or \
       re.search(r"\bint\s+main\s*\(\s*(?:void)?\s*\)", code_sample):
        return "C"

    if filename and filename.lower().endswith(".txt"):
        return "Plain Text"

    return "General"


def extract_code_meta(code: str, language: str) -> dict:
    """
    Extracts structural metadata (classes, methods, comments) from the source code.
    Used for objective analysis and algorithm step derivation without hallucinations.
    """
    if not code:
        return {
            "classes": [],
            "functions": [],
            "imports": [],
            "comments": [],
            "line_count": 0,
            "subject": "program",
        }

    lines = code.splitlines()
    classes = []
    functions = []
    imports = []
    comments = []

    # Check top comments for program title/objective
    for line in lines[:15]:
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("#"):
            comment_text = stripped.lstrip("/#* -").strip()
            if comment_text and len(comment_text) > 3:
                comments.append(comment_text)
        elif stripped.startswith("/*"):
            comment_text = stripped.lstrip("/* -").rstrip("*/").strip()
            if comment_text and len(comment_text) > 3:
                comments.append(comment_text)

    # Class and function regex patterns
    if language == "Python":
        classes = re.findall(r"^\s*class\s+([A-Za-z0-9_]+)", code, re.MULTILINE)
        functions = re.findall(r"^\s*def\s+([A-Za-z0-9_]+)", code, re.MULTILINE)
        imports = re.findall(r"^\s*(?:from\s+([A-Za-z0-9_.]+)|import\s+([A-Za-z0-9_.]+))", code, re.MULTILINE)
        imports = [i[0] or i[1] for i in imports if i[0] or i[1]]
    else:
        # Java / C / C++
        classes = re.findall(r"\bclass\s+([A-Za-z0-9_]+)", code)
        # Function/method patterns
        raw_funcs = re.findall(r"(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+([A-Za-z0-9_]+)\s*\([^)]*\)\s*(?:\{|;)", code)
        # Filter common keywords
        ignored = {"if", "for", "while", "switch", "catch"}
        functions = [f for f in raw_funcs if f not in ignored]

    # Deduplicate while preserving order
    classes = list(dict.fromkeys(classes))
    functions = list(dict.fromkeys(functions))

    # Derive primary subject
    subject = "program"
    if comments:
        # e.g., "Binary Search Tree implementation" -> use first descriptive comment
        subject = comments[0]
    elif classes:
        # e.g. "BinarySearchTree" -> split CamelCase to "Binary Search Tree"
        cc = classes[0]
        split_name = re.sub(r"([A-Z])", r" \1", cc).strip()
        subject = f"{split_name} ({cc})"
    elif functions:
        main_funcs = [f for f in functions if f.lower() not in ("main", "__init__")]
        if main_funcs:
            fn = main_funcs[0]
            split_name = re.sub(r"([A-Z])", r" \1", fn).replace("_", " ").strip()
            subject = f"{split_name} algorithm"

    return {
        "classes": classes,
        "functions": functions,
        "imports": imports,
        "comments": comments,
        "line_count": len(lines),
        "subject": subject,
    }
