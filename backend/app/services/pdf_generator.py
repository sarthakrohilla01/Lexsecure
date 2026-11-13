"""Minimal valid-PDF builder (standard library only)."""

import textwrap


def build_pdf_bytes(title: str, body: str) -> bytes:
    """Renders title + body text into a minimal valid single-font PDF."""
    safe_title = _sanitize(title)
    lines = [safe_title, ""]
    for paragraph in body.split("\n"):
        paragraph = _sanitize(paragraph.strip())
        if not paragraph:
            lines.append("")
        else:
            lines.extend(textwrap.wrap(paragraph, width=95) or [""])

    per_page = 44
    pages = [lines[i:i + per_page] for i in range(0, len(lines), per_page)] or [[]]

    objects: list[bytes] = []
    page_obj_nums = []
    num = 3
    for _ in pages:
        page_obj_nums.append((num, num + 1))
        num += 2
    font_num = num

    content_streams = []
    for page_lines in pages:
        content_streams.append(_page_stream(page_lines))

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{p} 0 R" for p, _ in page_obj_nums)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())

    for (_, content_num), stream in zip(page_obj_nums, content_streams):
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_num} 0 R >> >> "
            f"/Contents {content_num} 0 R >>".encode()
        )
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body_bytes in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode())
        out.extend(body_bytes)
        out.extend(b"\nendobj\n")
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF".encode()
    )
    return bytes(out)


def _page_stream(lines: list) -> bytes:
    parts = ["BT", "/F1 16 Tf", "50 792 Td", "18 TL"]
    first = True
    for line in lines:
        if first and line:
            parts.append(f"({line}) Tj")
            parts.append("/F1 12 Tf")
            first = False
        elif line:
            parts.append("T*")
            parts.append(f"({line}) Tj")
        else:
            parts.append("T*")
    parts.append("ET")
    return "\n".join(parts).encode("latin-1")


def _sanitize(text: str) -> str:
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return text.encode("latin-1", errors="replace").decode("latin-1")
