"""
Analiz metnini Word (.docx) veya Excel (.xlsx) dosyasına aktarma.
"""
import re
import tempfile

from docx import Document
import openpyxl


def create_docx(title: str, content: str) -> str:
    doc = Document()
    doc.add_heading(title, level=1)
    for line in content.split("\n"):
        line = line.strip()
        if line:
            doc.add_paragraph(line)
    tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    tmp.close()
    doc.save(tmp.name)
    return tmp.name


def _split_row(line: str):
    if "|" in line:
        parts = [c.strip() for c in line.split("|") if c.strip()]
        if parts:
            return parts
    parts = re.split(r"\s{2,}|\t", line.strip())
    parts = [p for p in parts if p]
    return parts if len(parts) > 1 else [line.strip()]


def create_xlsx(title: str, content: str) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = (title or "Analiz")[:31]
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        ws.append(_split_row(line))
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    wb.save(tmp.name)
    return tmp.name
