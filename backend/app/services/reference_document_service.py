"""Upload and storage helpers for platform-managed reference documents."""

import os

from flask import current_app
from flask_login import current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Document
from app.services.document_service import (
    calculate_sha256,
    extract_text,
    is_allowed_file,
    make_storage_filename,
)


def save_reference_document(file_storage, title, *, commit=True):
    if not file_storage or not file_storage.filename:
        raise ValueError("Choose a document to upload.")

    original_filename = secure_filename(file_storage.filename)
    if not original_filename:
        raise ValueError("The uploaded filename is invalid.")

    if not is_allowed_file(original_filename, current_app.config["ALLOWED_EXTENSIONS"]):
        raise ValueError("Only PDF, DOCX and TXT documents are supported.")

    file_bytes = file_storage.read()
    if not file_bytes:
        raise ValueError("The uploaded document is empty.")

    extracted = extract_text(original_filename, file_bytes)
    storage_name = make_storage_filename(original_filename)
    storage_path = os.path.join(current_app.config["UPLOAD_FOLDER"], storage_name)
    with open(storage_path, "wb") as stored_file:
        stored_file.write(file_bytes)

    document = Document(
        user_id=current_user.user_id,
        workspace_id=None,
        visibility_scope="platform",
        title=(title or os.path.splitext(original_filename)[0]).strip()[:255],
        original_filename=original_filename[:255],
        storage_path=storage_name,
        file_type=os.path.splitext(original_filename)[1].lower().lstrip("."),
        document_type="reference",
        extracted_text=extracted,
        file_hash=calculate_sha256(file_bytes),
        processing_status="processed",
    )
    db.session.add(document)
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return document
