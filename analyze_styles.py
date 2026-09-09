#!/usr/bin/env python3
"""
MotionForge — Gemini Video Style Analyzer
Analisa um vídeo usando a Gemini API e extrai estilos de títulos/textos animados.
Retorna JSON com definições de estilo compatíveis com o editor MotionForge.

Uso:
  python analyze_styles.py <video_path_or_url> [--api-key KEY] [--model MODEL]

Requer:
  pip install google-genai
"""
import os, sys, json, time, argparse, tempfile, re
from datetime import datetime, timezone

def download_video(url: str, output_dir: str) -> str:
    """Download video from URL using yt-dlp if needed."""
    import subprocess
    ext = os.path.splitext(url.split("?")[0])[-1].lower()
    if ext in (".mp4", ".webm", ".mov", ".avi"):
        # Direct download
        import urllib.request
        fname = os.path.join(output_dir, "input_video" + ext)
        urllib.request.urlretrieve(url, fname)
        return fname
    else:
        # Use yt-dlp for YouTube/social media
        fname = os.path.join(output_dir, "input_video.mp4")
        subprocess.run([
            "yt-dlp", "-f", "best[height<=1080]",
            "--merge-output-format", "mp4",
            "-o", fname, url
        ], check=True, capture_output=True)
        return fname


def _anotar_gasto(resp, model: str) -> None:
    """Anota o custo desta analise no mesmo livro que o servidor usa.

    Escreve direto no JSONL em vez de chamar o servidor: este script roda como
    processo separado e precisa funcionar tambem quando alguem o executa a mao,
    com o Klipe fechado. Anexar linha e atomico o bastante para os dois
    escreverem sem combinar nada.

    Nunca levanta excecao: perder a anotacao do gasto nao pode custar a analise
    que acabou de ser paga.
    """
    try:
        import os as _os
        from pathlib import Path as _P

        u = getattr(resp, "usage_metadata", None)
        if u is None:
            return
        ent = int(getattr(u, "prompt_token_count", 0) or 0)
        sai = int(getattr(u, "candidates_token_count", 0) or 0)
        if not ent and not sai:
            return

        pasta = _P(_os.environ.get("LOCALAPPDATA", _P.home())) / "Klipe"
        # As tarifas sao as mesmas que a tela mostra; se o usuario ajustou la,
        # e o valor dele que vale aqui.
        taxas = {"tarifa_gemini_mtok_in": 0.10, "tarifa_gemini_mtok_out": 0.40}
        try:
            cfg = json.loads((pasta / "klipe_settings.json").read_text(encoding="utf-8"))
            for k in taxas:
                v = float(cfg.get(k, taxas[k]))
                if v >= 0:
                    taxas[k] = v
        except Exception:
            pass

        custo = ent / 1e6 * taxas["tarifa_gemini_mtok_in"] + sai / 1e6 * taxas["tarifa_gemini_mtok_out"]
        linha = {
            "quando": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "tipo": "gemini", "modelo": model, "segundos": 0,
            "tokensEntrada": ent, "tokensSaida": sai,
            "tarifa": 0, "custo": round(custo, 4), "moeda": "USD", "projeto": "",
        }
        pasta.mkdir(parents=True, exist_ok=True)
        with open(pasta / "gastos.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(linha) + "\n")
        print(f"[MotionForge] analise: {ent}+{sai} tokens = US$ {custo:.4f}", file=sys.stderr)
    except Exception as e:
        print(f"[MotionForge] nao consegui anotar o gasto ({e})", file=sys.stderr)


def analyze_video_styles(video_path: str, api_key: str = None, model: str = None) -> dict:
    """
    Upload video to Gemini and analyze all text/title overlays and animations.
    Returns structured JSON with style definitions.
    """
    try:
        from google import genai
    except ImportError:
        return {"error": "google-genai not installed. Run: pip install google-genai"}

    api_key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"error": "GEMINI_API_KEY not set. Pass --api-key or set environment variable."}

    model = model or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

    client = genai.Client(api_key=api_key)

    # Upload video
    try:
        print(f"[MotionForge] Uploading video: {video_path}", file=sys.stderr)
        uploaded = client.files.upload(file=video_path)
    except Exception as e:
        return {"error": f"Failed to upload video: {str(e)}"}

    # Wait for processing
    max_wait = 300  # 5 minutes
    waited = 0
    while getattr(uploaded, "state", None) and getattr(uploaded.state, "name", "") == "PROCESSING":
        if waited >= max_wait:
            return {"error": "Video processing timed out after 5 minutes"}
        time.sleep(3)
        waited += 3
        uploaded = client.files.get(name=uploaded.name)
        print(f"[MotionForge] Processing... ({waited}s)", file=sys.stderr)

    if getattr(uploaded, "state", None) and getattr(uploaded.state, "name", "") == "FAILED":
        return {"error": "Gemini failed to process the video"}

    # Analysis prompt
    prompt = """Analise este vídeo e identifique TODOS os textos/títulos animados que aparecem na tela.

Para CADA texto/título encontrado, extraia:

1. **timing**: segundo de início e fim (startSec, endSec)
2. **text**: o texto exato que aparece
3. **style_description**: descrição detalhada do estilo visual:
   - Família tipográfica (serif, sans-serif, display, monospace)
   - Peso (regular, bold, black, light)
   - Tamanho aproximado relativo à tela (pequeno, médio, grande, gigante)
   - Cor do texto (hex ou nome)
   - Background/fundo (transparente, caixa colorida, gradiente, blur)
   - Alinhamento (esquerda, centro, direita)
   - Caixa (MAIÚSCULA, minúscula, Normal)
4. **animation_in**: como o texto ENTRA na tela:
   - Tipo: fade, slide-left, slide-right, slide-up, slide-down, scale-up, scale-down, blur-in, typewriter, flicker, bounce, rotate-in, none
   - Duração aproximada em segundos
5. **animation_out**: como o texto SAI da tela (mesmos tipos)
6. **position**: posição na tela:
   - vertical: top, center, bottom, lower-third
   - horizontal: left, center, right
   - Coordenadas aproximadas em % (posX: 0-100, posY: 0-100)
7. **layers**: se o título é composto por múltiplas linhas/camadas com animações diferentes, liste cada camada separadamente
8. **effects**: efeitos especiais (sombra, glow, outline, distortion, glitch, etc.)
9. **suggested_motionforge_style**: qual estilo do MotionForge mais se aproxima:
   - hero: título grande centralizado, Bebas Neue
   - lower3rd: barra inferior com nome/cargo
   - credit: nome + credencial com linha separadora
   - kinetic: texto palavra por palavra, tipo teleprompter
   - counter: número grande + texto
   - panel: lista de itens com bullet points
   - quote: citação com aspas decorativas
   - flash: texto de impacto rápido, fullscreen
   - ribbon: faixa horizontal com texto
   - compound: título multi-linha com animações diferentes por linha
   - compound2: igual compound mas com efeitos blur/flicker
   - NEW: se nenhum estilo existente serve, sugira um nome para novo estilo

Retorne APENAS um JSON válido (sem markdown, sem code fences) no formato:
{
  "styles_found": [
    {
      "startSec": 2.5,
      "endSec": 5.0,
      "text": "TEXTO AQUI",
      "style_description": {
        "font_family": "sans-serif",
        "font_weight": "bold",
        "font_size": "large",
        "color": "#FFFFFF",
        "background": "none",
        "alignment": "center",
        "text_transform": "uppercase"
      },
      "animation_in": { "type": "slide-up", "duration": 0.5 },
      "animation_out": { "type": "fade", "duration": 0.3 },
      "position": { "vertical": "center", "horizontal": "center", "posX": 50, "posY": 50 },
      "layers": [
        {
          "text": "LINHA 1",
          "font_weight": "bold",
          "font_size": "large",
          "color": "#FFFFFF",
          "animation_in": "slide-left"
        }
      ],
      "effects": ["shadow", "glow"],
      "suggested_motionforge_style": "hero"
    }
  ],
  "video_info": {
    "duration_sec": 30,
    "resolution": "1080x1920",
    "total_titles_found": 5
  },
  "style_summary": "Descrição geral do estilo visual do vídeo (paleta de cores, vibe, referências)"
}"""

    # Send to Gemini with retries
    max_retries = 4
    for attempt in range(max_retries):
        try:
            print(f"[MotionForge] Analyzing (attempt {attempt + 1})...", file=sys.stderr)
            resp = client.models.generate_content(
                model=model,
                contents=[uploaded, prompt]
            )

            _anotar_gasto(resp, model)

            raw = resp.text.strip()
            # Remove markdown code fences if present
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
                raw = re.sub(r"\n?```\s*$", "", raw)

            result = json.loads(raw)
            print(f"[MotionForge] Analysis complete!", file=sys.stderr)

            # Clean up uploaded file
            try:
                client.files.delete(name=uploaded.name)
            except:
                pass

            return result

        except json.JSONDecodeError as e:
            # Try to extract JSON from response
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                try:
                    result = json.loads(match.group())
                    return result
                except:
                    pass
            if attempt == max_retries - 1:
                return {"error": f"Failed to parse Gemini response as JSON: {str(e)}", "raw_response": raw[:2000]}

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate" in err_str.lower():
                wait = (attempt + 1) * 5
                print(f"[MotionForge] Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
            elif attempt == max_retries - 1:
                return {"error": f"Gemini API error: {err_str}"}
            else:
                time.sleep(2)

    return {"error": "Max retries exceeded"}


def convert_to_motionforge_clips(analysis: dict) -> list:
    """
    Convert Gemini analysis results into MotionForge-compatible clip definitions.
    Returns a list of title clips ready to be added to the editor.
    """
    clips = []
    styles_found = analysis.get("styles_found", [])

    for i, style in enumerate(styles_found):
        clip = {
            "id": f"ai_{i}_{int(time.time())}",
            "startSec": style.get("startSec", 0),
            "endSec": style.get("endSec", 3),
            "text": style.get("text", ""),
            "style": _map_to_motionforge_style(style),
        }

        # Map position
        pos = style.get("position", {})
        if pos.get("posX") is not None:
            clip["posX"] = (pos["posX"] / 100) * 1920 - 960  # Convert % to px offset from center
        if pos.get("posY") is not None:
            clip["posY"] = (pos["posY"] / 100) * 1080 - 540

        clips.append(clip)

    return clips


def _map_to_motionforge_style(style_data: dict) -> str:
    """Map Gemini's suggestion to a valid MotionForge style."""
    suggested = style_data.get("suggested_motionforge_style", "hero")
    valid = ["hero", "lower3rd", "credit", "kinetic", "counter", "panel", "quote", "flash", "ribbon", "compound", "compound2"]

    if suggested in valid:
        return suggested

    # Fuzzy match
    suggested_lower = suggested.lower()
    if "compound" in suggested_lower:
        return "compound"
    if "lower" in suggested_lower or "third" in suggested_lower or "bar" in suggested_lower:
        return "lower3rd"
    if "flash" in suggested_lower or "impact" in suggested_lower:
        return "flash"
    if "quote" in suggested_lower or "cita" in suggested_lower:
        return "quote"
    if "credit" in suggested_lower or "nome" in suggested_lower:
        return "credit"
    if "ribbon" in suggested_lower or "faixa" in suggested_lower:
        return "ribbon"

    return "hero"  # Default fallback


def main():
    parser = argparse.ArgumentParser(description="MotionForge Gemini Video Style Analyzer")
    parser.add_argument("video", help="Video file path or URL")
    parser.add_argument("--api-key", help="Gemini API key (or set GEMINI_API_KEY env)")
    parser.add_argument("--model", help="Gemini model (default: gemini-2.0-flash)")
    parser.add_argument("--clips", action="store_true", help="Also output MotionForge clip definitions")
    args = parser.parse_args()

    video_path = args.video

    # Download if URL
    if video_path.startswith("http://") or video_path.startswith("https://"):
        tmpdir = tempfile.mkdtemp(prefix="mf_analyze_")
        try:
            video_path = download_video(video_path, tmpdir)
        except Exception as e:
            print(json.dumps({"error": f"Failed to download video: {str(e)}"}))
            sys.exit(1)

    if not os.path.isfile(video_path):
        print(json.dumps({"error": f"Video file not found: {video_path}"}))
        sys.exit(1)

    result = analyze_video_styles(video_path, api_key=args.api_key, model=args.model)

    if args.clips and "styles_found" in result:
        result["motionforge_clips"] = convert_to_motionforge_clips(result)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
