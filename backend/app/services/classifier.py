"""Document Classifier Service"""

from typing import Tuple

DOCUMENT_TYPES = [
    "FIR",
    "Investigation Report",
    "Witness Statement",
    "Forensic Report",
    "Evidence",
    "Charge Sheet",
    "Court Filing",
    "Legal Notice",
    "Judgment",
    "Other"
]

def classify_document(filename: str, extracted_text: str = "") -> Tuple[str, float]:
    """Classifies legal document based on filename heuristics and semantic content keywords. Returns: (classification_type, confidence_score)"""
    lower_name = filename.lower()
    lower_text = extracted_text.lower()

    if "fir" in lower_name or "first information report" in lower_text:
        return "FIR", 0.98
    if "forensic" in lower_name or "dna" in lower_text or "cyber forensic" in lower_text or "ballistic" in lower_text:
        return "Forensic Report", 0.96
    if "witness" in lower_name or "deposition" in lower_name or "statement of" in lower_text:
        return "Witness Statement", 0.94
    if "investigation" in lower_name or "case diary" in lower_text or "io report" in lower_name:
        return "Investigation Report", 0.93
    if "charge" in lower_name or "chargesheet" in lower_name or "section 173" in lower_text:
        return "Charge Sheet", 0.97
    if "court" in lower_name or "filing" in lower_name or "petition" in lower_text:
        return "Court Filing", 0.92
    if "judgment" in lower_name or "order" in lower_name or "hon'ble court" in lower_text:
        return "Judgment", 0.95
    if "notice" in lower_name or "summons" in lower_text:
        return "Legal Notice", 0.91
    if "evidence" in lower_name or "seizure" in lower_text or "malkhana" in lower_text:
        return "Evidence", 0.94

    return "Other", 0.75
