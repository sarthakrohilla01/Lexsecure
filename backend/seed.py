"""LexSecure Database & System Seeder"""

import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.session import Base, engine, SessionLocal
from app.models.user import User, UserRole, Department
from app.models.case import Case, CaseAssignment
from app.models.document import Document
from app.security.jwt import hash_password
from app.security.mfa import generate_secret
from app.security.pki import generate_key_pair
from app.security.crypto import encrypt_secret
from app.services.doc_processor import process_and_store_document
from app.services.pdf_generator import build_pdf_bytes
from app.blockchain.ledger_service import ensure_genesis_block
from app.utils.time import utcnow

SAMPLE_PASSWORD = "LexSecure@2026"

USERS_SEED = [
    {
        "email": "investigator@lexsecure.local",
        "full_name": "Inspector Rajesh Kumar",
        "role": UserRole.INVESTIGATOR,
        "department": Department.CYBER_CRIME.value,
        "badge_number": "NCRB-INV-4091"
    },
    {
        "email": "forensic@lexsecure.local",
        "full_name": "Dr. Ananya Sharma",
        "role": UserRole.FORENSIC_EXPERT,
        "department": Department.FORENSIC_LAB.value,
        "badge_number": "CFSL-FOR-8821"
    },
    {
        "email": "legal@lexsecure.local",
        "full_name": "Advocate Vikram Mehta",
        "role": UserRole.LEGAL_OFFICER,
        "department": Department.PROSECUTION.value,
        "badge_number": "DOP-LEG-1044"
    },
    {
        "email": "supervisor@lexsecure.local",
        "full_name": "SP Sunita Verma (IPS)",
        "role": UserRole.SUPERVISOR,
        "department": Department.WOMEN_SAFETY.value,
        "badge_number": "NCRB-SUP-0012"
    },
    {
        "email": "admin@lexsecure.local",
        "full_name": "Chief Security Architect (SysAdmin)",
        "role": UserRole.ADMINISTRATOR,
        "department": Department.ADMINISTRATION.value,
        "badge_number": "MHA-SEC-9900"
    }
]

CASES_SEED = [
    {
        "id": "CASE-2026-001",
        "title": "State vs. Syndicate Alpha (Cyber Financial Fraud & Identity Theft)",
        "description": "Multi-jurisdictional investigation into orchestrated SIM-swapping, OTP intercept banking trojan, and unauthorized laundering across 4 states. Primary suspect apprehended in New Delhi.",
        "department": Department.CYBER_CRIME.value,
        "status": "UNDER_INVESTIGATION",
        "classification": "RESTRICTED",
        "incident_date": utcnow() - timedelta(days=25)
    },
    {
        "id": "CASE-2026-002",
        "title": "State vs. Unknown (Targeted Cyberstalking & Deepfake Harassment)",
        "description": "Investigation into synthetic identity creation, digital defamation, and AI-generated deepfake media harassment targeting executive personnel in New Delhi.",
        "department": Department.WOMEN_SAFETY.value,
        "status": "UNDER_INVESTIGATION",
        "classification": "CONFIDENTIAL",
        "incident_date": utcnow() - timedelta(days=12)
    },
    {
        "id": "CASE-2026-003",
        "title": "State vs. Advanced Persistent Group (Power Grid SCADA Intrusion)",
        "description": "Critical infrastructure cyber reconnaissance incident detected on regional telemetry nodes. Top secret classification restricted to national incident response teams.",
        "department": Department.CYBER_CRIME.value,
        "status": "ACTIVE",
        "classification": "SECRET",
        "incident_date": utcnow() - timedelta(days=5)
    }
]

SAMPLE_DOCUMENTS = [
    {
        "case_id": "CASE-2026-001",
        "filename": "FIR_CASE_001.pdf",
        "title": "First Information Report (FIR No. 042/2026)",
        "doc_type": "FIR",
        "classification": "RESTRICTED",
        "uploader_email": "investigator@lexsecure.local",
        "content": (
            "FIRST INFORMATION REPORT (Under Section 154 Cr.P.C. / Section 173 BNSS)\n"
            "Police Station: Cyber Crime Division, Special Cell, New Delhi\n"
            "FIR Number: 042/2026 | Date of Registration: 2026-08-20\n\n"
            "Complainant: Axis Digital Payments Risk Monitoring Group\n"
            "Acts and Sections: Section 66C, 66D Information Technology Act 2000; Section 318, 319 Bharatiya Nyaya Sanhita (BNS) 2023.\n\n"
            "Brief Description of Offence: An unauthorized intrusion occurred wherein automated scripts spoofed banking credentials, "
            "intercepted SMS-based multi-factor tokens, and siphoned INR 1.84 Crores into 14 mule cryptocurrency accounts. "
            "Suspect IP logs traced to residential broadband in Rohini Sector 11. Initial electronic evidence seized under Section 105 BNSS.\n\n"
            "Investigating Officer: Inspector Rajesh Kumar (NCRB-INV-4091)"
        )
    },
    {
        "case_id": "CASE-2026-001",
        "filename": "Forensic_Report_001.pdf",
        "title": "CFSL Cyber Forensic Laboratory Examination Report",
        "doc_type": "Forensic Report",
        "classification": "CONFIDENTIAL",
        "uploader_email": "forensic@lexsecure.local",
        "content": (
            "CENTRAL FORENSIC SCIENCE LABORATORY (CFSL) - CYBER FORENSICS DIVISION\n"
            "Forensic Case File: CFSL/CYBER/2026/089 | Reference: FIR 042/2026\n"
            "Examining Expert: Dr. Ananya Sharma, Senior Forensic Scientist\n\n"
            "1. Evidence Received:\n"
            "   - Exhibit Q-1: One Western Digital 2TB NVMe SSD (Serial: WDS200T3X0E)\n"
            "   - Exhibit Q-2: One OnePlus 12 Android Smartphone (IMEI: 864910048192019)\n\n"
            "2. Forensic Methodology:\n"
            "   Hardware write-blocker (Tableau T8u) utilized during forensic bit-stream imaging. "
            "Physical image SHA-256 verified identical before and after acquisition.\n\n"
            "3. Key Forensic Findings:\n"
            "   a) Reverse engineering of Exhibit Q-1 revealed an active deployment of 'Gh0stRAT' remote administration tool.\n"
            "   b) Telegram session caches contained active negotiation logs with handle '@crypto_mule_laundering'.\n"
            "   c) Memory dump analysis recovered the private keys corresponding to Ethereum wallet 0x71C...4e89 containing 42.8 ETH.\n\n"
            "4. Conclusion: Exhibits Q-1 and Q-2 conclusively establish direct orchestration of fraudulent credential harvesting."
        )
    },
    {
        "case_id": "CASE-2026-001",
        "filename": "Witness_Statement_001.pdf",
        "title": "Deposition of Key Witness (Senior IT Infrastructure Manager)",
        "doc_type": "Witness Statement",
        "classification": "RESTRICTED",
        "uploader_email": "investigator@lexsecure.local",
        "content": (
            "WITNESS DEPOSITION STATEMENT (Recorded under Section 180 BNSS / 161 CrPC)\n"
            "Witness Name: Mr. Alok Tandon | Age: 41 | Occupation: Chief Information Security Officer\n"
            "Location: Cyber Cell Office, Mandir Marg, New Delhi\n\n"
            "Statement on Oath:\n"
            "'I state that on 18th August 2026 at approximately 02:14 AM IST, our Security Operations Center (SOC) "
            "triggered an automated tier-3 alarm regarding abnormal API token calls emanating from VPN node AP-SOUTH-1. "
            "I personally initiated the emergency credential revocation sequence at 02:35 AM. "
            "I observed unauthorized SSH tunnels routing from internal IP 10.240.12.8 to an external offshore command server. "
            "All perimeter firewall syslog archives have been securely transferred to CFSL on write-once media.'\n\n"
            "Recorded by: Inspector Rajesh Kumar, IO"
        )
    },
    {
        "case_id": "CASE-2026-001",
        "filename": "Charge_Sheet_001.pdf",
        "title": "Final Police Report / Charge Sheet (Section 193 BNSS)",
        "doc_type": "Charge Sheet",
        "classification": "CONFIDENTIAL",
        "uploader_email": "legal@lexsecure.local",
        "requires_dual_auth": False,
        "content": (
            "IN THE COURT OF CHIEF METROPOLITAN MAGISTRATE, PATIALA HOUSE COURTS, NEW DELHI\n"
            "Police Report under Section 193 Bharatiya Nagarik Suraksha Sanhita 2023\n"
            "Case Crime No: FIR 042/2026 | Police Station: Cyber Crime New Delhi\n\n"
            "Accused Person: Sameer Saxena s/o Ramesh Saxena (In Judicial Custody)\n"
            "Charges Framed: Section 66C, 66D IT Act 2000; Section 318(4), 319(2), 61(2) Bharatiya Nyaya Sanhita 2023.\n\n"
            "Summary of Prosecution Evidence:\n"
            "The digital chain of custody has been preserved cryptographically in LexSecure. "
            "The CFSL report establishes forensic correlation between the accused's hardware address and the unauthorized bank transfers. "
            "Prayer: The Hon'ble Court is prayed to take cognizance and issue process against the accused."
        )
    },
    {
        "case_id": "CASE-2026-001",
        "filename": "Confidential_Informant.pdf",
        "title": "Confidential Informant Statement (TOP SECRET)",
        "doc_type": "Witness Statement",
        "classification": "SECRET",
        "uploader_email": "investigator@lexsecure.local",
        "requires_dual_auth": True,
        "content": (
            "TOP SECRET - TWO MAN RULE CLEARANCE REQUIRED\n"
            "Informant ID: CI-49912 (Identity Protected)\n"
            "Date of Recording: 2026-08-22\n\n"
            "The informant has provided exact locations of the offshore hardware wallets holding the laundered funds. "
            "Releasing this document without dual authorization could lead to immediate asset freezing countermeasures by the syndicate."
        )
    },
    {
        "case_id": "CASE-2026-002",
        "filename": "Investigation_Report_002.pdf",
        "title": "Preliminary Investigation Diary - Cyber Harassment Incident",
        "doc_type": "Investigation Report",
        "classification": "CONFIDENTIAL",
        "uploader_email": "supervisor@lexsecure.local",
        "content": (
            "CASE DIARY / PRELIMINARY INVESTIGATION REPORT\n"
            "Case Reference: CASE-2026-002 (Women Safety Division)\n"
            "Supervising Officer: SP Sunita Verma, IPS\n\n"
            "Summary:\n"
            "Complainant reported synthetic audiovisual extortion messages received via encrypted VoIP numbers. "
            "Digital IP header inspection indicates spoofed virtual private network exits in Frankfurt and Singapore. "
            "A formal request under Section 94 BNSS has been served upon the cloud VoIP provider to preserve metadata and connection records."
        )
    }
]

def seed_database():
    print("==========================================================")
    print("LEXSECURE SAMPLE DATA SEEDER")
    print("Creates evaluation cases/documents in the configured database.")
    print("Safe to re-run: existing records are left untouched.")
    print("==========================================================")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        genesis = ensure_genesis_block(db)
        print(f"[✓] Blockchain Ledger initialized. Genesis Block: #{genesis.block_number}")

        user_map = {}
        for u_data in USERS_SEED:
            existing = db.query(User).filter(User.email == u_data["email"]).first()
            if not existing:
                priv_pem, pub_pem = generate_key_pair()
                user = User(
                    email=u_data["email"],
                    full_name=u_data["full_name"],
                    role=u_data["role"],
                    department=u_data["department"],
                    badge_number=u_data["badge_number"],
                    hashed_password=hash_password(SAMPLE_PASSWORD),
                    mfa_enabled=True,
                    mfa_secret=generate_secret(),
                    mfa_activated_at=None,
                    public_key_pem=pub_pem,
                    private_key_pem=encrypt_secret(priv_pem),
                    is_active=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                user_map[user.email] = user
                print(f"[✓] Created user: {user.email} [{user.role.value}] with RSA-2048 keys")
            else:
                user_map[existing.email] = existing

        for c_data in CASES_SEED:
            existing_case = db.query(Case).filter(Case.id == c_data["id"]).first()
            if not existing_case:
                c = Case(
                    id=c_data["id"],
                    title=c_data["title"],
                    description=c_data["description"],
                    department=c_data["department"],
                    status=c_data["status"],
                    classification=c_data["classification"],
                    incident_date=c_data["incident_date"]
                )
                db.add(c)
                db.commit()
                print(f"[✓] Created case: {c.id} - {c.title[:45]}...")

                if c.id == "CASE-2026-001":
                    for role_email, a_role in [
                        ("investigator@lexsecure.local", "LEAD_INVESTIGATOR"),
                        ("forensic@lexsecure.local", "FORENSIC_EXPERT"),
                        ("legal@lexsecure.local", "PROSECUTING_COUNSEL"),
                        ("supervisor@lexsecure.local", "SUPERVISING_OFFICER")
                    ]:
                        u = user_map[role_email]
                        assign = CaseAssignment(
                            case_id=c.id,
                            user_id=u.id,
                            assignment_role=a_role,
                            can_upload=True,
                            can_approve=(u.role in [UserRole.SUPERVISOR, UserRole.LEGAL_OFFICER])
                        )
                        db.add(assign)

                elif c.id == "CASE-2026-002":
                    for role_email, a_role in [
                        ("legal@lexsecure.local", "PROSECUTING_COUNSEL"),
                        ("supervisor@lexsecure.local", "SUPERVISING_OFFICER")
                    ]:
                        u = user_map[role_email]
                        assign = CaseAssignment(
                            case_id=c.id,
                            user_id=u.id,
                            assignment_role=a_role,
                            can_upload=True,
                            can_approve=True
                        )
                        db.add(assign)

                elif c.id == "CASE-2026-003":
                    u = user_map["supervisor@lexsecure.local"]
                    assign = CaseAssignment(
                        case_id=c.id,
                        user_id=u.id,
                        assignment_role="SUPERVISING_OFFICER",
                        can_upload=True,
                        can_approve=True
                    )
                    db.add(assign)

                db.commit()

        for d_info in SAMPLE_DOCUMENTS:
            existing_doc = db.query(Document).filter(
                Document.case_id == d_info["case_id"],
                Document.title == d_info["title"]
            ).first()

            if not existing_doc:
                uploader = user_map[d_info["uploader_email"]]
                doc_bytes = build_pdf_bytes(d_info["title"], d_info["content"])
                res = process_and_store_document(
                    db=db,
                    user=uploader,
                    case_id=d_info["case_id"],
                    file_name=d_info["filename"],
                    file_bytes=doc_bytes,
                    mime_type="application/pdf",
                    title=d_info["title"],
                    document_type_override=d_info["doc_type"],
                    classification=d_info["classification"],
                    requires_dual_auth=d_info.get("requires_dual_auth", False),
                    change_reason="Initial evidentiary filing"
                )
                print(f"[✓] Document processed: {d_info['filename']} -> Hash: {res['sha256_hash'][:12]}... (Ledger #{res['ledger_block_number']})")

        forensic_doc = db.query(Document).filter(
            Document.case_id == "CASE-2026-001",
            Document.title.contains("Forensic")
        ).first()

        if forensic_doc and forensic_doc.current_version == 1:
            forensic_user = user_map["forensic@lexsecure.local"]
            v2_content = (
                SAMPLE_DOCUMENTS[1]["content"] +
                "\n\n--- SUPPLEMENTARY ADDENDUM (VERSION 2) ---\n"
                "Date: 2026-08-25 | Supplementary Examination:\n"
                "Additional forensic de-obfuscation of the ransomware command and control protocol.\n"
                "Decoded secondary configuration file targeting port 443 with TLS fingerprint matching known APT infrastructure.\n"
                "Digital signature updated."
            )
            v2_res = process_and_store_document(
                db=db,
                user=forensic_user,
                case_id="CASE-2026-001",
                file_name="Forensic_Report_001_v2.pdf",
                file_bytes=build_pdf_bytes(forensic_doc.title, v2_content),
                mime_type="application/pdf",
                title=forensic_doc.title,
                document_type_override=forensic_doc.document_type,
                classification=forensic_doc.classification,
                change_reason="Added supplementary protocol de-obfuscation addendum",
                existing_document_id=forensic_doc.id
            )
            print(f"[✓] Created Document Version 2: {forensic_doc.title} (v2 Hash: {v2_res['sha256_hash'][:12]}...)")

        informant_doc = db.query(Document).filter(
            Document.case_id == "CASE-2026-002",
            Document.title.contains("Investigation Diary")
        ).first() or forensic_doc
        if informant_doc and not informant_doc.requires_dual_auth:
            informant_doc.requires_dual_auth = True
            db.commit()
            print(f"[✓] Sealed '{informant_doc.title[:40]}' under Two-Man Rule (dual-auth)")

        print("==========================================================")
        print("DATABASE SEEDING COMPLETED SUCCESSFULLY")
        print(f"Sample account password: {SAMPLE_PASSWORD}")
        print("MFA: TOTP is enforced. Run 'python scripts/provision_mfa.py'")
        print("     to print the QR codes / secrets for these accounts.")
        print("==========================================================")

    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
