#!/usr/bin/env python3
"""
transcribe_klipe.py — Transcreve video pra formato Klipe (segment-level JSON)

Usa faster-whisper (GPU CUDA) com large-v3 default. Gera transcription.json
em public/projects/<project>/ com formato:
  [{"start": 0.0, "end": 4.68, "text": "..."}, ...]

Uso:
  python transcribe_klipe.py <project> [--model large-v3] [--lang pt]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT / "public" / "projects"


def transcribe(project, model_name="large-v3", language="pt"):
    proj_dir = PROJECTS / project
    if not proj_dir.exists():
        print(f"FAIL: projeto nao existe: {proj_dir}")
        sys.exit(1)

    video_path = proj_dir / "video.mp4"
    if not video_path.exists():
        video_path = proj_dir / "video_preview.mp4"
    if not video_path.exists():
        print(f"FAIL: video.mp4 ou video_preview.mp4 nao encontrado em {proj_dir}")
        sys.exit(1)

    out_path = proj_dir / "transcription.json"
    print(f"[Transcribe] Source: {video_path}")
    print(f"[Transcribe] Model: faster-whisper {model_name} | Lang: {language}")

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("FAIL: faster_whisper nao instalado")
        sys.exit(1)

    # GPU primeiro, CPU se falhar. A queda tem que cobrir o USO do modelo, e
    # nao so a construcao: com as libs da NVIDIA ausentes o modelo CARREGA na
    # GPU e so quebra ao codificar o primeiro trecho — "cublas64_12.dll is not
    # found". O try antigo pegava so a construcao, entao a transcricao morria
    # com um erro de DLL que nao diz nada a quem so queria a legenda.
    def _carregar():
        if os.environ.get("KLIPE_WHISPER_CPU"):
            print("[Transcribe] CPU por pedido (KLIPE_WHISPER_CPU)")
            return WhisperModel(model_name, device="cpu", compute_type="int8"), True
        try:
            m = WhisperModel(model_name, device="cuda", compute_type="float16")
            # Prova de fogo: encoda 1s de silencio. Se as libs faltam, estoura
            # AQUI, onde ainda da para cair para a CPU, e nao no meio do video.
            import numpy as _np
            list(m.transcribe(_np.zeros(16000, dtype=_np.float32), language=language)[0])
            print("[Transcribe] GPU (float16)")
            return m, False
        except Exception as e:
            print(f"[Transcribe] GPU indisponivel ({str(e)[:80]}), indo de CPU int8")
            return WhisperModel(model_name, device="cpu", compute_type="int8"), True

    model, em_cpu = _carregar()

    from motioncore.glossario import corrigir as _corrigir, hotwords as _hw, termos
    _termos = termos(project)
    _hotwords = _hw(_termos)
    if _termos:
        print(f"[Transcribe] Glossario: {len(_termos)} termos "
              f"({', '.join(_termos[:6])}{'...' if len(_termos) > 6 else ''})")
    else:
        print("[Transcribe] Glossario vazio — nenhum termo enviesando o modelo")

    print(f"[Transcribe] Iniciando...")
    t0 = time.time()
    segments_iter, info = model.transcribe(
        str(video_path),
        language=language,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
        condition_on_previous_text=False,  # evita hallucination loops
        # Tempo por PALAVRA. E o que permite cortar pelo texto como no Premiere:
        # sem isto so da para apagar a frase inteira, e a frase inteira quase
        # nunca e a unidade que a pessoa quer tirar — ela quer tirar o "e...",
        # a repeticao, o comeco falso.
        #
        # Custa ~15% a mais de tempo de transcricao. Vale: refazer a transcricao
        # so para ganhar as palavras custaria o dobro.
        word_timestamps=True,
        # Os termos que o Whisper nao conhece, enviesando CADA janela de audio.
        # Sem isto ele transcreve o que soa parecido e que ja viu muito:
        # "MotionCore" vira "motion core", "Klipe" vira "clipe". `hotwords` age
        # ANTES do erro — a correcao depois so limpa o que escapou.
        hotwords=_hotwords,
    )

    _trocas_total = []

    print(f"[Transcribe] Lang detectado: {info.language} ({info.language_probability:.2%})")
    print(f"[Transcribe] Duracao audio: {info.duration:.1f}s")

    segments = []
    for s in segments_iter:
        # `words` entra como campo A MAIS: transcricao antiga sem ele continua
        # valendo, e quem le decide se usa a palavra ou a frase.
        palavras = []
        for w in (getattr(s, "words", None) or []):
            txt = (w.word or "").strip()
            if not txt:
                continue
            palavras.append({"start": round(w.start, 3), "end": round(w.end, 3),
                             "text": txt, "prob": round(getattr(w, "probability", 1.0), 3)})
        # Segunda camada: o que o `hotwords` nao evitou, a semelhanca conserta.
        # So o TEXTO muda — `start` e `end` ficam intactos, senao o corte pelo
        # texto passaria a cortar o pedaco errado do video.
        if _termos and palavras:
            palavras, _tr = _corrigir(palavras, _termos)
            _trocas_total += _tr
        segments.append({
            "start": round(s.start, 2),
            "end": round(s.end, 2),
            # a frase e remontada das palavras corrigidas; usar `s.text` cru
            # deixaria legenda por frase e legenda por palavra discordando
            "text": (" ".join(w["text"] for w in palavras).strip()
                     if (_termos and palavras) else s.text.strip()),
            "words": palavras,
        })
        # Progress
        if len(segments) % 20 == 0:
            pct = (s.end / info.duration) * 100
            print(f"  ... {len(segments)} segmentos | {s.end:.0f}s / {info.duration:.0f}s ({pct:.0f}%)", flush=True)

    elapsed = time.time() - t0
    print(f"[Transcribe] Pronto em {elapsed:.1f}s | {len(segments)} segmentos")
    _relatar_glossario(_trocas_total)

    out_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Transcribe] Saved -> {out_path}")
    print(f"[Transcribe] Sample primeiros 3 segmentos:")
    for s in segments[:3]:
        print(f"  [{s['start']:.2f}s -> {s['end']:.2f}s] {s['text'][:80]}")


def _relatar_glossario(trocas):
    """Toda troca aparece. Correcao automatica que ninguem ve e correcao em que
    ninguem pode confiar — e a lista tambem ensina qual termo esta faltando."""
    if not trocas:
        return
    print(f"[Transcribe] Glossario corrigiu {len(trocas)} palavra(s):")
    for antes, depois, t in trocas[:20]:
        print(f"             {t:7.2f}s  {antes!r} -> {depois!r}")
    if len(trocas) > 20:
        print(f"             ... e mais {len(trocas) - 20}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--model", default="large-v3", help="Whisper model: tiny|base|small|medium|large-v3")
    ap.add_argument("--lang", default="pt", help="Language code (pt, en, es, etc)")
    args = ap.parse_args()
    transcribe(args.project, args.model, args.lang)


if __name__ == "__main__":
    main()
