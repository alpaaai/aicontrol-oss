import uuid
import pytest
from pathlib import Path

from enterprise.compliance.storage import LocalFileStorage


def test_write_creates_file_and_returns_path(tmp_path):
    storage = LocalFileStorage(base_dir=tmp_path)
    report_id = uuid.uuid4()
    content = b"%PDF-test content"

    path = storage.write(report_id, content, "pdf")

    assert Path(path).exists()
    assert path.endswith(".pdf")
    assert str(report_id) in path


def test_read_returns_original_bytes(tmp_path):
    storage = LocalFileStorage(base_dir=tmp_path)
    report_id = uuid.uuid4()
    content = b"# Compliance Report\n\nSome markdown content."

    path = storage.write(report_id, content, "md")
    result = storage.read(path)

    assert result == content


def test_base_dir_created_if_missing(tmp_path):
    new_dir = tmp_path / "reports" / "nested"
    storage = LocalFileStorage(base_dir=new_dir)
    report_id = uuid.uuid4()

    storage.write(report_id, b"data", "pdf")

    assert new_dir.exists()


def test_write_pdf_and_md_independently(tmp_path):
    storage = LocalFileStorage(base_dir=tmp_path)
    report_id = uuid.uuid4()

    pdf_path = storage.write(report_id, b"pdf bytes", "pdf")
    md_path = storage.write(report_id, b"md content", "md")

    assert pdf_path != md_path
    assert storage.read(pdf_path) == b"pdf bytes"
    assert storage.read(md_path) == b"md content"
