"""Compatibility wrappers for Think9 fine-tuning dataset export."""

from sqlalchemy.orm import Session

from app.services.feedback.think9_model import build_dataset, export_filename


def build_rows(session: Session) -> list[dict]:
    rows, _manifest = build_dataset(session)
    return rows


__all__ = ["build_rows", "export_filename"]
