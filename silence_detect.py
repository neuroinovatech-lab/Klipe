#!/usr/bin/env python3
"""
silence_detect.py — Detector de silencios + filler words pro Klipe Auto-Edit

Le transcription.json (Whisper output, segment-level) e detecta:
  1. SILENCES entre segmentos (gap > threshold)
  2. FILLER SEGMENTS inteiros ("ah", "umm", "eh", "tipo")
  3. FALSE STARTS (segmento que comeca igual ao proximo)

Output: JSON com cuts sugeridos pra UI mostrar pro user aprovar.

Uso:
  python silence_detect.py <project_name> [--silence-min 0.5] [--apply]
  python silence_detect.py barreiras-academico
  python silence_detect.py barreiras-academico --silence-min 0.8
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
PROJECTS = PUBLIC / "projects"

# Filler words em PT-BR + EN (regex case-insensitive)
# Sao "fillers" quando o SEGMENTO INTEIRO eh esse padrao (sentenca curta = ruido)
FILLER_PATTERNS_FULL_SEGMENT = [
    r"^\s*(ah+|hum+|um+|eh+|errr+|ahnnn+|tipo|n[ée]+|ent[aã]o|sabe)\s*[\.,!?]*\s*$",
    r"^\s*(uh+|um+|er+|hmm+|like|you know)\s*[\.,!?]*\s*$",
]

# Filler patterns: palavras que DENTRO do segmento sao fillers (so detectado se houver
# word-level timestamps — futura implementacao). Por enquanto so segmentos cheios.
FILLER_WORDS_INLINE = [
    "ah", "ahn", "humm", "uhm", "tipo", "tipo assim",
    "né", "então", "sabe", "tipo que", "pera"
]


def load_transcription(project_name: str):
    """Le transcription.json do projeto. Retorna lista de segments [{start,end,text}]."""
    path = PROJECTS / project_name / "transcription.json"
    if not path.exists():
        print(f"FAIL: {path} nao encontrado")
        sys.exit(1)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        # Whisper output pode vir como dict {segments: [...]} dependendo do tool
        if isinstance(data, dict) and "segments" in data:
            data = data["segments"]
        else:
            print(f"FAIL: formato inesperado em {path}")
            sys.exit(1)
    return data


def detect_silences(segments, min_silence_sec=0.5, head_silence=True, padding=0.18):
    """Detecta gaps entre segmentos > threshold.
    Retorna lista de [{startSec, endSec, type, durSec, reason}].

    PADDING (default 0.18s): preserva audio antes/depois de cada cut pra não cortar
    palavras pela metade. Whisper marca segment.end as vezes antes do som da palavra
    realmente terminar — o padding compensa esse erro de detecção.

    Cut efetivo = [gap_start + padding, gap_end - padding].
    Se gap < 2*padding + 0.1s (margem mínima viável), pula esse cut (nao vale).
    """
    silences = []
    min_viable_gap = 2 * padding + 0.10  # gap precisa ser > esse pra valer cortar

    if head_silence and segments and segments[0]["start"] > min_silence_sec:
        # No início, só temos um lado pra paddear
        head_end = max(0, segments[0]["start"] - padding)
        if head_end > padding:
            silences.append({
                "startSec": 0.0,
                "endSec": round(head_end, 2),
                "type": "silence",
                "durSec": round(head_end, 2),
                "reason": "Silencio inicial (antes da primeira fala)",
            })

    for i in range(len(segments) - 1):
        gap_start = segments[i]["end"]
        gap_end = segments[i + 1]["start"]
        gap = gap_end - gap_start
        if gap >= min_silence_sec and gap >= min_viable_gap:
            # Aplica padding dos dois lados
            cut_start = gap_start + padding
            cut_end = gap_end - padding
            if cut_end > cut_start + 0.05:  # cut precisa ter pelo menos 50ms de duração
                silences.append({
                    "startSec": round(cut_start, 2),
                    "endSec": round(cut_end, 2),
                    "type": "silence",
                    "durSec": round(cut_end - cut_start, 2),
                    "reason": f"Gap de {gap:.2f}s entre falas (com padding {padding}s)",
                })
    return silences


def detect_filler_segments(segments, max_filler_dur=2.0):
    """Detecta segmentos que sao APENAS filler words.
    max_filler_dur: descarta segmentos longos (>2s) — provavelmente nao sao filler.
    """
    fillers = []
    for s in segments:
        dur = s["end"] - s["start"]
        if dur > max_filler_dur:
            continue
        text = s["text"].strip()
        if not text:
            continue
        is_filler = any(re.match(pat, text, re.IGNORECASE) for pat in FILLER_PATTERNS_FULL_SEGMENT)
        if is_filler:
            fillers.append({
                "startSec": round(s["start"], 2),
                "endSec": round(s["end"], 2),
                "type": "filler",
                "durSec": round(dur, 2),
                "reason": f"Segmento-filler: \"{text}\"",
            })
    return fillers


def detect_false_starts(segments, max_overlap_chars=15):
    """Detecta false starts E repeticoes literais.

    Casos:
    1. False start prefixo: A=\"Eu acho\", B=\"Eu acho que isso...\" → corta A
    2. Repeticao literal: A=\"frase X\", B=\"frase X\" (texto identico) → corta A
    3. Repeticao parcial: A e B com 70%+ palavras em comum E A curto → corta A
    """
    false_starts = []
    def normalize_words(text):
        return [re.sub(r"[^\w]", "", w.lower()) for w in text.split() if w.strip()]

    for i in range(len(segments) - 1):
        a_text = segments[i]["text"].strip()
        b_text = segments[i + 1]["text"].strip()
        a_words = normalize_words(a_text)
        b_words = normalize_words(b_text)

        if len(a_words) < 3 or len(b_words) < 3:
            continue

        # CASO 1 + 2 — prefixo (3+ palavras iguais comecando do inicio)
        common_prefix = 0
        for wa, wb in zip(a_words, b_words):
            if wa == wb:
                common_prefix += 1
            else:
                break

        # CASO 3 — overlap por set (70%+ palavras de A estao em B)
        a_set = set(a_words)
        b_set = set(b_words)
        overlap_ratio = len(a_set & b_set) / len(a_set) if a_set else 0

        # Decisao: corta A se
        # - prefixo: 3+ palavras iguais E A curto (≤20 palavras)
        # - repeticao literal: 100% palavras iguais (e mesma quantidade)
        # - repeticao parcial: 80%+ overlap E A nao gigante (≤20 palavras)
        is_false_start = (common_prefix >= 3 and len(a_words) <= 20)
        is_literal_repeat = (a_words == b_words)
        is_partial_repeat = (overlap_ratio >= 0.80 and len(a_words) <= 20)

        if is_false_start or is_literal_repeat or is_partial_repeat:
            kind = "literal_repeat" if is_literal_repeat else ("partial_repeat" if is_partial_repeat else "false_start")
            false_starts.append({
                "startSec": round(segments[i]["start"], 2),
                "endSec": round(segments[i]["end"] + 0.1, 2),  # inclui pausa de 100ms
                "type": kind,
                "durSec": round(segments[i]["end"] - segments[i]["start"] + 0.1, 2),
                "reason": f"{kind}: \"{a_text[:60]}\" repetido/duplicado em N+1",
            })
    return false_starts


def consolidate_cuts(cuts, merge_gap=0.3):
    """Mescla cuts adjacentes se gap entre eles < merge_gap."""
    if not cuts:
        return []
    cuts = sorted(cuts, key=lambda c: c["startSec"])
    merged = [dict(cuts[0])]
    for c in cuts[1:]:
        last = merged[-1]
        if c["startSec"] - last["endSec"] <= merge_gap:
            last["endSec"] = max(last["endSec"], c["endSec"])
            last["durSec"] = round(last["endSec"] - last["startSec"], 2)
            last["reason"] = f"{last['reason']} + {c['reason']}"
            last["type"] = "mixed" if last["type"] != c["type"] else last["type"]
        else:
            merged.append(dict(c))
    return merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", help="Nome do projeto (ex: barreiras-academico)")
    ap.add_argument("--silence-min", type=float, default=0.5,
                    help="Silencio minimo em segundos pra cortar (default 0.5)")
    ap.add_argument("--padding", type=float, default=0.18,
                    help="Padding em segundos pra preservar audio antes/depois do cut (default 0.18 — evita cortar palavras pela metade)")
    ap.add_argument("--filler-max-dur", type=float, default=2.0,
                    help="Duracao max de segmento pra ser considerado filler (default 2s)")
    ap.add_argument("--no-merge", action="store_true",
                    help="Nao consolida cuts adjacentes")
    ap.add_argument("--out", help="Salva output JSON em arquivo")
    args = ap.parse_args()

    segments = load_transcription(args.project)
    print(f"Loaded {len(segments)} segments from {args.project}/transcription.json")

    silences = detect_silences(segments, min_silence_sec=args.silence_min, padding=args.padding)
    fillers = detect_filler_segments(segments, max_filler_dur=args.filler_max_dur)
    false_starts = detect_false_starts(segments)

    print(f"\nDetected:")
    print(f"  Silences ({args.silence_min}s+): {len(silences)}")
    print(f"  Filler segments: {len(fillers)}")
    print(f"  False starts: {len(false_starts)}")

    all_cuts = silences + fillers + false_starts
    if not args.no_merge:
        all_cuts = consolidate_cuts(all_cuts)

    total_dur = sum(c["durSec"] for c in all_cuts)
    print(f"\nTotal cuts: {len(all_cuts)} | tempo cortado total: {total_dur:.1f}s ({total_dur/60:.1f}min)")

    # Sample preview
    print("\nSample cuts (primeiros 10):")
    for c in all_cuts[:10]:
        print(f"  [{c['type']:12s}] {c['startSec']:7.2f}s -> {c['endSec']:7.2f}s ({c['durSec']:.2f}s) | {c['reason'][:80]}")

    output = {
        "project": args.project,
        "totalCuts": len(all_cuts),
        "totalCutDurSec": round(total_dur, 2),
        "params": {
            "silenceMinSec": args.silence_min,
            "fillerMaxDur": args.filler_max_dur,
        },
        "cuts": all_cuts,
        "stats": {
            "silences": len(silences),
            "fillers": len(fillers),
            "falseStarts": len(false_starts),
        }
    }

    if args.out:
        Path(args.out).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSaved to {args.out}")

    # Stdout JSON pra ser consumido por outro processo
    if not args.out:
        print("\n--- JSON output ---")
        print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
