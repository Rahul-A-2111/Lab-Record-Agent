from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os

from services import (
    detect_language,
    validate_sections,
    generate_record_content,
    generate_docx,
    get_all_templates,
    parse_and_save_docx_template,
    delete_template,
    get_all_records,
    save_record,
    delete_record,
)

def load_dotenv():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"java", "py", "c", "cpp", "txt"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


@app.route("/", methods=["GET", "POST"])
def home():
    filename = None
    code = None
    file_size = None
    language = None

    if request.method == "POST":
        file = request.files.get("program")

        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            file.save(filepath)

            with open(filepath, "r", encoding="utf-8") as f:
                code = f.read()

            file_size = f"{os.path.getsize(filepath) / 1024:.1f} KB"
            language = detect_language(filename, code)

    return render_template(
        "index.html",
        filename=filename,
        code=code,
        file_size=file_size,
        language=language
    )


@app.route("/api/generate", methods=["POST"])
def generate():
    """
    API endpoint for generating collegiate record sections.
    Receives JSON payload:
    - code (str): program source code
    - filename (str, optional): program filename
    - language (str, optional): programming language
    - sections (list[str]): list of selected sections
    """
    payload = request.get_json(silent=True) or {}
    code = payload.get("code", "")
    filename = payload.get("filename")
    language = payload.get("language")
    sections = payload.get("sections", [])

    has_code = bool(code and code.strip())

    # 1. Validation
    is_valid, error_msg = validate_sections(sections, has_code)
    if not is_valid:
        return jsonify({"success": False, "error": error_msg}), 400

    # 2. Language detection
    if not language or language == "Unknown":
        language = detect_language(filename, code)

    api_key = payload.get("api_key")
    provider = payload.get("provider", "gemini")

    # 3. Generate selected sections
    generation_result = generate_record_content(
        code=code,
        language=language,
        sections=sections,
        api_key=api_key,
        provider=provider
    )

    return jsonify({
        "success": True,
        "language": language,
        "sections": generation_result.get("sections", {}),
        "engine": generation_result.get("engine", "none"),
        "note": generation_result.get("note", "")
    })


@app.route("/api/ai-status")
def ai_status():
    """
    Returns the active environment configuration (e.g. from .env file).
    """
    load_dotenv()
    gh = bool(os.environ.get("GITHUB_TOKEN", "").strip() or os.environ.get("GH_TOKEN", "").strip())
    gemini = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    groq = bool(os.environ.get("GROQ_API_KEY", "").strip())
    openai = bool(os.environ.get("OPENAI_API_KEY", "").strip())

    active = "offline"
    label = "Offline Mode"
    if gh:
        active = "github"
        label = "GitHub Models (GPT-4o-mini) Active via .env"
    elif gemini:
        active = "gemini"
        label = "Gemini LLM Active via .env"
    elif groq:
        active = "groq"
        label = "Groq Llama-3 Active via .env"
    elif openai:
        active = "openai"
        label = "OpenAI Active via .env"

    return jsonify({
        "active_provider": active,
        "label": label,
        "has_env": active != "offline"
    })


@app.route("/api/export-docx", methods=["POST"])
def export_docx():
    """
    Exports the generated and verified lab record content into a Word .docx document.
    """
    payload = request.get_json(silent=True) or {}
    sections = payload.get("sections", {})
    formatting = payload.get("formatting", {})
    images = payload.get("images", [])
    meta = payload.get("meta", {})
    filename = payload.get("filename", "Lab_Record.docx")
    export_folder = payload.get("export_folder", "").strip()

    if not filename.endswith(".docx"):
        filename += ".docx"
    filename = secure_filename(filename) or "Lab_Record.docx"

    # Default export folder is uploads/generated unless user specifies an existing local directory
    if not export_folder or not os.path.exists(export_folder):
        export_folder = os.path.join(app.config["UPLOAD_FOLDER"], "generated")

    os.makedirs(export_folder, exist_ok=True)
    full_output_path = os.path.join(export_folder, filename)

    sections_payload = payload.get("ordered_sections") or payload.get("sections", {})

    try:
        saved_path = generate_docx(
            output_path=full_output_path,
            sections=sections_payload,
            formatting=formatting,
            images=images,
            meta=meta
        )
        file_size_kb = (os.path.getsize(saved_path) / 1024.0) if os.path.exists(saved_path) else 0.0

        # Automatically record generated document into My Records history
        record_entry = save_record(
            storage_dir=app.config["UPLOAD_FOLDER"],
            filename=filename,
            title=meta.get("experiment_title") or meta.get("title") or filename,
            language=meta.get("language") or "Code",
            sections=list(sections.keys()),
            saved_path=saved_path,
            file_size_kb=file_size_kb,
            meta=meta
        )

        return jsonify({
            "success": True,
            "filename": filename,
            "saved_path": saved_path,
            "download_url": f"/api/download/{filename}",
            "record": record_entry
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/download/<filename>", methods=["GET"])
def download_docx(filename):
    filename = secure_filename(filename)
    export_folder = os.path.join(app.config["UPLOAD_FOLDER"], "generated")
    filepath = os.path.join(export_folder, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=filename)
    return jsonify({"error": "File not found"}), 404


@app.route("/api/records", methods=["GET"])
def api_records():
    """
    Returns list of all saved records in My Records.
    """
    records = get_all_records(app.config["UPLOAD_FOLDER"])
    return jsonify({"success": True, "records": records, "count": len(records)})


@app.route("/api/records/<record_id>", methods=["DELETE"])
def api_delete_record(record_id):
    """
    Deletes a record from My Records history.
    """
    success = delete_record(app.config["UPLOAD_FOLDER"], record_id)
    return jsonify({"success": success})


@app.route("/api/templates", methods=["GET"])
def api_templates():
    """
    Returns list of available formatting templates (built-in + uploaded).
    """
    templates = get_all_templates(app.config["UPLOAD_FOLDER"])
    return jsonify({"success": True, "templates": templates})


@app.route("/api/templates/upload", methods=["POST"])
def api_upload_template():
    """
    Uploads a sample Word (.docx) file and parses its formatting.
    """
    file = request.files.get("template_file")
    if not file or not file.filename:
        return jsonify({"success": False, "error": "No file uploaded"}), 400

    filename = secure_filename(file.filename)
    if not filename.lower().endswith(".docx"):
        return jsonify({"success": False, "error": "Only Microsoft Word (.docx) files can be used as templates"}), 400

    try:
        template_entry = parse_and_save_docx_template(
            file_storage=file,
            filename=filename,
            storage_dir=app.config["UPLOAD_FOLDER"]
        )
        return jsonify({"success": True, "template": template_entry})
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to parse template: {e}"}), 500


@app.route("/api/templates/<template_id>", methods=["DELETE"])
def api_delete_template(template_id):
    """
    Deletes a user-uploaded template.
    """
    success = delete_template(template_id, app.config["UPLOAD_FOLDER"])
    return jsonify({"success": success})


if __name__ == "__main__":
    app.run(debug=True)