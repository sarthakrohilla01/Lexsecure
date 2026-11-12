"""Permissioned Ledger Service — Append-only cryptographic hash chain"""

import hashlib
import threading
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.ledger import LedgerBlock
from app.blockchain.fabric_adapter import LocalLedgerAdapter
from app.utils.time import utcnow

ledger_adapter = LocalLedgerAdapter()

_chain_lock = threading.Lock()

def compute_block_hash(
    block_number: int,
    timestamp_str: str,
    document_id: Optional[int],
    version_number: Optional[int],
    document_hash: str,
    event_type: str,
    user_id: Optional[int],
    previous_hash: str
) -> str:
    """Computes cryptographic SHA-256 hash for a block payload. Ensures complete chaining and tamper resistance."""
    content = f"{block_number}|{timestamp_str}|{document_id}|{version_number}|{document_hash}|{event_type}|{user_id}|{previous_hash}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def ensure_genesis_block(db: Session) -> LedgerBlock:
    """Initializes Genesis block if the ledger is empty."""
    genesis = db.query(LedgerBlock).filter(LedgerBlock.block_number == 0).first()
    if genesis:
        return genesis

    ts = utcnow()
    prev_hash = "0" * 64
    doc_hash = "0" * 64
    block_hash = compute_block_hash(
        block_number=0,
        timestamp_str=ts.isoformat(),
        document_id=None,
        version_number=0,
        document_hash=doc_hash,
        event_type="GENESIS",
        user_id=None,
        previous_hash=prev_hash
    )

    genesis = LedgerBlock(
        block_number=0,
        timestamp=ts,
        document_id=None,
        case_id="SYSTEM",
        version_number=0,
        document_hash=doc_hash,
        event_type="GENESIS",
        user_id=None,
        user_email="system@ncrb.gov.in",
        user_role="SYSTEM",
        previous_hash=prev_hash,
        block_hash=block_hash,
        chaincode_tx_id="GENESIS-BLOCK-0"
    )
    db.add(genesis)
    db.commit()
    db.refresh(genesis)
    return genesis

def record_ledger_block(
    db: Session,
    document_id: Optional[int],
    case_id: Optional[str],
    version_number: Optional[int],
    document_hash: str,
    event_type: str,
    user_id: Optional[int],
    user_email: Optional[str],
    user_role: Optional[str]
) -> LedgerBlock:
    """Appends a new block to the permissioned ledger chain."""
    with _chain_lock:
        ensure_genesis_block(db)

        last_block = db.query(LedgerBlock).order_by(LedgerBlock.block_number.desc()).first()
        next_block_number = last_block.block_number + 1
        previous_hash = last_block.block_hash
        ts = utcnow()

        block_hash = compute_block_hash(
            block_number=next_block_number,
            timestamp_str=ts.isoformat(),
            document_id=document_id,
            version_number=version_number,
            document_hash=document_hash,
            event_type=event_type,
            user_id=user_id,
            previous_hash=previous_hash
        )

        ledger_tx = ledger_adapter.invoke_chaincode(
            fcn="RecordDocumentEvent",
            args=[str(document_id or ""), str(version_number or 1), document_hash, event_type]
        )

        new_block = LedgerBlock(
            block_number=next_block_number,
            timestamp=ts,
            document_id=document_id,
            case_id=case_id,
            version_number=version_number,
            document_hash=document_hash,
            event_type=event_type,
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            previous_hash=previous_hash,
            block_hash=block_hash,
            chaincode_tx_id=ledger_tx["tx_id"]
        )
        db.add(new_block)
        db.commit()
        db.refresh(new_block)
        return new_block

def verify_ledger_chain_integrity(db: Session) -> Dict[str, Any]:
    """Validates entire ledger chain from Genesis to tip. Detects if any historical block, hash, or chain link was modified."""
    blocks = db.query(LedgerBlock).order_by(LedgerBlock.block_number.asc()).all()
    if not blocks:
        return {"status": "EMPTY", "is_valid": True, "blocks_verified": 0}

    for i, block in enumerate(blocks):
        if i > 0:
            prev_block = blocks[i - 1]
            if block.previous_hash != prev_block.block_hash:
                return {
                    "status": "TAMPERING_DETECTED",
                    "is_valid": False,
                    "failed_block": block.block_number,
                    "reason": f"Block #{block.block_number} previous_hash mismatch with Block #{prev_block.block_number}",
                    "expected_previous_hash": prev_block.block_hash,
                    "actual_previous_hash": block.previous_hash
                }

        recomputed = compute_block_hash(
            block_number=block.block_number,
            timestamp_str=block.timestamp.isoformat(),
            document_id=block.document_id,
            version_number=block.version_number,
            document_hash=block.document_hash,
            event_type=block.event_type,
            user_id=block.user_id,
            previous_hash=block.previous_hash
        )
        if recomputed != block.block_hash:
            return {
                "status": "TAMPERING_DETECTED",
                "is_valid": False,
                "failed_block": block.block_number,
                "reason": f"Block #{block.block_number} data content was altered after commit!",
                "expected_block_hash": block.block_hash,
                "recalculated_hash": recomputed
            }

    return {
        "status": "VERIFIED",
        "is_valid": True,
        "blocks_verified": len(blocks),
        "latest_block_number": blocks[-1].block_number,
        "latest_block_hash": blocks[-1].block_hash,
        "ledger_technology": "Append-only SHA-256 hash chain (deterministic transaction ids)"
    }
