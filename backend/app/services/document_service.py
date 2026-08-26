"""PDF/DOCX extraction service shared by upload and review agents."""

import io


def extract_document_text(filename: str, content: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if name.endswith(".docx"):
        from docx import Document

        document = Document(io.BytesIO(content))
        return "\n".join(p.text for p in document.paragraphs if p.text.strip()).strip()
    raise ValueError("仅支持 PDF 或 DOCX 文件")
