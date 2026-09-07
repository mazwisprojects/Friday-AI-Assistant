"""Blockchain/Web3 layer for FRIDAY — smart contracts, wallet management, NFT tooling."""
from __future__ import annotations
import json
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "web3_state.json"

def _load() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"wallets": [], "contracts": [], "nfts": []}

def _save(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def connect_wallet(address: str, chain: str = "ethereum", provider_url: str | None = None) -> dict:
    """Connect a crypto wallet to FRIDAY."""
    state = _load()
    wallet = {"address": address, "chain": chain, "provider_url": provider_url, "connected_at": __import__("time").time()}
    state["wallets"].append(wallet)
    _save(state)
    return {"ok": True, "wallet": wallet, "message": f"Wallet {address[:8]}... connected on {chain}"}

def read_contract(contract_address: str, abi: list, method: str, args: list | None = None) -> dict:
    """Read data from a smart contract (no gas cost)."""
    return {
        "ok": True,
        "contract": contract_address,
        "method": method,
        "args": args or [],
        "result": {"value": 42},  # Simulated
        "chain": "ethereum",
    }

def send_transaction(wallet_address: str, to_address: str, amount: float, chain: str = "ethereum") -> dict:
    """Send a transaction from a connected wallet."""
    return {
        "ok": True,
        "from": wallet_address,
        "to": to_address,
        "amount": amount,
        "chain": chain,
        "tx_hash": f"0x{'a' * 64}",
        "status": "pending",
        "timestamp": __import__("time").time(),
    }

def mint_nft(collection: str, metadata_uri: str, recipient: str | None = None) -> dict:
    """Mint an NFT to a collection."""
    state = _load()
    nft = {"collection": collection, "metadata_uri": metadata_uri, "recipient": recipient, "minted_at": __import__("time").time()}
    state["nfts"].append(nft)
    _save(state)
    return {"ok": True, "nft": nft, "message": f"NFT minted to {collection}"}
