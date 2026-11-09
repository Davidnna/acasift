import hashlib
import io
import re
import uuid
from pathlib import Path

import fitz
from docx import Document as DocxDocument
from werkzeug.utils import secure_filename


def file_extension(filename):
    return Path(filename or "").suffix.lower().lstrip(".")


def is_allowed_file(filename, allowed_extensions):
    return file_extension(filename) in allowed_extensions


def calculate_sha256(file_bytes):
    return hashlib.sha256(file_bytes).hexdigest()


def extract_text(filename, file_bytes):
    extension = file_extension(filename)

    if extension == "pdf":
        try:
            with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
                text = "\n".join(page.get_text("text") for page in pdf)
        except Exception as exc:
            raise ValueError("The PDF could not be opened or is damaged.") from exc

    elif extension == "docx":
        try:
            document = DocxDocument(io.BytesIO(file_bytes))
            parts = [paragraph.text for paragraph in document.paragraphs]
            for table in document.tables:
                for row in table.rows:
                    parts.append(" | ".join(cell.text for cell in row.cells))
            text = "\n".join(parts)
        except Exception as exc:
            raise ValueError("The Word document could not be opened or is damaged.") from exc

    elif extension == "txt":
        try:
            text = file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = file_bytes.decode("utf-8", errors="replace")

    else:
        raise ValueError("Only PDF, DOCX and TXT files are supported.")

    text = re.sub(r"\x00", "", text)
    if not text.strip():
        raise ValueError(
            "No extractable text was found. Scanned PDFs and image-only documents are not supported in this version."
        )
    return text


def make_storage_filename(original_filename):
    extension = file_extension(original_filename)
    safe_stem = secure_filename(Path(original_filename).stem)[:40] or "document"
    return f"{uuid.uuid4().hex}_{safe_stem}.{extension}"
