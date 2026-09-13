"""
Resume upload: PDF or plain text in, resume text out.

The browser sends the file as base64 JSON (no multipart dependency). PDFs are
read with pypdf; scanned PDFs have no text layer and get a clear error rather
than an empty resume.
"""
import base64
import binascii
import io

MAX_BYTES = 5 * 1024 * 1024


def parse_resume(filename: str, data_base64: str) -> str:
    """Returns the resume text. Raises ValueError with a user-facing message on bad input."""
    try:
        raw = base64.b64decode(data_base64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("The upload was corrupted. Try the file again.")
    if len(raw) > MAX_BYTES:
        raise ValueError("Resume file is over 5 MB.")

    name = filename.lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader

        try:
            text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
        except Exception as exc:  # noqa: BLE001 - encrypted or malformed PDFs raise many types
            raise ValueError(f"Couldn't read that PDF ({type(exc).__name__}). Try exporting it again.")
    elif name.endswith((".txt", ".md")):
        text = raw.decode("utf-8", errors="replace")
    else:
        # ponytail: PDF and text only; add DOCX via python-docx if users ask for it
        raise ValueError("Upload a PDF or .txt resume.")

    text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if len(text) < 20:
        raise ValueError("No text found in that file. Scanned PDFs need to be exported with text.")
    return text


if __name__ == "__main__":
    b64 = lambda data: base64.b64encode(data).decode()  # noqa: E731
    assert parse_resume("cv.txt", b64(b"Jordan Rivera\nPython, FastAPI  \n")) == "Jordan Rivera\nPython, FastAPI"

    # A minimal valid one-page PDF with a real xref table (byte offsets computed), text in Helvetica.
    content = b"BT /F1 18 Tf 20 100 Td (Jordan Rivera Python FastAPI) Tj ET"
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 400 144]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length " + str(len(content)).encode() + b">>stream\n" + content + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    pdf, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    pdf += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    pdf += f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref_at}\n%%EOF".encode()
    assert "Jordan Rivera Python FastAPI" in parse_resume("cv.pdf", b64(pdf))

    for bad_name, bad_data, message in [("cv.docx", b64(b"x" * 50), "PDF or .txt"), ("cv.txt", "***", "corrupted"),
                                        ("cv.txt", b64(b"short"), "No text")]:
        try:
            parse_resume(bad_name, bad_data)
            raise AssertionError(f"{bad_name} should have failed")
        except ValueError as exc:
            assert message in str(exc), exc
    print("resume parse self-check passed")
