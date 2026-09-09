#!/usr/bin/env python3
"""
download_brolls.py — Baixa brolls automaticamente do Pexels.

Uso:
  set PEXELS_API_KEY=xxxx
  python download_brolls.py abuso-mulheres-autistas

Requer:
  - Pexels API key (free): https://www.pexels.com/api/ → Get Started
  - requests (pip install requests)

Comportamento:
  - Lê lista de brolls hardcoded por projeto
  - Pra cada query, pesquisa em pexels.com/v1/videos
  - Baixa primeiro resultado HD (1080p preferido) MP4
  - Salva em public/projects/<project>/brolls/
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import requests
except ImportError:
    print("FAIL: pip install requests")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent
PROJECTS_DIR = ROOT / "public" / "projects"
PEXELS_API = "https://api.pexels.com/videos/search"

# ============= BROLLS POR PROJETO =============
BROLLS_CONFIG = {
    # Reel 9:16: profissional respondendo uma mae sobre suporte na
    # adolescencia. O b-roll cobre o trecho 46-58s, onde ele lista os
    # AMBIENTES que o adolescente frequenta — escola, igreja, esporte,
    # amigos. Cena cotidiana, nao imagem clinica: o assunto e a vida dele,
    # e ilustrar com jaleco e consultorio contaria outra historia.
    "reel-suporte": [
        ("broll_escola.mp4", "teenager walking school hallway",     "portrait", 5),
        ("broll_amigos.mp4", "teenagers group friends talking",     "portrait", 5),
        ("broll_esporte.mp4", "teenager playing sport outdoors",    "portrait", 5),
    ],
    # Video vertical da Dra sobre percepcao de padroes no cerebro autista.
    # Portrait porque o projeto e 9:16 — landscape entraria cortado.
    "eli-premiere": [
        ("broll_padroes.mp4",   "geometric pattern abstract loop",   "portrait", 5),
        ("broll_cerebro.mp4",   "brain scan neurons firing",         "portrait", 5),
        ("broll_pensando.mp4",  "woman thinking window pensive",     "portrait", 5),
        ("broll_conexoes.mp4",  "abstract network connections dots", "portrait", 5),
        ("broll_trabalho.mp4",  "woman working laptop focused",      "portrait", 5),
    ],
    # Gameplay de jogo da mentira. B-roll aqui e cutaway comico: entra na
    # piada que o proprio video ja faz (poligrafo, policia, atropelamento),
    # nao ilustracao seria. Landscape porque o projeto e 16:9.
    "gmod-mentira": [
        ("broll_poligrafo.mp4",   "lie detector polygraph test",      "landscape", 5),
        ("broll_policia.mp4",     "police car lights night street",   "landscape", 5),
        ("broll_atropelo.mp4",    "car driving fast road pov",        "landscape", 5),
        ("broll_detetive.mp4",    "detective magnifying glass clues", "landscape", 5),
        ("broll_traicao.mp4",     "handshake betrayal knife back",    "landscape", 5),
        ("broll_suspeita.mp4",    "suspicious man looking around",    "landscape", 5),
        ("broll_gato.mp4",        "cat looking at camera closeup",    "landscape", 5),
        ("broll_ambulancia.mp4",  "ambulance emergency siren street", "landscape", 5),
        ("broll_fumaca.mp4",      "smoke grenade colored fog",        "landscape", 5),
        ("broll_caos.mp4",        "crowd running panic chaos",        "landscape", 5),
        ("broll_mascara.mp4",     "masked people group mystery",      "landscape", 5),
        ("broll_relogio.mp4",     "clock ticking countdown closeup",  "landscape", 5),
    ],
    "abuso-mulheres-autistas": [
        # (filename, query, orientation, min_duration_sec)
        ("broll_woman_thinking.mp4",      "pensive woman portrait",         "landscape", 6),
        ("broll_girl_obey.mp4",           "quiet child listening",          "landscape", 6),
        ("broll_calendar_years.mp4",      "calendar pages turning time",    "landscape", 6),
        ("broll_no_pressure.mp4",         "uncomfortable woman boundary",   "landscape", 6),
        ("broll_money_control.mp4",       "wallet money close up",          "landscape", 6),
        ("broll_workplace_uncomfort.mp4", "office meeting professional",    "landscape", 6),
        ("broll_anxious_alone.mp4",       "anxious woman window alone",     "landscape", 8),
        ("broll_packing_leaving.mp4",     "woman packing suitcase",         "landscape", 8),
        ("broll_doctor_office.mp4",       "doctor consultation patient",    "landscape", 8),
        ("broll_empowered_woman.mp4",     "woman walking sunset",           "landscape", 8),
    ],
    "melhores-tecnicas-terapias": [
        ("broll_therapy_session.mp4",    "therapy session psychologist patient", "landscape", 6),
        ("broll_child_aba.mp4",          "child behavioral therapy learning",    "landscape", 6),
        ("broll_brain_cognitive.mp4",    "brain cognitive thinking abstract",    "landscape", 6),
        ("broll_anxiety_stress.mp4",     "anxious stressed person alone",        "landscape", 6),
        ("broll_noise_headphones.mp4",   "noise cancelling headphones person",   "landscape", 5),
        ("broll_sensory_texture.mp4",    "hands touching fabric texture",        "landscape", 5),
        ("broll_shower_hygiene.mp4",     "shower water bathroom clean",          "landscape", 5),
        ("broll_cleaning_home.mp4",      "person cleaning house chores",         "landscape", 5),
        ("broll_social_group.mp4",       "group people talking social",          "landscape", 6),
        ("broll_teen_friends.mp4",       "teenagers friends conversation",       "landscape", 6),
        ("broll_speech_therapy.mp4",     "speech therapy mouth talking",         "landscape", 5),
        ("broll_organization_study.mp4", "organized desk planner study",         "landscape", 5),
        ("broll_balance_motor.mp4",      "physical therapy balance exercise",    "landscape", 6),
        ("broll_coordination_body.mp4",  "body coordination movement exercise",  "landscape", 6),
        ("broll_doctor_explain.mp4",     "doctor explaining patient consult",    "landscape", 6),
        ("broll_adult_autism.mp4",       "adult thoughtful portrait calm",       "landscape", 6),
    ],
    "seletividade-alimentar": [
        # Brolls horizontais 16:9 — Dra Eli falando sobre seletividade alimentar TEA
        ("broll_picky_eater_kid.mp4",      "child picky eater food refuse",     "landscape", 6),
        ("broll_brain_neurons.mp4",        "brain neurons synapses close up",   "landscape", 6),
        ("broll_food_serving.mp4",         "food being served plate steam",     "landscape", 5),
        ("broll_family_dinner.mp4",        "family dinner table together",      "landscape", 6),
        ("broll_sensory_overload.mp4",     "person sensory overload anxious",   "landscape", 6),
        ("broll_kid_refusing.mp4",         "child refusing food at table",      "landscape", 5),
        ("broll_blood_test.mp4",           "blood test laboratory tubes",       "landscape", 5),
        ("broll_supplements.mp4",          "vitamin supplements pills capsules","landscape", 5),
        ("broll_baby_food_intro.mp4",      "baby food introduction spoon",      "landscape", 6),
        ("broll_colorful_veggies.mp4",     "colorful vegetables green plate",   "landscape", 5),
        ("broll_family_support_meal.mp4",  "supportive family meal child",      "landscape", 6),
        ("broll_repetitive_food.mp4",      "same meal repeating boring",        "landscape", 5),
    ],
    "domingo-com-ritalina": [
        # Brolls VERTICAIS (portrait) pra Reels/Shorts 9:16
        ("broll_lonely_thinking.mp4",     "woman alone thinking window",     "portrait", 6),
        ("broll_empty_party.mp4",         "empty party balloons table",      "portrait", 5),
        ("broll_baby_shower.mp4",         "baby shower decoration alone",    "portrait", 5),
        ("broll_pregnant_belly.mp4",      "pregnant woman calm portrait",    "portrait", 6),
        ("broll_sad_face_hands.mp4",      "woman sad hands face",            "portrait", 6),
        ("broll_wall_shadow.mp4",         "wall shadow silhouette dark",     "portrait", 5),
        ("broll_anxious_night.mp4",       "anxious sleepless night woman",   "portrait", 6),
        ("broll_typing_laptop.mp4",       "hands typing laptop close",       "portrait", 5),
        ("broll_couple_celebrate.mp4",    "couple celebrating intimate",     "portrait", 6),
        ("broll_woman_hug_support.mp4",   "woman hug support emotional",     "portrait", 6),
        ("broll_confident_sunset.mp4",    "confident woman sunset light",    "portrait", 6),
    ],
    "mascaramento-autismo": [
        # Brolls VERTICAIS 9:16 (portrait) — masking/mascaramento mulheres autistas
        ("broll_brain_abstract.mp4",      "abstract brain neural network glowing",        "portrait", 5),
        ("broll_anxious_woman.mp4",        "anxious stressed woman portrait dark",         "portrait", 6),
        ("broll_woman_window_alone.mp4",   "lonely woman looking out window sad",          "portrait", 6),
        ("broll_woman_mirror.mp4",         "woman looking at herself in mirror",           "portrait", 6),
        ("broll_makeup_mask.mp4",          "woman applying makeup close up mirror",        "portrait", 5),
        ("broll_tired_exhausted.mp4",      "exhausted tired woman rubbing eyes",           "portrait", 6),
        ("broll_teen_girl_alone.mp4",      "teenage girl sitting alone thoughtful",        "portrait", 6),
        ("broll_crowd_overwhelm.mp4",      "crowded busy people blurred motion",           "portrait", 5),
        ("broll_women_support.mp4",        "women hugging supporting each other",          "portrait", 6),
        ("broll_woman_relief.mp4",         "woman calm relief breathing peaceful",         "portrait", 6),
        # Segunda leva — blocos sem apoio (neurociência, dopamina, relacionamentos, diagnóstico)
        ("broll_neurons_abstract.mp4",     "abstract particles network connections dark",  "portrait", 6),
        ("broll_woman_thinking_deep.mp4",  "woman thinking deep thoughtful portrait",      "portrait", 6),
        ("broll_couple_distant.mp4",       "couple sitting apart distant relationship",    "portrait", 6),
        ("broll_woman_smiling_mask.mp4",   "woman forced smile portrait close up",         "portrait", 6),
        ("broll_doctor_consult.mp4",       "doctor talking to patient consultation",       "portrait", 6),
        ("broll_woman_writing.mp4",        "woman writing notebook journaling",            "portrait", 6),
    ],
    "linguagens-de-amor": [
        # Brolls LANDSCAPE 16:9 — 5 linguagens do amor versao autista
        ("broll_book_open_pages.mp4",       "open book pages flipping romantic close up",  "landscape", 10),
        ("broll_couple_quiet_together.mp4", "couple sitting together quietly side by side", "landscape", 6),
        ("broll_gift_wrapped.mp4",          "hands wrapping gift box ribbon",              "landscape", 5),
        ("broll_old_letter_keepsake.mp4",   "old handwritten letter close up",             "landscape", 5),
        ("broll_couple_talking.mp4",        "couple talking smiling enthusiastic",         "landscape", 6),
        ("broll_organizing_home.mp4",       "person tidying organizing home cleaning",     "landscape", 6),
        ("broll_manicure_hands.mp4",        "manicure painting nails close up",            "landscape", 5),
        ("broll_hand_on_shoulder.mp4",      "hand on shoulder couple supportive",          "landscape", 5),
        ("broll_tight_hug.mp4",             "couple tight hug warm embrace",               "landscape", 6),
        ("broll_penguin_pair.mp4",          "penguin pair couple wildlife",                "landscape", 5),
        ("broll_couple_laughing.mp4",       "couple laughing happy genuine moment",        "landscape", 6),
    ],
    "meltdown-shutdown-autismo": [
        # Brolls LANDSCAPE 16:9 — meltdown e shutdown (crises autistas)
        ("broll_overwhelmed_head.mp4",     "overwhelmed person hands covering ears stress", "landscape", 6),
        ("broll_alone_dark_room.mp4",      "person sitting alone dark room sad",            "landscape", 6),
        ("broll_brain_synapse.mp4",        "abstract neural network synapse glowing",       "landscape", 5),
        ("broll_busy_crowd_blur.mp4",      "busy crowd blurred motion people city",         "landscape", 6),
        ("broll_slow_motion_walk.mp4",     "lonely person walking slow motion street",      "landscape", 6),
        ("broll_anxious_breathing.mp4",    "anxious woman stressed breathing",              "landscape", 6),
        ("broll_noise_headphones.mp4",     "person wearing headphones eyes closed calm",    "landscape", 5),
        ("broll_pause_coffee.mp4",         "calm person coffee break window quiet",         "landscape", 6),
        ("broll_resting_couch.mp4",        "tired person resting lying on couch",           "landscape", 6),
        ("broll_support_shoulder.mp4",     "supportive hand on shoulder comfort",           "landscape", 6),
    ],
}


def get_pexels_key_local():
    """A chave que o usuario digitou em Configuracoes › Chaves de API.

    E a unica fonte automatica: a chave e do Klipe, e o painel de
    Configuracoes e onde ela se ve e se troca. Depender de outro servico estar
    de pe para saber a propria chave e dependencia que so pode falhar.
    """
    try:
        p = Path(__file__).parent / "klipe_settings.json"
        return (json.loads(p.read_text(encoding="utf-8")).get("pexels_key") or "").strip()
    except Exception:
        return ""


# A busca no Zero-One (http://localhost:8003/api/config/PEXELS_API_KEY) saiu
# daqui. A chave foi importada para as Configuracoes do Klipe e mora em
# klipe_settings.json — o Klipe nao depende mais de outro servico estar de pe
# para saber a propria chave. Medido com o 8003 fora do ar: 4,1 segundos de
# espera para devolver vazio, em toda chamada.
#
# Se um dia a chave precisar vir de fora, sobrou `--key` e a variavel de
# ambiente PEXELS_API_KEY — as duas continuam valendo.


def search_pexels(query, api_key, orientation="landscape", per_page=5):
    """Search Pexels videos. Returns list of video info dicts."""
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "per_page": per_page,
        "orientation": orientation,
        "size": "medium",  # medium = HD (720p+); large = 4K
    }
    r = requests.get(PEXELS_API, headers=headers, params=params, timeout=30)
    if r.status_code == 401:
        print("  FAIL: API key invalida (401)")
        return None
    if r.status_code != 200:
        print(f"  FAIL: HTTP {r.status_code}: {r.text[:200]}")
        return None
    return r.json().get("videos", [])


def pick_best_video(videos, min_dur):
    """Pick first video with duration >= min_dur and 1080p HD file."""
    for v in videos:
        if v.get("duration", 0) < min_dur:
            continue
        files = v.get("video_files", [])

        # BUG ATE 2026-08-07: ordenava por `height == 1080`. Isso so vale em
        # DEITADO — num video em pe, o arquivo de 1080 de largura tem altura
        # 1920, a regra nunca casava, tudo caia no ultimo balde e sobrava o
        # menor arquivo da lista. Resultado medido: um b-roll de 240x426 num
        # projeto 1080x1920, borrado, e ninguem avisava.
        #
        # O que importa e o LADO MENOR: num 9:16 e a largura, num 16:9 e a
        # altura. Perto de 1080 ganha; abaixo disso perde feio, porque
        # ampliar b-roll e o unico erro que nao tem conserto depois.
        def nota(f):
            lado = min(f.get("width") or 0, f.get("height") or 0)
            if lado <= 0:
                return (3, 0)
            if lado < 1080:
                return (2, -lado)          # menor que o alvo: quanto maior, melhor
            return (0 if lado == 1080 else 1, lado)   # 1080 exato, senao o menor acima

        files.sort(key=nota)
        for f in files:
            if f.get("file_type", "").startswith("video/mp4") and f.get("link"):
                return v, f
    return None, None


def download_file(url, dest):
    """Download file with progress."""
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    total = int(r.headers.get("content-length", 0))
    downloaded = 0
    chunk_size = 65536
    with open(dest, "wb") as fp:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fp.write(chunk)
                downloaded += len(chunk)
    return downloaded


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", help="Project slug (ex: abuso-mulheres-autistas)")
    ap.add_argument("--key", default="", help="Pexels API key (default: Configuracoes do Klipe, ou env PEXELS_API_KEY)")
    ap.add_argument("--force", action="store_true", help="Re-download mesmo se ja existir")
    args = ap.parse_args()

    # Resolve key: arg > Configuracoes do Klipe > env
    api_key = (args.key or get_pexels_key_local()
               or os.environ.get("PEXELS_API_KEY", ""))
    if not api_key:
        print("FAIL: PEXELS_API_KEY nao encontrado.")
        print("  Tentei: --key, Configuracoes do Klipe, env PEXELS_API_KEY")
        print("  Cole a chave em: Klipe > Configuracoes > Chaves de API")
        print("  Get free: https://www.pexels.com/api/")
        sys.exit(1)
    # A ordem aqui espelha a resolucao acima; sem isso a mensagem mente sobre
    # qual chave esta em uso e o proximo a debugar perde uma hora.
    _fonte = "arg" if args.key else ("Configuracoes" if get_pexels_key_local() else "env")
    print(f"[Pexels] key fonte: {_fonte}")
    args.key = api_key

    if args.project not in BROLLS_CONFIG:
        print(f"FAIL: projeto '{args.project}' nao tem brolls configurados.")
        print(f"  Configurados: {list(BROLLS_CONFIG.keys())}")
        sys.exit(1)

    project_dir = PROJECTS_DIR / args.project / "brolls"
    project_dir.mkdir(parents=True, exist_ok=True)

    brolls = BROLLS_CONFIG[args.project]
    print(f"[Pexels] Baixando {len(brolls)} brolls pra {args.project}")
    print()

    success = 0
    skip = 0
    fail = 0
    t0 = time.time()

    for i, (fname, query, orientation, min_dur) in enumerate(brolls, 1):
        dest = project_dir / fname
        if dest.exists() and not args.force:
            print(f"[{i}/{len(brolls)}] {fname} JA EXISTE, pulando")
            skip += 1
            continue

        print(f"[{i}/{len(brolls)}] '{query}' -> {fname}")
        videos = search_pexels(query, args.key, orientation=orientation)
        if not videos:
            print(f"  FAIL: sem resultados pra '{query}'")
            fail += 1
            continue

        v, file_info = pick_best_video(videos, min_dur)
        if not v:
            print(f"  FAIL: nenhum video tem duracao >= {min_dur}s")
            fail += 1
            continue

        url = file_info["link"]
        size_pred = file_info.get("file_type")
        h = file_info.get("height")
        print(f"  Baixando ({h}p) por {v.get('user',{}).get('name','?')}...")

        try:
            t1 = time.time()
            size = download_file(url, dest)
            elapsed = time.time() - t1
            print(f"  OK {size//1024//1024} MB em {elapsed:.1f}s | duration={v['duration']}s | {v.get('url','')}")
            success += 1
            # Pequeno delay pra evitar rate limit
            time.sleep(0.5)
        except Exception as e:
            print(f"  FAIL download: {e}")
            if dest.exists():
                dest.unlink()
            fail += 1

    total = time.time() - t0
    print()
    print(f"[Pexels] OK: {success} | JA TINHA: {skip} | FAIL: {fail}")
    print(f"[Pexels] Total: {total:.1f}s")
    print(f"[Pexels] Pasta: {project_dir}")


if __name__ == "__main__":
    main()
