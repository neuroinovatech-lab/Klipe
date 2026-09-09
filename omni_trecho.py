#!/usr/bin/env python3
"""
omni_trecho.py — manda UM trecho do vídeo pro OMNI e recebe o que fazer nele.

O OMNI **não edita vídeo**. Perguntamos direto (teste de 31/07) e a resposta
dele foi: *"Eu apenas analiso e descrevo o conteúdo do vídeo; não tenho a
capacidade de editar o arquivo e te devolver uma versão alterada."*

Então a divisão é essa:

    OMNI decide  →  o Klipe aplica

Ele assiste ao trecho (no máximo 10s, que é o limite prático), ouve o que ela
fala ali, lê o seu pedido — e devolve uma DECISÃO ESTRUTURADA: que elemento
entra, com que texto, em que segundo. Quem coloca na timeline é o Klipe, usando
o que ele já sabe fazer: b-roll, título, texto atrás da pessoa, zoom.

Por isso nem sempre vira b-roll. Se o trecho já tem imagem boa, ele pode pedir
só uma palavra atrás da pessoa; se ela enfatiza algo, um zoom.

Uso:
    python omni_trecho.py --inicio 368.75 --fim 378.25 --pedido "poe uma palavra
        forte atras dela quando ela fala de pertencer"
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
CFG = PUBLIC / "edit_config.json"
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
MODELO = "models/gemini-omni-flash-preview"
LIMITE_S = 10.0        # o OMNI so aceita trecho curto — acima disso ele recusa

# O que o Klipe sabe colocar num trecho. O OMNI escolhe SÓ entre estes.
ELEMENTOS = """
- "broll": imagem de cobertura gerada por IA (Veo). Use quando o que está em
  cena não ilustra o que ela fala. Precisa de `promptVeo` descrevendo a cena.
- "titulo": texto na tela. Precisa de `texto` e `estilo`. Estilos disponíveis:
  hero (virada de assunto), flash (impacto curto), kinetic (palavras em
  cascata), lower3rd (rodapé), quote (citação), pointList (lista), compound2
  (escada), ribbon (faixa), counter (número), panel (lista lateral),
  stackedReveal, mixedSerif, paradoxQuote, sensoryStorm, wordCollapse,
  echoWords, liveComments, letterEyebrow, descending.
- "zoom": aproximação. Precisa de `intensidade` (1.05 a 1.3) e `direcao`
  ("in", "out", "hardIn").
- "nada": o trecho já está bom. É uma resposta legítima — não force elemento.
"""


def transcricao_do_trecho(cfg: dict, ini: float, fim: float) -> str:
    partes = [c["text"].strip() for c in (cfg.get("captions") or [])
              if float(c["endSec"]) > ini and float(c["startSec"]) < fim]
    return " ".join(partes).strip()


def recortar(src: Path, ini: float, dur: float, destino: Path) -> bool:
    r = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-ss", f"{ini:.3f}", "-i", str(src), "-t", f"{dur:.3f}",
         # 480p e 12fps: o OMNI cobra por token de video e nao precisa de
         # resolucao cheia pra entender a cena
         "-vf", "scale=-2:480,fps=12", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", str(destino)],
        capture_output=True, text=True)
    return r.returncode == 0 and destino.exists() and destino.stat().st_size > 1000


def perguntar(video: Path, pedido: str, fala: str, ini: float, dur: float,
              chave: str) -> dict:
    esquema = {
        "tipo": "broll | titulo | zoom | nada",
        "porque": "uma frase dizendo por que isso e não outra coisa",
        "inicioRelativo": "segundo DENTRO do trecho onde o elemento entra (0 a %.1f)" % dur,
        "duracao": "quantos segundos dura",
        "texto": "só pra titulo — TEM que sair da fala dela",
        "estilo": "só pra titulo",
        "promptVeo": "só pra broll — descrição da cena, em inglês",
        "intensidade": "só pra zoom",
        "direcao": "só pra zoom",
    }
    pergunta = f"""Você é assistente de edição de vídeo. Assista a este trecho de {dur:.1f}s.

O QUE ELA FALA AQUI: "{fala or '(sem fala)'}"

PEDIDO DO EDITOR: {pedido}

Escolha UM elemento pra colocar neste trecho, entre estes:
{ELEMENTOS}

REGRA DURA: se o elemento tiver texto, ele TEM que ser recorte do que ela fala.
Nunca invente frase que ela não disse.

Responda SÓ com um JSON, sem cercas de código, neste formato:
{json.dumps(esquema, ensure_ascii=False, indent=1)}"""

    body = {"model": MODELO, "input": [{"type": "user_input", "content": [
        {"type": "video", "data": base64.b64encode(video.read_bytes()).decode(),
         "mime_type": "video/mp4"},
        {"type": "text", "text": pergunta},
    ]}]}
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode(),
        headers={"x-goog-api-key": chave, "Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        bruto = json.loads(r.read())
    dt = time.time() - t0

    textos = []

    def _colher(o):
        if isinstance(o, list):
            for x in o:
                _colher(x)
        elif isinstance(o, dict):
            for k, v in o.items():
                if k == "text" and isinstance(v, str) and len(v) > 2:
                    textos.append(v)
                else:
                    _colher(v)
    _colher(bruto)

    tokens = (bruto.get("usage") or {}).get("total_tokens")
    resposta = "\n".join(textos).strip()
    # o modelo às vezes devolve cercado em ```json
    if "```" in resposta:
        resposta = resposta.split("```")[1].lstrip("json").strip()
    try:
        decisao = json.loads(resposta)
    except Exception:
        return {"erro": "o OMNI nao devolveu JSON valido", "bruto": resposta[:600],
                "segundos": round(dt, 1), "tokens": tokens}
    decisao["_segundos"] = round(dt, 1)
    decisao["_tokens"] = tokens
    return decisao


def para_clip(dec: dict, ini_abs: float) -> dict | None:
    """Converte a decisão do OMNI num clip que o Klipe entende."""
    tipo = (dec.get("tipo") or "").strip()
    if tipo in ("", "nada"):
        return None
    ini = ini_abs + float(dec.get("inicioRelativo") or 0)
    dur = float(dec.get("duracao") or 4)
    base = {"startSec": round(ini, 2), "endSec": round(ini + dur, 2)}
    if tipo == "titulo":
        return {"_alvo": "titles", **base, "text": dec.get("texto", ""),
                "style": dec.get("estilo", "lower3rd")}
    if tipo == "zoom":
        return {"_alvo": "zooms", **base,
                "intensity": float(dec.get("intensidade") or 1.15),
                "direction": dec.get("direcao", "in"), "easing": "smooth"}
    if tipo == "broll":
        return {"_alvo": "brolls", **base, "_promptVeo": dec.get("promptVeo", ""),
                "label": (dec.get("porque") or "")[:40]}
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inicio", type=float, required=True)
    ap.add_argument("--fim", type=float, required=True)
    ap.add_argument("--pedido", required=True)
    ap.add_argument("--config", default=str(CFG))
    args = ap.parse_args()

    dur = args.fim - args.inicio
    if dur <= 0:
        print("fim tem que ser depois do inicio")
        return 1
    if dur > LIMITE_S:
        print(f"trecho de {dur:.1f}s — o OMNI so aceita ate {LIMITE_S:.0f}s. "
              f"Corte menor ou divida em pedacos.")
        return 1

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    chave = json.loads((ROOT / "klipe_settings.json").read_text(encoding="utf-8"))["gemini_key"]
    src = PUBLIC / cfg["videoSrc"]
    if not src.exists():
        print(f"video nao encontrado: {src}")
        return 1

    fala = transcricao_do_trecho(cfg, args.inicio, args.fim)
    with tempfile.TemporaryDirectory() as tmp:
        clipe = Path(tmp) / "trecho.mp4"
        print(f"recortando {dur:.1f}s a partir de {args.inicio:.2f}s...")
        if not recortar(src, args.inicio, dur, clipe):
            print("falhou o recorte")
            return 1
        print(f"  {clipe.stat().st_size/1e6:.1f} MB | fala: \"{fala[:70]}\"")
        print("perguntando pro OMNI...")
        dec = perguntar(clipe, args.pedido, fala, args.inicio, dur, chave)

    if dec.get("erro"):
        print(f"  {dec['erro']}")
        print(f"  resposta crua: {dec.get('bruto', '')[:300]}")
        return 1

    print(f"\nOMNI respondeu em {dec.get('_segundos')}s ({dec.get('_tokens')} tokens):")
    print(f"  tipo   : {dec.get('tipo')}")
    print(f"  porque : {dec.get('porque')}")
    for k in ("texto", "estilo", "promptVeo", "intensidade", "direcao"):
        if dec.get(k):
            print(f"  {k:<7}: {dec[k]}")

    clip = para_clip(dec, args.inicio)
    print("\nvira este clip no Klipe:")
    print("  " + (json.dumps(clip, ensure_ascii=False) if clip else "(nada — trecho ja esta bom)"))
    print(json.dumps({"decisao": dec, "clip": clip}, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
