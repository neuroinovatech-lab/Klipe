"""
Offline port of /api/analyze-shorts (editor-server.js) — gera motionforge_clips
direto no edit_config.json, sem depender do servidor rodar.

Uso:
    python analyze_shorts_offline.py <caminho-projeto>
    ex: python analyze_shorts_offline.py public/projects/niveis-suporte-adulta

Injeta (ou substitui) a chave `motionforge_clips` no edit_config.json do projeto.
Também retorna a lista via stdout em JSON.
"""
import json
import re
import sys
from pathlib import Path

SENT_END_RE = re.compile(r'[.!?…]+')
# Strong words: didactic-content vocab (saúde mental, autismo, neurodiversidade, educação)
STRONG_WORDS = [
    "cuidado","atenção","nunca","sempre","jamais","importante","grave","sério","fatal",
    "mito","verdade","real","chocante","incrível","perigoso","essencial","crucial","fundamental",
    "barreiras","desistência","desistem","direitos","direito","estratégias","fadiga","autonomia",
    "isolamento","sobrecarga","bullying","ignoradas","insuportável","alarmantes","exige","precisa",
]
STAT_RE = re.compile(r'\d+\s*%|\d+\s*mil|\d+\s*milh|\d+\s*a\s*\d+|\d+\s*(vezes|x)\b', re.IGNORECASE)
PAYOFF_RE = re.compile(r'\b(por isso|então|resumindo|é por isso|ou seja|moral da história|no final|conclus|entende|percebe)\b', re.IGNORECASE)
ENG_WORDS = [
    "nunca","sempre","importante","cuidado","atenção","perigoso","incrível","chocante",
    "verdade","mentira","mito","real","precisa","deve","grave","sério","fatal",
    "diagnóstico","tratamento","sintoma","déficit","funcional","suporte","dificuldade","autonomia",
    "barreiras","desistência","direitos","estratégias","fadiga","sobrecarga","bullying",
]
STYLES_ROTATION = ["talkingHead","splitScreen","zoomPunchIn","squareBlur","letterbox","textHeavy","progressHook","floatingHead","memeCommentary"]
DEFAULT_THRESHOLD = 8


def extract_sentences(transcription):
    sents = []
    for cap in transcription:
        text = (cap.get("text") or "").strip()
        dur = cap["end"] - cap["start"]
        if not text or dur <= 0:
            continue
        t_per_char = dur / len(text)
        last_pos = 0
        for m in SENT_END_RE.finditer(text):
            end_pos = m.end()
            sent_text = text[last_pos:end_pos].strip()
            if len(sent_text) > 2:
                t = ("question" if "?" in m.group()
                     else "exclaim" if "!" in m.group()
                     else "statement")
                sents.append({
                    "startT": cap["start"] + last_pos * t_per_char,
                    "endT": min(cap["end"], cap["start"] + end_pos * t_per_char),
                    "text": sent_text,
                    "type": t,
                })
            last_pos = end_pos
            while last_pos < len(text) and text[last_pos].isspace():
                last_pos += 1
        if last_pos < len(text):
            sent_text = text[last_pos:].strip()
            if len(sent_text) > 2:
                sents.append({
                    "startT": cap["start"] + last_pos * t_per_char,
                    "endT": cap["end"],
                    "text": sent_text,
                    "type": "fragment",
                    "noPunct": True,
                })
    return sents


def hook_score(sent):
    s = 0
    t = sent["text"].lower()
    if sent["type"] == "question": s += 10
    if sent["type"] == "exclaim": s += 6
    if STAT_RE.search(t): s += 8
    strong = sum(1 for w in STRONG_WORDS if w in t)
    s += min(strong * 3, 9)
    if 20 <= len(t) <= 90: s += 4
    if sent["type"] == "question" and len(t) < 70: s += 3
    return s


def snap_to_cap_start(t, transcription):
    for cap in transcription:
        if cap["start"] <= t + 0.5 and cap["end"] > t:
            return max(0, cap["start"])
    return max(0, t)


def starts_capital(txt):
    f = (txt or "").strip()[:1]
    return bool(f) and f.isupper() and f != f.lower()


def snap_to_cap_end(t, max_t, transcription):
    upper = (max_t + 5) if max_t is not None else float("inf")
    sent_ends = []
    for cap in transcription:
        if cap["end"] < t: continue
        if cap["start"] > upper: break
        text = (cap.get("text") or "").strip()
        if not text: continue
        dur = cap["end"] - cap["start"]
        if dur <= 0: continue
        t_per_char = dur / len(text)
        for m in re.finditer(r'[.!?…]+', text):
            pos = m.end()
            time = cap["start"] + pos * t_per_char
            if t <= time <= upper:
                next_chars = text[pos:].strip()
                next_capital = len(next_chars) == 0 or starts_capital(next_chars)
                sent_ends.append({"time": time, "nextCapital": next_capital})
    if not sent_ends:
        for cap in transcription:
            if cap["start"] < t and cap["end"] >= t - 0.5:
                return cap["end"]
        return t
    with_cap = next((s for s in sent_ends if s["nextCapital"]), None)
    chosen = with_cap or sent_ends[0]
    return chosen["time"] + 0.2


def analyze_shorts(edit_config, transcription, hook_threshold=DEFAULT_THRESHOLD):
    titles = edit_config.get("titles", []) or []
    brolls = edit_config.get("brolls", []) or []
    HOOK_THRESHOLD = hook_threshold
    MIN_DUR, IDEAL_MIN, IDEAL_MAX, MAX_DUR = 20, 30, 120, 180

    sentences = extract_sentences(transcription)
    candidates = []

    for i, hook in enumerate(sentences):
        hs = hook_score(hook)
        if hs < HOOK_THRESHOLD: continue

        clip_start = hook["startT"]
        if i > 0 and hook["startT"] - sentences[i-1]["endT"] < 0.6:
            clip_start = max(hook["startT"] - 1.5, sentences[i-1]["startT"])
        clip_start = max(0, clip_start)
        clip_start = snap_to_cap_start(clip_start, transcription)

        best = None
        for j in range(i+1, len(sentences)):
            s2 = sentences[j]
            dur = s2["endT"] - clip_start
            if dur < MIN_DUR: continue
            if dur > MAX_DUR: break
            if s2.get("noPunct"): continue
            local = 0
            s2t = s2["text"].lower()
            if PAYOFF_RE.search(s2t): local += 5
            if s2["type"] == "statement" and IDEAL_MIN <= dur <= IDEAL_MAX: local += 3
            if s2["type"] == "exclaim": local += 2
            if not re.match(r'^(e |mas |porque |então |aí )', s2["text"], re.IGNORECASE): local += 1
            if IDEAL_MIN <= dur <= IDEAL_MAX: local += 2
            if not best or local > best["localScore"]:
                best = {"endT": s2["endT"], "localScore": local, "payoffText": s2["text"]}
        if not best: continue

        max_t = clip_start + MAX_DUR
        clip_end = snap_to_cap_end(best["endT"], max_t, transcription)
        dur = clip_end - clip_start

        clip_sents = [s for s in sentences if s["startT"] >= clip_start and s["endT"] <= clip_end + 0.5]
        clip_text = " ".join(s["text"] for s in clip_sents).lower()
        score = hs + best["localScore"]
        eng_count = sum(1 for w in ENG_WORDS if w in clip_text)
        score += min(eng_count, 8)
        q_count = sum(1 for s in clip_sents if s["type"] == "question")
        score += min(q_count * 2, 6)
        stat_count = len(re.findall(r'\d+\s*%', clip_text))
        score += stat_count * 3
        if IDEAL_MIN <= dur <= IDEAL_MAX: score += 5
        elif dur < 20: score -= 10
        elif dur > 180: score -= 5
        overlap_titles = [t for t in titles if t.get("endSec", 0) > clip_start and t.get("startSec", 0) < clip_end]
        score += min(len(overlap_titles) * 2, 8)

        hero = next((t for t in overlap_titles if t.get("style") in ("hero", "flash")), None)
        topic = (hero["text"] if hero else re.sub(r'[.?!…]+$', '', hook["text"])[:55])

        candidates.append({
            "startSec": clip_start,
            "endSec": clip_end,
            "duration": dur,
            "score": score,
            "topic": topic,
            "hookText": hook["text"],
            "payoffText": best["payoffText"],
            "titleCount": len(overlap_titles),
            "titles": [t.get("text", "") for t in overlap_titles],
            "titleObjects": overlap_titles,
        })

    candidates.sort(key=lambda c: -c["score"])
    selected = []
    for c in candidates:
        overlaps = any(c["startSec"] < s["endSec"] - 1 and c["endSec"] > s["startSec"] + 1 for s in selected)
        if not overlaps: selected.append(c)
        if len(selected) >= 10: break

    style_idx = 0
    for clip in selected:
        if clip["titleCount"] >= 4:
            clip["style"] = "textHeavy"
        elif any(STAT_RE.search(t) for t in clip["titles"]):
            clip["style"] = "splitScreen"
        elif clip["score"] >= 30:
            clip["style"] = "zoomPunchIn"
        else:
            clip["style"] = STYLES_ROTATION[style_idx % len(STYLES_ROTATION)]
            style_idx += 1

    selected.sort(key=lambda c: c["startSec"])

    out_clips = []
    for i, c in enumerate(selected, start=1):
        clip_brolls = [b for b in brolls if b.get("endSec", 0) > c["startSec"] and b.get("startSec", 0) < c["endSec"]]
        out_clips.append({
            "index": i,
            "startSec": round(c["startSec"] * 10) / 10,
            "endSec": round(c["endSec"] * 10) / 10,
            "duration": round(c["duration"] * 10) / 10,
            "topic": c["topic"],
            "score": c["score"],
            "style": c["style"],
            "hookText": c["hookText"],
            "payoffText": c["payoffText"],
            "titleCount": c["titleCount"],
            "titles": c["titles"],
            "titleObjects": c["titleObjects"],
            "brollObjects": clip_brolls,
        })
    return out_clips, len(candidates)


def main():
    if len(sys.argv) < 2:
        print("uso: python analyze_shorts_offline.py <caminho-projeto> [--threshold N]")
        sys.exit(1)
    proj = Path(sys.argv[1])
    if not proj.is_absolute():
        proj = Path(__file__).parent / proj
    threshold = DEFAULT_THRESHOLD
    args = sys.argv[2:]
    while args:
        a = args.pop(0)
        if a == "--threshold" and args:
            threshold = int(args.pop(0))
    config_path = proj / "edit_config.json"
    trans_path = proj / "transcription.json"
    if not config_path.exists():
        print(f"ERRO: {config_path} nao existe"); sys.exit(1)
    if not trans_path.exists():
        print(f"ERRO: {trans_path} nao existe"); sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        edit_config = json.load(f)
    with open(trans_path, "r", encoding="utf-8") as f:
        transcription = json.load(f)

    clips, total = analyze_shorts(edit_config, transcription, hook_threshold=threshold)
    edit_config["motionforge_clips"] = clips

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(edit_config, f, ensure_ascii=False, indent=2)

    print(f"OK: {len(clips)} shorts salvos em {config_path} (candidatos totais: {total})")
    for c in clips:
        print(f"  #{c['index']:02d} [{c['startSec']:6.1f}s -> {c['endSec']:6.1f}s] ({c['duration']:5.1f}s) "
              f"score={c['score']:3} style={c['style']:15} | {c['topic'][:60].encode('ascii', 'replace').decode()}")


if __name__ == "__main__":
    main()
