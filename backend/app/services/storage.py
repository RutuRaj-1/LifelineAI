"""Report storage. Files are always written locally (needed for OCR); optionally mirrored to Firebase Storage."""
import re
import uuid
from pathlib import Path

from ..config import get_settings


def save_report_file(patient_id: int, filename: str, data: bytes) -> tuple[Path, str]:
    s = get_settings()
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[-80:] or "report"
    rel = f"patients/{patient_id}/{uuid.uuid4().hex[:10]}_{safe}"
    path = Path(s.upload_dir) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    ref = f"local://{rel}"
    if s.storage_backend == "firebase" and s.firebase_storage_bucket:
        try:
            bucket = _firebase_bucket()
            bucket.blob(rel).upload_from_filename(str(path))
            ref = f"gs://{s.firebase_storage_bucket}/{rel}"
        except Exception:  # noqa: BLE001 - keep the local copy if the mirror fails
            pass
    return path, ref


def local_path(ref: str) -> Path | None:
    return Path(get_settings().upload_dir) / ref.removeprefix("local://") if ref.startswith("local://") else None


def _firebase_bucket():
    import firebase_admin
    from firebase_admin import credentials, storage

    s = get_settings()
    if not firebase_admin._apps:
        options = {"storageBucket": s.firebase_storage_bucket}
        if s.firebase_project_id:
            options["projectId"] = s.firebase_project_id
        if s.firebase_credentials_path and Path(s.firebase_credentials_path).exists():
            cred = credentials.Certificate(s.firebase_credentials_path)
            firebase_admin.initialize_app(cred, options)
        else:
            firebase_admin.initialize_app(options=options)
    return storage.bucket()


def firebase_signed_url(ref: str) -> str:
    from datetime import timedelta

    s = get_settings()
    try:
        blob_path = ref.split("/", 3)[3] if ref.startswith("gs://") else ref
        blob = _firebase_bucket().blob(blob_path)
        return blob.generate_signed_url(expiration=timedelta(minutes=10))
    except Exception:
        # Fallback to direct public Firebase Storage URL format
        raw_path = ref.split("/", 3)[3] if ref.startswith("gs://") else ref
        encoded_path = raw_path.replace("/", "%2F")
        bucket = s.firebase_storage_bucket or "lifeline-ai-cdabc.firebasestorage.app"
        return f"https://firebasestorage.googleapis.com/v0/b/{bucket}/o/{encoded_path}?alt=media"
