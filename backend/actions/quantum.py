"""Quantum computing layer for FRIDAY — dependency-free statevector simulator, Grover, Qiskit/Cirq bridge."""
from __future__ import annotations
import json, math, cmath, random, time
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "quantum_state.json"

_H = [[1 / math.sqrt(2), 1 / math.sqrt(2)], [1 / math.sqrt(2), -1 / math.sqrt(2)]]
_X = [[0, 1], [1, 0]]
_Y = [[0, -1j], [1j, 0]]
_Z = [[1, 0], [0, -1]]

def _gate_matrix(name: str, theta: float = 0.0):
    if name == "h": return _H
    if name == "x": return _X
    if name == "y": return _Y
    if name == "z": return _Z
    if name == "rx": return [[math.cos(theta / 2), -1j * math.sin(theta / 2)], [-1j * math.sin(theta / 2), math.cos(theta / 2)]]
    if name == "ry": return [[math.cos(theta / 2), -math.sin(theta / 2)], [math.sin(theta / 2), math.cos(theta / 2)]]
    if name == "rz": return [[cmath.exp(-1j * theta / 2), 0], [0, cmath.exp(1j * theta / 2)]]
    raise ValueError("Unknown gate: %s" % name)

def _apply_1q(state: list, matrix, target: int) -> list:
    new = list(state)
    stride = 1 << target
    for i in range(len(state)):
        if i & stride:
            continue
        a, b = state[i], state[i | stride]
        new[i] = matrix[0][0] * a + matrix[0][1] * b
        new[i | stride] = matrix[1][0] * a + matrix[1][1] * b
    return new

def _apply_cx(state: list, control: int, target: int) -> list:
    new = list(state)
    for i in range(len(state)):
        if (i >> control) & 1 and not (i >> target) & 1:
            j = i | (1 << target)
            new[i], new[j] = state[j], state[i]
    return new

def run_circuit(qubits: int, gates: list, shots: int = 256) -> dict:
    """Simulate a quantum circuit on a real statevector (supports h,x,y,z,rx,ry,rz,cx)."""
    if not 1 <= qubits <= 12:
        return {"ok": False, "error": "qubits must be 1..12 for the local simulator"}
    state = [complex(0)] * (1 << qubits)
    state[0] = complex(1)
    applied = []
    for g in gates or []:
        name = g.get("gate", "")
        if name == "cx":
            state = _apply_cx(state, int(g["control"]), int(g["target"]))
        else:
            state = _apply_1q(state, _gate_matrix(name, float(g.get("theta", 0))), int(g["target"]))
        applied.append(g)
    probs = [abs(a) ** 2 for a in state]
    samples = {}
    for _ in range(max(1, int(shots))):
        r, acc = random.random(), 0.0
        for i, p in enumerate(probs):
            acc += p
            if r <= acc:
                bits = format(i, "0%db" % qubits)
                samples[bits] = samples.get(bits, 0) + 1
                break
    return {"ok": True, "qubits": qubits, "gates_applied": applied,
            "probabilities": {format(i, "0%db" % qubits): round(p, 6) for i, p in enumerate(probs) if p > 1e-9},
            "samples": samples, "backend": "statevector-pure-python"}
def grover_search(n_qubits: int, marked_index: int, shots: int = 64) -> dict:
    """Real Grover amplitude amplification on the statevector (no dependencies)."""
    if not 1 <= n_qubits <= 10:
        return {"ok": False, "error": "qubits must be 1..10"}
    n = 1 << n_qubits
    marked = marked_index % n
    state = [complex(1 / math.sqrt(n))] * n
    iterations = int(math.floor(math.pi / 4 * math.sqrt(n)))
    for _ in range(max(1, iterations)):
        state[marked] = -state[marked]                      # oracle
        mean = sum(state) / n                               # diffusion (2|s><s| - I)
        state = [2 * mean - a for a in state]
    probs = [abs(a) ** 2 for a in state]
    best = max(range(n), key=lambda i: probs[i])
    samples = {}
    for _ in range(max(1, shots)):
        r, acc = random.random(), 0.0
        for i, p in enumerate(probs):
            acc += p
            if r <= acc:
                bits = format(i, "0%db" % n_qubits)
                samples[bits] = samples.get(bits, 0) + 1
                break
    return {"ok": True, "algorithm": "grover", "qubits": n_qubits, "marked_index": marked,
            "iterations": max(1, iterations), "found_index": best,
            "success_probability": round(probs[best], 4),
            "success": best == marked, "samples": samples}

def qiskit_run(qubits: int, gates: list, shots: int = 256) -> dict:
    """Run the same circuit through Qiskit AerSimulator when installed."""
    try:
        from qiskit import QuantumCircuit  # type: ignore
        from qiskit_aer import AerSimulator  # type: ignore
    except Exception as exc:
        return {"ok": False, "error": "qiskit not installed (%s)" % exc, "fallback": "use run_circuit (pure python)"}
    qc = QuantumCircuit(qubits, qubits)
    for g in gates or []:
        name = g.get("gate", "")
        if name == "cx":
            qc.cx(int(g["control"]), int(g["target"]))
        elif name == "h":
            qc.h(int(g["target"]))
        elif name in ("x", "y", "z"):
            getattr(qc, name)(int(g["target"]))
        elif name in ("rx", "ry", "rz"):
            getattr(qc, name)(float(g.get("theta", 0)), int(g["target"]))
    qc.measure(range(qubits), range(qubits))
    counts = AerSimulator().run(qc, shots=shots).result().get_counts()
    return {"ok": True, "backend": "qiskit-aer", "counts": counts}

def quantum_tool(args: dict) -> dict:
    a = args or {}
    action = a.get("action", "")
    if action == "run_circuit":
        return run_circuit(int(a.get("qubits", 2)), a.get("gates", []), int(a.get("shots", 256)))
    if action == "bell_state":
        return run_circuit(2, [{"gate": "h", "target": 0}, {"gate": "cx", "control": 0, "target": 1}], int(a.get("shots", 256)))
    if action == "grover":
        return grover_search(int(a.get("qubits", 3)), int(a.get("marked_index", 0)), int(a.get("shots", 64)))
    if action == "qiskit":
        return qiskit_run(int(a.get("qubits", 2)), a.get("gates", []), int(a.get("shots", 256)))
    return {"ok": False, "error": "Unknown quantum action"}