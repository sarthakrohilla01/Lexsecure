"""Zero-Width Steganography Engine (The "Leak Tracker")

Embeds an invisible watermark into text evidence at download time, binding the
copy to the downloading officer (email + user id), the document version and a
timestamp.

Frame layout: START_MARKER, then one zero-width character per bit
(U+200B = 0, U+200C = 1), then END_MARKER. The frame is appended to the end of
the text, so the visible content is untouched and the stored vault bytes are
never modified — the watermark exists only on the download copy.

The payload is JSON with a magic tag and a CRC-32 checksum, so a partially
corrupted frame is reported instead of being misattributed to the wrong
officer.
"""

import json
import zlib
from typing import List, Dict, Any

BIT_0 = '\u200b'
BIT_1 = '\u200c'

START_MARKER = '\u2060\u200d\u2060'
END_MARKER = '\u2060\u200b\u2060'

MAGIC = "LEXSECURE_LEAK_TRACE_V1"


def _bytes_to_bits(data: bytes) -> str:
    """Byte-aligned binary string — every byte contributes exactly 8 bits (leading zeros preserved, unlike bin(int)[2:])."""
    return ''.join(f'{b:08b}' for b in data)


def _bits_to_bytes(bits: str) -> bytes:
    """Inverse of _bytes_to_bits. Raises ValueError on malformed input."""
    if len(bits) % 8 != 0:
        raise ValueError("bit string length is not byte-aligned")
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))


def generate_watermark_string(email: str, user_id: int, document_id: int,
                              version: int, timestamp: str) -> str:
    """Builds the invisible watermark frame for one download event."""
    core = {
        "magic": MAGIC,
        "email": email,
        "uid": user_id,
        "doc": document_id,
        "ver": version,
        "ts": timestamp,
    }
    core["crc"] = f"{zlib.crc32(json.dumps(core, sort_keys=True).encode('utf-8')):08x}"
    bits = _bytes_to_bits(json.dumps(core, sort_keys=True).encode('utf-8'))
    return START_MARKER + ''.join(BIT_1 if b == '1' else BIT_0 for b in bits) + END_MARKER


def inject_watermark_bytes(file_bytes: bytes, email: str, user_id: int,
                           document_id: int, version: int, timestamp: str) -> bytes:
    """Returns download bytes with the invisible watermark appended. ONLY call this with text content: the frame is UTF-8 zero-width chars with no visible marker, so rendered text is pixel-identical."""
    text = file_bytes.decode('utf-8')
    frame = generate_watermark_string(email, user_id, document_id, version, timestamp)
    return (text + frame).encode('utf-8')


def is_text_like(data: bytes) -> bool:
    """Heuristic: is this payload renderable text (safe to watermark)?"""
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return False
    if '\x00' in text:
        return False
    printable = sum(1 for ch in text if ch.isprintable() or ch in '\n\r\t')
    return bool(text.strip()) and printable / max(1, len(text)) > 0.9


def _decode_frame(frame_bits: str) -> Dict[str, Any]:
    payload = json.loads(_bits_to_bytes(frame_bits).decode('utf-8'))
    if not isinstance(payload, dict) or payload.get("magic") != MAGIC:
        raise ValueError("unrecognized watermark")
    core = {k: v for k, v in payload.items() if k != "crc"}
    expected = f"{zlib.crc32(json.dumps(core, sort_keys=True).encode('utf-8')):08x}"
    if payload.get("crc") != expected:
        raise ValueError("checksum mismatch — watermark was altered")
    return payload


def extract_watermark_bytes(watermarked_bytes: bytes) -> dict:
    """Scans file bytes for leak-tracker frames. Returns every decodable watermark (a file shared onward can accumulate several) plus the most recent one as the primary suspect."""
    try:
        text = watermarked_bytes.decode('utf-8', errors='ignore')
    except Exception:
        return {"is_valid": False, "error": "Could not decode file bytes."}

    found: List[Dict[str, Any]] = []
    corrupted = 0
    search_from = 0
    while True:
        start = text.find(START_MARKER, search_from)
        if start == -1:
            break
        end = text.find(END_MARKER, start + len(START_MARKER))
        if end == -1:
            corrupted += 1
            break
        seq = text[start + len(START_MARKER):end]
        if seq and all(ch == BIT_0 or ch == BIT_1 for ch in seq):
            try:
                found.append(_decode_frame(''.join(
                    '1' if ch == BIT_1 else '0' for ch in seq)))
            except Exception:
                corrupted += 1
        else:
            corrupted += 1
        search_from = end + len(END_MARKER)

    if not found:
        return {
            "is_valid": False,
            "error": ("Incomplete or corrupted watermark found — no verifiable "
                      "leak-tracker frame survived." if corrupted
                      else "No watermark found in this file."),
        }

    primary = found[-1]
    return {
        "is_valid": True,
        "email": primary["email"],
        "user_id": primary["uid"],
        "document_id": primary["doc"],
        "version": primary["ver"],
        "timestamp": primary["ts"],
        "chain_length": len(found),
        "chain": [
            {"email": f["email"], "user_id": f["uid"], "timestamp": f["ts"]}
            for f in found
        ],
    }
