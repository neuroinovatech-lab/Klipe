#!/usr/bin/env python3
"""
gen_abuso_config.py — Gera edit_config.json pro projeto abuso-mulheres-autistas.

Inclui: 47 titles, 24 zooms, 5 music tracks, captions karaoke, color, progress bar.
NAO inclui: SFX, brolls, motions custom (deixados pra fases seguintes).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
PROJECT = "abuso-mulheres-autistas"
PROJ_DIR = PUBLIC / "projects" / PROJECT
SRC_REL = f"projects/{PROJECT}/video_preview.mp4"

# ============= TITLES (~50) =============
# Timestamps REAIS do video consolidado (818.12s) — re-transcrito apos consolidate
# (start, end, style, text)
TITLES = [
    # Bloco 1: Hook + Intro (0-50s)
    # MOTION-BROLL #1: ALERTA ABERTURA (silhueta + triangle + texto reveal)
    (0.5, 8.5, "alertaAbertura", "ABUSO|contra mulheres autistas"),
    (6.0, 9.0, "lower3rd", "Uma aula extremamente importante"),
    (9.7, 13.5, "credit", "Dra. Eli | Médica · Mestre em TEA"),
    (14.5, 20.0, "ribbon", "O risco aumenta para nós"),
    (22.0, 29.5, "lower3rd", "Literalidade · Dificuldade em ler intenções"),
    (31.0, 35.5, "flash", "PRESA FÁCIL"),
    (37.0, 44.5, "panel", "Entender o abuso|Identificar|Se proteger"),
    # Bloco 2: Por que vulneráveis (50-124s)
    (50.5, 56.5, "ribbon", "Mais vulneráveis a relacionamentos abusivos"),
    (57.7, 63.5, "panel", "Emocional|Manipulação|Física|Sexual"),
    (68.5, 74.0, "lower3rd", "Ensinadas a obedecer desde pequenas"),
    (75.0, 82.8, "panel", "Não questionar|Parecer normais|Buscar aceitação"),
    (96.5, 106.5, "lower3rd", "O abuso nem sempre é explícito"),
    (108.0, 117.0, "hero", "Anos sem perceber"),
    # Bloco 3: 5 Tipos de Abuso (124-282s)
    (124.5, 126.5, "ribbon", "Vamos direto ao ponto"),
    (127.0, 133.0, "hero", "5 TIPOS DE ABUSO"),
    (134.0, 140.0, "flash", "1. EMOCIONAL"),
    (140.5, 150.5, "lower3rd", "Manipulação · Desvalorização · Culpa"),
    # MOTION-BROLL: chat bubble com 2 frases manipuladoras citadas literalmente
    (151.0, 159.5, "chatBubble", "Você nunca vai encontrar alguém melhor que eu|Se você realmente me amasse, faria isso por mim"),
    (165.0, 168.5, "flash", "2. PSICOLÓGICO"),
    (169.0, 187.0, "lower3rd", "Usa suas inseguranças contra você"),
    # MOTION-BROLL #7: mentalChaos — palavras flutuantes da manipulação
    (185.0, 196.0, "mentalChaos", "EU TE AMO|VC ENTENDEU ERRADO|EU SÓ FAÇO POR VC|É CULPA SUA|VC ESTÁ EXAGERANDO|NÃO FOI ISSO"),
    (193.5, 196.0, "flash", "3. SEXUAL"),
    # MOTION-BROLL #8: compareVisual X vs ✓
    (197.0, 207.5, "compareVisual", "Sem consentimento|Consentimento claro"),
    (205.0, 213.0, "lower3rd", "Inclui insistência e coação"),
    (225.0, 233.0, "quote", "Não precisa ser penetração"),
    (242.0, 244.5, "flash", "4. FINANCEIRO"),
    (245.0, 263.0, "lower3rd", "Controle do dinheiro = controle de você"),
    (265.0, 267.0, "flash", "5. FÍSICO"),
    (282.0, 301.0, "panel", "Romance|Família|Trabalho|Faculdade|Profissional de saúde"),
    # Bloco 4: Por que mais vulneráveis (302-396s)
    (302.5, 312.0, "hero", "Por que MAIS vulneráveis?"),
    (313.0, 322.0, "lower3rd", "Não captamos nuance social"),
    # MOTION-BROLL: chat bubble com a frase de manipulacao
    (323.3, 329.0, "chatBubble", "Eu só faço isso porque eu te amo"),
    (329.5, 341.0, "quote", "Podemos acreditar sem questionar"),
    (372.7, 384.0, "lower3rd", "Hipossexualidade — pressão pra ceder"),
    (385.5, 395.5, "lower3rd", "Hipersexualidade — exploração"),
    # Bloco 5: Sinais (396-479s)
    (396.5, 411.5, "hero", "SINAIS de abuso"),
    # MOTION-BROLL #1 (sem pessoa): sensoryOverload — sinais de alerta voando
    (412.5, 437.0, "sensoryOverload", "MEDO|ANSIEDADE|CULPA|ISOLAMENTO|SEMPRE CEDER|GASLIGHTING"),
    (437.5, 452.5, "panel", "Sempre você cede|Insiste após o NÃO|Te afasta dos seus"),
    (453.0, 464.5, "kinetic", "GASLIGHTING DE NOVO"),
    # Bloco 6: Como se proteger (480-595s)
    # MOTION-BROLL #10: microAcoes — 4 passos pra se proteger
    (480.5, 502.0, "microAcoes", "Confiar|Limites|Plano|Apoio"),
    (509.5, 523.0, "notification", "Confie no seu desconforto"),
    # MOTION-BROLL: NAO grande pulsando (frase chave da Dra Eli)
    (524.0, 537.5, "naoPulsa", "NÃO|É UMA FRASE COMPLETA"),
    (538.5, 549.5, "lower3rd", "Se desrespeita uma vez, vai fazer de novo"),
    # MOTION-BROLL #2: uiMockup — app de plano de segurança
    (565.5, 590.0, "uiMockup", "Plano de Segurança|Contato de confiança|Local seguro pra ir|Documentos importantes|Não isolar das amigas"),
    # Bloco 7: Como sair (596-672s)
    (597.0, 612.5, "hero", "Como SAIR"),
    # MOTION-BROLL: flowDiagram causal (passos pra sair de relacionamento abusivo)
    (615.5, 644.5, "flowDiagram", "Plano de saída|Peça ajuda|Registre provas|Não confronte sozinha"),
    (660.5, 671.0, "lower3rd", "Não confronte sozinha"),
    # Bloco 8: Abuso médico (672-748s)
    (672.0, 685.0, "ribbon", "Abuso pode vir de profissional de saúde"),
    (700.5, 717.0, "terminal", "Abuso = autonomia · dor · consentimento"),
    # MOTION-BROLL #9: documentLei — direitos genéricos (sem se passar por lei específica)
    (725.5, 745.0, "documentLei", "Em Consulta Médica|Recusar qualquer exame ou procedimento|Pedir acompanhante de confiança|Sair da situação se não se sente segura"),
    # Bloco 9: Conclusão (748-815s)
    (749.0, 765.0, "hero", "Não é sua culpa"),
    (773.5, 793.0, "hero", "VOCÊ MERECE RESPEITO"),
    (793.0, 803.0, "ribbon", "O abuso pode ser interrompido"),
    (809.0, 815.5, "socialCta", "Compartilhe · Ajude outra mulher autista"),
]

# ============= ZOOMS (24) — timestamps reais consolidado =============
# (start, end, direction, intensity, easing)
# Distribuicao: 9 hardIn, 9 in, 3 out, 3 hardOut
ZOOMS = [
    # Hook + intro
    (0.5, 6.0, "in", 1.10, "smooth"),
    (14.5, 20.5, "hardIn", 1.25, "easeOutCubic"),
    (31.0, 36.5, "hardIn", 1.28, "easeOutCubic"),
    (44.5, 50.5, "out", 1.0, "smooth"),
    # Vulneráveis
    (50.5, 64.0, "in", 1.12, "smooth"),
    (96.5, 107.0, "in", 1.10, "smooth"),
    (108.0, 124.0, "hardIn", 1.30, "easeOutCubic"),
    (124.0, 127.0, "out", 1.0, "smooth"),
    # 5 tipos
    (127.0, 133.5, "hardIn", 1.32, "easeOutCubic"),
    (134.0, 150.5, "in", 1.12, "smooth"),
    (165.0, 187.0, "in", 1.12, "smooth"),
    (187.6, 193.0, "hardIn", 1.28, "easeOutCubic"),
    (197.0, 213.0, "hardIn", 1.25, "easeOutCubic"),
    (225.0, 233.0, "in", 1.10, "smooth"),
    (242.0, 263.0, "in", 1.12, "smooth"),
    (265.0, 282.0, "hardOut", 1.0, "easeOutCubic"),
    # Vulneráveis 2
    (302.5, 312.0, "hardIn", 1.28, "easeOutCubic"),
    (329.5, 341.0, "in", 1.10, "smooth"),
    # Sinais
    (396.5, 412.0, "hardIn", 1.30, "easeOutCubic"),
    (453.0, 464.5, "hardIn", 1.32, "easeOutCubic"),
    (464.5, 480.0, "out", 1.0, "smooth"),
    # Proteger / Sair
    (480.5, 502.0, "in", 1.15, "smooth"),
    (524.0, 537.5, "hardOut", 1.0, "easeOutCubic"),
    # Conclusao
    (773.5, 815.0, "hardOut", 1.0, "easeOutCubic"),
]

# ============= BROLLS (10 sugeridos — user baixa de Pexels) =============
# (start, end, filename, label, fallback_text)
# Filename: arquivo esperado em projects/abuso-mulheres-autistas/brolls/
# Fallback: enquanto user nao baixa, mostra texto minimalist
BROLLS = [
    (6.0,   12.0, "broll_woman_thinking.mp4",     "Mulher autista pensativa",        "AUTISMO + ABUSO"),
    (70.0,  82.0, "broll_girl_obey.mp4",          "Menina sendo ensinada a obedecer","ENSINADAS A OBEDECER"),
    (108.0, 124.0,"broll_calendar_years.mp4",     "Calendario passando anos",        "ANOS SEM PERCEBER"),
    (210.0, 222.0,"broll_no_pressure.mp4",        "Mulher pressionada / desconforto","SEM CONSENTIMENTO"),
    (250.0, 264.0,"broll_money_control.mp4",      "Controle financeiro/dinheiro",     "CONTROLE = ABUSO"),
    (290.0, 301.0,"broll_workplace_uncomfort.mp4","Locais de abuso (trab/fam/medico)","EM TODO LUGAR"),
    (412.0, 437.0,"broll_anxious_alone.mp4",      "Mulher ansiosa sozinha",          "MEDO · ANSIEDADE"),
    (615.0, 645.0,"broll_packing_leaving.mp4",    "Mulher fazendo as malas",         "PLANO DE SAIDA"),
    (695.0, 725.0,"broll_doctor_office.mp4",      "Consultorio medico",              "ABUSO MEDICO"),
    (793.0, 815.0,"broll_empowered_woman.mp4",    "Mulher livre/empoderada",         "VOCE MERECE LIBERDADE"),
]

# ============= MUSIC (5 tracks segmentando 818s) =============
MUSICS = [
    # (start, end, src, vol, fadeIn, fadeOut, srcStart)
    (0,    180, "music/documentary/Soft Documentary Background.mp3",   0.06, 1.5, 2.5, 0),
    (175,  340, "music/documentary/Documentary Background.mp3",         0.07, 2.0, 2.5, 4),
    (335,  500, "music/documentary/Peaceful Reflection.mp3",             0.06, 2.0, 3.0, 0),
    (495,  690, "music/documentary/Documentary Cinematic.mp3",           0.07, 2.0, 3.0, 6),
    (685,  818.12, "music/documentary/Soft Documentary Background.mp3", 0.06, 2.0, 4.0, 8),
]

# ============= MAIN =============
def main():
    cfg_path = PUBLIC / "edit_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    # Preserva: videoDuration, videoSrc, videoClips, video* fields
    # Substitui: titles, zooms, musicTracks, captions (do transcription novo)
    # Mantem vazio: sfx, brolls, shapes (pra fase seguinte)

    new_dur = cfg["videoDuration"]

    # Captions do transcription novo (consolidado)
    trans_path = PROJ_DIR / "transcription.json"
    if trans_path.exists():
        trans = json.loads(trans_path.read_text(encoding="utf-8"))
        captions_out = []
        for i, seg in enumerate(trans):
            captions_out.append({
                "id": f"cap{i+1:03d}",
                "startSec": seg["start"],
                "endSec": seg["end"],
                "text": seg["text"],
            })
        cfg["captions"] = captions_out
        print(f"  Captions: {len(captions_out)} (regenerado do transcription)")

    # Titles
    titles_out = []
    for i, (s, e, style, text) in enumerate(TITLES):
        titles_out.append({
            "id": f"t{i+1:02d}",
            "startSec": s,
            "endSec": e,
            "text": text,
            "style": style,
        })

    # Zooms
    zooms_out = []
    for i, (s, e, d, intensity, easing) in enumerate(ZOOMS):
        z = {
            "id": f"z{i+1:02d}",
            "startSec": s,
            "endSec": e,
            "direction": d,
            "intensity": intensity,
            "easing": easing,
        }
        # originY default 50, mas em hardIn focar no rosto (32-35)
        if d in ("hardIn", "in") and intensity >= 1.20:
            z["originY"] = 32
        zooms_out.append(z)

    # Music
    music_out = []
    for i, (s, e, src, vol, fi, fo, ss) in enumerate(MUSICS):
        music_out.append({
            "id": f"mus{i+1:02d}",
            "startSec": s,
            "endSec": min(e, new_dur),
            "src": src,
            "volume": vol,
            "fadeIn": fi,
            "fadeOut": fo,
            "srcStart": ss,
        })

    # Aplica
    cfg["titles"] = titles_out
    cfg["zooms"] = zooms_out
    cfg["musicTracks"] = music_out
    # Brolls reais (baixados via download_brolls.py do Pexels)
    BROLL_DIR = PROJ_DIR / "brolls"
    brolls_out = []
    for i, (s, e, fname, label, _) in enumerate(BROLLS):
        broll_path = BROLL_DIR / fname
        if broll_path.exists():
            brolls_out.append({
                "id": f"br{i+1:02d}",
                "startSec": s, "endSec": e,
                "src": f"projects/{PROJECT}/brolls/{fname}",
                "label": label,
                "scale": 1.0, "opacity": 1.0,
            })
    cfg["brolls"] = brolls_out
    cfg["sfx"] = []        # FASE 2 — vazio por agora
    cfg["shapes"] = []

    # Captions karaoke (sobreescreve defaults se não tem)
    cfg["captionStyle"] = "words"
    cfg["captionKaraoke"] = True
    cfg["captionFont"] = "Montserrat"
    cfg["captionFontSize"] = 100
    cfg["captionColor"] = "#FFFFFF"
    cfg["captionHighlightColor"] = "#E8940A"
    cfg["captionMaxLines"] = 2
    cfg["captionBg"] = True

    # Color correction Dra Eli
    cfg["colorCorrection"] = {
        "brightness": 0,
        "contrast": 5,
        "saturation": -3,
        "temperature": 0,
    }

    # Progress bar
    cfg["showProgressBar"] = True
    cfg["barColor"] = "#E8940A"
    cfg["barHeight"] = 4

    # Salva nos 2 lugares
    out_active = PUBLIC / "edit_config.json"
    out_proj = PROJ_DIR / "edit_config.json"
    payload = json.dumps(cfg, ensure_ascii=False, indent=2)
    out_active.write_text(payload, encoding="utf-8")
    out_proj.write_text(payload, encoding="utf-8")

    print(f"[GenConfig] OK")
    print(f"  Titles: {len(titles_out)}")
    print(f"  Zooms:  {len(zooms_out)}")
    print(f"  Musics: {len(music_out)}")
    print(f"  SFX:    {len(cfg['sfx'])} (vazio)")
    print(f"  Brolls: {len(cfg['brolls'])} (reais do Pexels)")
    print(f"  Salvo em:")
    print(f"    {out_active}")
    print(f"    {out_proj}")

if __name__ == "__main__":
    main()
