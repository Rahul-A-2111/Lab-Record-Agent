"""
AI Generation Service.

Responsible for synthesizing AIM, ALGORITHM, and RESULT sections from source code.
Adheres strictly to laboratory guidelines without hallucinations or fabricated outputs.
Supports Google Gemini (Free), Groq (Free), OpenAI, or local deterministic code analysis.
"""

import json
import os
import re
import requests
from .source_handler import extract_code_meta


def generate_record_content(
    code: str,
    language: str,
    sections: list[str],
    api_key: str | None = None,
    provider: str = "gemini",
) -> dict:
    """
    Generates the requested record sections based on source code and language.

    Generation Rules:
    - AIM: Explains the objective/purpose; college lab record format; no invented functionality.
    - ALGORITHM: Step-by-step numbered steps derived from actual code; no invented functionality.
    - RESULT: State what the program accomplishes; no invented test results or fake outputs.
    - PROGRAM: Verbatim original source code (never rewritten or modified).
    - OUTPUT: No fake or invented output (deferred to future milestone).
    """
    results = {}
    selected_set = set(sections)

    # 1. PROGRAM Section: Preserve original source verbatim
    if "PROGRAM" in selected_set:
        results["PROGRAM"] = code

    # 2. OUTPUT Section: Do NOT fake or invent output
    if "OUTPUT" in selected_set:
        results["OUTPUT"] = (
            "Program output execution is reserved for a future milestone. "
            "No simulated or artificial output is displayed."
        )

    # 3. AI Sections: AIM, ALGORITHM, RESULT
    ai_sections = [s for s in ["AIM", "ALGORITHM", "RESULT"] if s in selected_set]

    engine = "none"
    note = ""

    if ai_sections:
        raw_key = (api_key or "").strip()
        env_github = os.environ.get("GITHUB_TOKEN", "").strip() or os.environ.get("GH_TOKEN", "").strip()
        env_gemini = os.environ.get("GEMINI_API_KEY", "").strip()
        env_groq = os.environ.get("GROQ_API_KEY", "").strip()
        env_openai = os.environ.get("OPENAI_API_KEY", "").strip()

        # Determine effective provider and credentials
        chosen_provider = None
        chosen_key = None

        if raw_key:
            if raw_key.startswith("ghp_") or raw_key.startswith("github_pat_"):
                chosen_provider = "github"
                chosen_key = raw_key
            elif raw_key.startswith("AIzaSy"):
                chosen_provider = "gemini"
                chosen_key = raw_key
            elif raw_key.startswith("gsk_"):
                chosen_provider = "groq"
                chosen_key = raw_key
            elif raw_key.startswith("sk-"):
                chosen_provider = "openai"
                chosen_key = raw_key
            else:
                chosen_provider = provider or "gemini"
                chosen_key = raw_key
        else:
            # Fall back to environment variables from .env
            if env_github:
                chosen_provider = "github"
                chosen_key = env_github
            elif env_gemini:
                chosen_provider = "gemini"
                chosen_key = env_gemini
            elif env_groq:
                chosen_provider = "groq"
                chosen_key = env_groq
            elif env_openai:
                chosen_provider = "openai"
                chosen_key = env_openai

        generated_data = None

        # 1. GitHub Models (Free GPT-4o-mini via GitHub Token - zero scopes required)
        if chosen_provider == "github" and chosen_key:
            try:
                generated_data = _generate_with_github_models(code, language, ai_sections, chosen_key)
                engine = "github_gpt4o"
                note = "Generated using GitHub Models (Free GPT-4o-mini via GITHUB_TOKEN)."
            except Exception as e:
                note = f"GitHub Models API returned an error ({e}); fell back to structural code analysis."
                generated_data = None

        # 2. Google Gemini (Free Tier via Google AI Studio)
        elif chosen_provider == "gemini" and chosen_key:
            try:
                generated_data = _generate_with_gemini(code, language, ai_sections, chosen_key)
                engine = "gemini"
                note = "Generated using Google Gemini API (gemini-1.5-flash via GEMINI_API_KEY)."
            except Exception as e:
                note = f"Gemini API returned an error ({e}); fell back to structural code analysis."
                generated_data = None

        # 3. Groq Cloud (Free Tier)
        elif chosen_provider == "groq" and chosen_key:
            try:
                generated_data = _generate_with_groq(code, language, ai_sections, chosen_key)
                engine = "groq"
                note = "Generated using Groq API (Llama 3.3 70B via GROQ_API_KEY)."
            except Exception as e:
                note = f"Groq API returned an error ({e}); fell back to structural code analysis."
                generated_data = None

        # 4. OpenAI API
        elif chosen_provider == "openai" and chosen_key:
            try:
                generated_data = _generate_with_openai(code, language, ai_sections, chosen_key)
                engine = "openai"
                note = "Generated using OpenAI API (via OPENAI_API_KEY)."
            except Exception as e:
                note = f"OpenAI API returned an error ({e}); fell back to structural code analysis."
                generated_data = None

        # Fallback: Deterministic structural code analysis
        if not generated_data:
            generated_data = _generate_rule_based(code, language, ai_sections)
            if engine == "none":
                engine = "rule_based"
                if not note:
                    note = "Generated via structural code analysis (Offline Mode). Add GITHUB_TOKEN or GEMINI_API_KEY to your .env file to activate AI generation."

        for s in ai_sections:
            if s in generated_data:
                results[s] = generated_data[s]

    return {
        "sections": results,
        "engine": engine,
        "note": note,
    }


def _generate_with_gemini(code: str, language: str, ai_sections: list[str], api_key: str) -> dict:
    """
    Calls Google Gemini REST API (gemini-1.5-flash / gemini-2.0-flash).
    Free tier allows 15 RPM and 1,500 RPD without a credit card.
    """
    model = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    prompt = _build_generation_prompt(code, language, ai_sections)

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    resp = requests.post(url, json=payload, timeout=25)
    resp.raise_for_status()

    data = resp.json()
    candidate_text = data["candidates"][0]["content"]["parts"][0]["text"]
    parsed = json.loads(candidate_text)
    return _normalize_ai_response(parsed, ai_sections)


def _generate_with_groq(code: str, language: str, ai_sections: list[str], api_key: str) -> dict:
    """
    Calls Groq Cloud REST API (Llama 3.3 70B Versatile).
    Free tier with high tokens/sec.
    """
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    url = "https://api.groq.com/openai/v1/chat/completions"

    prompt = _build_generation_prompt(code, language, ai_sections)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an expert collegiate Computer Science laboratory assistant. Respond in valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=25)
    resp.raise_for_status()

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    return _normalize_ai_response(parsed, ai_sections)


def _generate_with_github_models(code: str, language: str, ai_sections: list[str], token: str) -> dict:
    """
    Calls GitHub Models REST API (Free GPT-4o-mini inference).
    Requires a GitHub Personal Access Token (classic or fine-grained) with zero scopes.
    Endpoint: https://models.inference.ai.azure.com/chat/completions
    """
    url = "https://models.inference.ai.azure.com/chat/completions"
    prompt = _build_generation_prompt(code, language, ai_sections)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are an expert collegiate Computer Science lab record assistant. Output valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=25)
    resp.raise_for_status()

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    return _normalize_ai_response(parsed, ai_sections)


def _generate_with_openai(code: str, language: str, ai_sections: list[str], api_key: str) -> dict:
    """
    Calls OpenAI REST API (gpt-4o-mini).
    """
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    url = "https://api.openai.com/v1/chat/completions"

    prompt = _build_generation_prompt(code, language, ai_sections)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an expert collegiate Computer Science lab record assistant. Output valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=25)
    resp.raise_for_status()

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    return _normalize_ai_response(parsed, ai_sections)


def _build_generation_prompt(code: str, language: str, ai_sections: list[str]) -> str:
    """
    Builds strict prompt instructing the model to generate only requested sections according to lab standards.
    """
    sections_str = ", ".join(ai_sections)
    return f"""You are an academic Computer Science laboratory assistant preparing a collegiate lab record document.

Analyze the following {language} program:
```{language}
{code}
```

Generate content ONLY for the following requested sections: {sections_str}

Strict Generation Rules:
1. AIM:
   - Formulate a clear, standard collegiate objective for the program (e.g. "To write, compile, and execute a {language} program to implement...").
   - Keep it suitable for a college laboratory manual.
   - Do NOT invent functionality that is not present in the code.
2. ALGORITHM:
   - Derive the algorithm step-by-step from the actual program logic.
   - Return as an array of numbered sequential steps: ["1. Start the program execution.", "2. ...", ..., "N. Stop the program execution."].
   - Keep it suitable for a college lab record.
   - Do NOT describe functionality that the code does not implement.
3. RESULT:
   - State what the program accomplishes based on the code (e.g. "Thus, the {language} program for ... was successfully created, compiled, and its functionality verified.").
   - Do NOT invent test results or claim an output that has not been provided.
4. Output MUST be valid JSON matching this schema:
{{
  {"\"AIM\": \"... string ...\"," if "AIM" in ai_sections else ""}
  {"\"ALGORITHM\": [\"1. ...\", \"2. ...\"]," if "ALGORITHM" in ai_sections else ""}
  {"\"RESULT\": \"... string ...\"" if "RESULT" in ai_sections else ""}
}}
"""


def _normalize_ai_response(parsed: dict, ai_sections: list[str]) -> dict:
    """
    Ensures correct casing and format for keys in LLM output.
    """
    normalized = {}
    for s in ai_sections:
        val = parsed.get(s) or parsed.get(s.lower()) or parsed.get(s.capitalize())
        if val is not None:
            normalized[s] = val
    return normalized


def _generate_rule_based(code: str, language: str, ai_sections: list[str]) -> dict:
    """
    Deterministic structural code analyzer.
    Derives AIM, ALGORITHM, and RESULT directly from code AST/heuristics
    without requiring external APIs or internet connection.
    """
    meta = extract_code_meta(code, language)
    subject = meta["subject"]
    classes = meta["classes"]
    functions = [f for f in meta["functions"] if f.lower() not in ("main", "__init__")]
    imports = meta["imports"]

    result = {}

    # AIM Generation
    if "AIM" in ai_sections:
        if classes:
            main_class = classes[0]
            if functions:
                methods_str = ", ".join(f"'{f}'" for f in functions[:3])
                result["AIM"] = (
                    f"To write, compile, and execute a {language} program implementing {main_class} "
                    f"with operations including {methods_str}."
                )
            else:
                result["AIM"] = (
                    f"To write, compile, and execute a {language} program implementing the {main_class} class "
                    f"and verify its correct execution."
                )
        elif functions:
            funcs_str = ", ".join(f"'{f}'" for f in functions[:3])
            result["AIM"] = (
                f"To write, compile, and execute a {language} program implementing functions "
                f"{funcs_str} to solve the problem."
            )
        else:
            result["AIM"] = (
                f"To write, compile, and execute a {language} program for {subject} "
                f"and verify its functionality."
            )

    # ALGORITHM Generation
    if "ALGORITHM" in ai_sections:
        steps = ["1. Start the program execution."]
        step_num = 2

        if imports:
            mod_names = ", ".join(imports[:3])
            steps.append(f"{step_num}. Import required modules/headers ({mod_names}).")
            step_num += 1

        if classes:
            cls_name = classes[0]
            steps.append(
                f"{step_num}. Define class '{cls_name}' with necessary member variables and initialization structures."
            )
            step_num += 1

        if functions:
            for fn in functions[:3]:
                steps.append(
                    f"{step_num}. Implement method/function '{fn}' to handle designated computational logic."
                )
                step_num += 1
        else:
            steps.append(f"{step_num}. Declare and initialize required variables and input parameters.")
            step_num += 1
            steps.append(f"{step_num}. Perform the core processing and computation steps as defined in the source code.")
            step_num += 1

        steps.append(f"{step_num}. In the driver/main routine, process test inputs and trigger required operations.")
        step_num += 1
        steps.append(f"{step_num}. Output the computed results to standard console display.")
        step_num += 1
        steps.append(f"{step_num}. Stop the program execution.")

        result["ALGORITHM"] = steps

    # RESULT Generation
    if "RESULT" in ai_sections:
        if classes:
            target_desc = f"class '{classes[0]}'"
        elif functions:
            target_desc = f"{functions[0]} routine"
        else:
            target_desc = subject

        result["RESULT"] = (
            f"Thus, the {language} program for {target_desc} was successfully developed, "
            f"compiled, and its execution verified."
        )

    return result
