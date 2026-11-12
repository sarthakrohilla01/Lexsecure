"""Generate synthetic sample legal documents for testing upload and OCR pipelines."""

import os

SAMPLES = {
    "FIR_CASE_001.txt": """FIRST INFORMATION REPORT (Under Section 154 Cr.P.C. / Section 173 BNSS)
Police Station: Cyber Crime Division, Special Cell, New Delhi
FIR Number: 042/2026 | Date: 2026-08-20
Complainant: Axis Digital Payments Risk Monitoring Group
Acts and Sections: Section 66C, 66D IT Act 2000; Section 318, 319 BNS 2023.
Summary: Unauthorized malware banking trojan intrusion and automated mule fund routing.
Investigating Officer: Inspector Rajesh Kumar (NCRB-INV-4091)
""",
    "Forensic_Report_001.txt": """CENTRAL FORENSIC SCIENCE LABORATORY (CFSL) - CYBER FORENSICS REPORT
Forensic Case File: CFSL/CYBER/2026/089 | Reference: FIR 042/2026
Examining Expert: Dr. Ananya Sharma, Senior Forensic Scientist
1. Evidence Received: Exhibit Q-1 Western Digital 2TB NVMe SSD; Exhibit Q-2 OnePlus 12 Smartphone.
2. Hash Verification: Physical Image SHA-256: 3919307f4dbd42b109e25bb...
3. Findings: Active Gh0stRAT Trojan payload identified. Telegram mule communications recovered.
4. Cryptographic conclusion: Hardware devices conclusively linked to malicious SIM-swap routing.
""",
    "Witness_Statement_001.txt": """WITNESS DEPOSITION STATEMENT (Under Section 180 BNSS)
Witness Name: Mr. Alok Tandon (CISO)
Deposition on Oath:
At 02:14 AM on 18 August 2026, abnormal API token anomalies were detected across the cloud gateway.
Emergency credential revocation was initiated at 02:35 AM.
Perimeter firewall logs transferred to CFSL.
""",
    "Charge_Sheet_001.txt": """IN THE COURT OF CHIEF METROPOLITAN MAGISTRATE, PATIALA HOUSE COURTS, NEW DELHI
FINAL POLICE REPORT / CHARGE SHEET (Under Section 193 BNSS)
State vs. Sameer Saxena
Charges Framed: Section 66C, 66D IT Act 2000; Section 318(4), 319(2) BNS 2023.
Evidentiary digital chain of custody preserved in LexSecure.
"""
}

out_dir = os.path.dirname(os.path.abspath(__file__))
for name, content in SAMPLES.items():
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
        f.write(content)

print("[✓] Sample legal documents created.")
