"""Bio-lab automation layer for FRIDAY — DNA analysis, PCR planning, lab equipment control."""
from __future__ import annotations
import json, time
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "bio_lab_state.json"

_CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L", "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M", "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S", "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T", "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*", "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K", "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W", "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R", "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}
_ENZYMES = {"EcoRI": "GAATTC", "BamHI": "GGATCC", "HindIII": "AAGCTT", "NotI": "GCGGCCGC",
            "XhoI": "CTCGAG", "PstI": "CTGCAG", "SmaI": "CCCGGG"}

def _load() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"experiments": [], "equipment_log": []}

def _save(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def _clean(seq: str) -> str:
    return "".join(c for c in (seq or "").upper() if c in "ATCG")

def analyze_dna(sequence: str) -> dict:
    """Real sequence stats: length, GC%, base counts, reverse complement, mRNA."""
    seq = _clean(sequence)
    if not seq:
        return {"ok": False, "error": "No valid ACGT bases in input"}
    comp = {"A": "T", "T": "A", "G": "C", "C": "G"}
    gc = sum(1 for c in seq if c in "GC")
    return {"ok": True, "length": len(seq), "gc_percent": round(100.0 * gc / len(seq), 2),
            "base_counts": {b: seq.count(b) for b in "ATCG"},
            "reverse_complement": "".join(comp[c] for c in reversed(seq)),
            "mrna": seq.replace("T", "U")}

def translate_dna(sequence: str) -> dict:
    """Translate DNA to a protein using the standard genetic code."""
    seq = _clean(sequence)
    protein = "".join(_CODON_TABLE.get(seq[i:i + 3], "X") for i in range(0, len(seq) - len(seq) % 3, 3))
    stop = protein.find("*")
    return {"ok": True, "protein": protein, "stops_at_first_terminator": protein[:stop] if stop >= 0 else None,
            "length_aa": len(protein.rstrip("*"))}

def find_restriction_sites(sequence: str, enzyme: str = None) -> dict:
    """Locate restriction enzyme cut motifs (real recognition sequences)."""
    seq = _clean(sequence)
    targets = {enzyme: _ENZYMES[enzyme]} if enzyme in _ENZYMES else _ENZYMES
    sites = {name: [i for i in range(len(seq) - len(motif) + 1) if seq[i:i + len(motif)] == motif]
             for name, motif in targets.items()}
    return {"ok": True, "sites": {k: v for k, v in sites.items() if v}}
def design_primers(sequence: str, length: int = 20) -> dict:
    """Design forward/reverse primers with real Wallace-rule Tm and GC checks."""
    seq = _clean(sequence)
    if len(seq) < 2 * length:
        return {"ok": False, "error": "Sequence too short for primer design"}
    def stats(p):
        gc = sum(1 for c in p if c in "GC")
        return {"gc_percent": round(100.0 * gc / len(p), 1), "tm_wallace_c": 2 * (len(p) - gc) + 4 * gc,
                "gc_clamp_3p": p[-1] in "GC"}
    fwd, rev = seq[:length], seq[-length:]
    comp = {"A": "T", "T": "A", "G": "C", "C": "G"}
    result = {"ok": True, "forward": {"sequence": fwd, **stats(fwd)},
              "reverse": {"sequence": "".join(comp[c] for c in reversed(rev)), **stats(rev)}}
    state = _load()
    state.setdefault("experiments", []).append({"t": time.time(), "type": "primer_design", "primer_len": length})
    _save(state)
    return result

def pcr_protocol(template_len_bp: int, primer_tm: float, cycles: int = 30) -> dict:
    """Generate a real PCR cycling program (extension ~30s per kb)."""
    anneal = max(50.0, primer_tm - 3.0)
    ext_seconds = max(15, int(template_len_bp / 1000.0 * 30))
    return {"ok": True, "cycles": cycles,
            "program": [
                {"step": "initial_denaturation", "temp_c": 95, "seconds": 180},
                {"step": "denaturation", "temp_c": 95, "seconds": 30},
                {"step": "annealing", "temp_c": round(anneal, 1), "seconds": 30},
                {"step": "extension", "temp_c": 72, "seconds": ext_seconds},
                {"step": "final_extension", "temp_c": 72, "seconds": 300},
                {"step": "hold", "temp_c": 4, "seconds": None}],
            "estimated_duration_min": round((3 + cycles * (0.5 + 0.5 + ext_seconds / 60.0) + 5), 1)}

def control_equipment(device: str, command: str, params: dict = None) -> dict:
    """Control lab equipment (OpenPCR, centrifuge) via serial command framing + log."""
    frame_map = {"openpcr": "OP:%s:%s;", "centrifuge": "CF:%s:%s;", "generic": "CMD:%s:%s;"}
    frame = frame_map.get(device, frame_map["generic"]) % (command.upper(), json.dumps(params or {}))
    state = _load()
    state.setdefault("equipment_log", []).append({"t": time.time(), "device": device, "command": command, "frame": frame})
    _save(state)
    return {"ok": True, "device": device, "command": command, "frame": frame,
            "note": "frame built; connect serial bridge to transmit"}

def bio_tool(args: dict) -> dict:
    a = args or {}
    action = a.get("action", "")
    if action == "analyze":
        return analyze_dna(a.get("sequence", ""))
    if action == "translate":
        return translate_dna(a.get("sequence", ""))
    if action == "restriction_sites":
        return find_restriction_sites(a.get("sequence", ""), a.get("enzyme"))
    if action == "primers":
        return design_primers(a.get("sequence", ""), int(a.get("length", 20)))
    if action == "pcr":
        return pcr_protocol(int(a.get("template_len_bp", 1000)), float(a.get("primer_tm", 58)), int(a.get("cycles", 30)))
    if action == "equipment":
        return control_equipment(a.get("device", "generic"), a.get("command", "status"), a.get("params"))
    return {"ok": False, "error": "Unknown bio action"}