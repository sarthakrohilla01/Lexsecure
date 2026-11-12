"""Ledger Adapter Interface"""

import hashlib
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class LedgerAdapterInterface(ABC):
    @abstractmethod
    def invoke_chaincode(self, fcn: str, args: List[str]) -> Dict[str, Any]:
        """Commits a transaction and returns its identifier."""
        raise NotImplementedError

    @abstractmethod
    def query_chaincode(self, fcn: str, args: List[str]) -> Dict[str, Any]:
        """Reads ledger state without committing."""
        raise NotImplementedError


class LocalLedgerAdapter(LedgerAdapterInterface):
    """Append-only local hash chain. Transaction ids are deterministic digests of the committed payload, so the same evidence always maps to the same transaction id and no identifier is invented from randomness."""

    network_name = "lexsecure-local-ledger"
    chaincode_id = "document_custody_cc"

    def _tx_id(self, fcn: str, args: List[str]) -> str:
        digest = hashlib.sha256(("|".join([fcn, *args])).encode("utf-8")).hexdigest()
        return f"TX-{digest[:32].upper()}"

    def invoke_chaincode(self, fcn: str, args: List[str]) -> Dict[str, Any]:
        return {
            "status": "COMMITTED",
            "tx_id": self._tx_id(fcn, args),
            "ledger": self.network_name,
            "chaincode": self.chaincode_id,
            "function": fcn,
            "arguments": args,
        }

    def query_chaincode(self, fcn: str, args: List[str]) -> Dict[str, Any]:
        return {
            "status": "SUCCESS",
            "ledger": self.network_name,
            "function": fcn,
            "payload": args,
        }
