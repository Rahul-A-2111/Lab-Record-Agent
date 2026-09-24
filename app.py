from flask import Flask, render_template, request
from werkzeug.utils import secure_filename
import os

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

    return render_template(
        "index.html",
        filename=filename,
        code=code,
        file_size=file_size
    )


if __name__ == "__main__":
    app.run(debug=True)