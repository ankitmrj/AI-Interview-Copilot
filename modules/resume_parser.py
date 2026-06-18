
from __future__ import annotations

from pathlib import Path
from typing import Union, IO


def extract_text_from_file(uploaded_file: Union[IO[bytes], IO[str]]) -> str:
    name = getattr(uploaded_file, "name", "").lower()

    if name.endswith(".txt"):
        data = uploaded_file.read()
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="ignore")
        return str(data)

    if name.endswith(".pdf"):
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(uploaded_file)
            texts = []
            for page in reader.pages:
                texts.append(page.extract_text() or "")
            return "\n".join(texts).strip()
        except Exception as e:
            raise RuntimeError(f"PDF parsing failed: {e}")

    if name.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(uploaded_file)
            return "\n".join(p.text for p in doc.paragraphs).strip()
        except Exception as e:
            raise RuntimeError(f"DOCX parsing failed: {e}")

    raise ValueError("Unsupported resume file type. Use PDF, TXT, or DOCX.")
