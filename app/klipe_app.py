"""
klipe_app.py — o Klipe como aplicativo de desktop.

Mesmo produto, duas portas de entrada:

  - **App**  : este arquivo (ou o .exe gerado por `build_exe.py`). Janela
               nativa, icone proprio, sem console preto, sem barra de endereco.
  - **Web**  : `Klipe Web.bat` (ou o `Iniciar Klipe.bat` de sempre). Abre no
               navegador e continua acessivel do celular/outro PC da rede.

Os dois falam com o MESMO servidor na mesma porta. Nao existe versao "app" e
versao "web" do Klipe — existe o Klipe, e duas formas de olhar pra ele. Se o
servidor ja estiver de pe (porque voce abriu pelo .bat antes), o app se PLUGA
nele em vez de subir outro; e nesse caso nao derruba nada ao fechar, porque a
janela nao e dona do servidor.

A janela usa o WebView2 que ja vem no Windows — nao empacota navegador nenhum,
por isso o exe fica em ~15 MB em vez de 200.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import webview

PORTA = int(os.environ.get("PORT", "3002"))
HOST = "127.0.0.1"
BASE_CFG = Path(os.environ.get("APPDATA", Path.home())) / "Klipe"
CONFIG = BASE_CFG / "app.json"
LOG = BASE_CFG / "app.log"
ESPERA_SERVIDOR = 40           # segundos ate desistir de esperar o server subir


def log(msg: str):
    """
    App `--windowed` nao tem console: sem isto, qualquer falha some sem deixar
    rastro e a janela simplesmente nao abre. O log e o unico jeito de saber
    por que.
    """
    linha = f"{datetime.now():%H:%M:%S}  {msg}"
    try:
        BASE_CFG.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception:
        pass
    if not getattr(sys, "frozen", False):
        print(linha)


# ── onde mora o projeto ───────────────────────────────────────────────────
def raiz_projeto() -> Path | None:
    """
    Acha a pasta do Klipe (a que tem `editor-server.js`).

    Ordem: variavel de ambiente -> ao lado do exe/script -> pasta pai ->
    o que ficou salvo na ultima vez. Se nada servir, devolve None e quem chamou
    pede a pasta pro usuario.
    """
    candidatas = []
    if os.environ.get("KLIPE_DIR"):
        candidatas.append(Path(os.environ["KLIPE_DIR"]))

    base = Path(sys.executable).parent if getattr(sys, "frozen", False) \
        else Path(__file__).resolve().parent
    candidatas += [base, base.parent, base.parent.parent]

    if CONFIG.exists():
        try:
            salvo = json.loads(CONFIG.read_text(encoding="utf-8")).get("raiz")
            if salvo:
                candidatas.append(Path(salvo))
        except Exception:
            pass

    for c in candidatas:
        try:
            if (c / "editor-server.js").exists():
                return c.resolve()
        except OSError:
            continue
    return None


def salvar_raiz(raiz: Path):
    try:
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps({"raiz": str(raiz)}), encoding="utf-8")
    except Exception:
        pass


# ── servidor ──────────────────────────────────────────────────────────────
def porta_responde(porta: int = PORTA, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((HOST, porta), timeout=timeout):
            return True
    except OSError:
        return False


def achar_node() -> str | None:
    """
    Onde esta o `node`.

    `shutil.which` resolve pelo PATH, mas o PATH de um app aberto pelo Explorer
    nao e o mesmo do terminal — o instalador do Node poe a pasta no PATH do
    usuario, e isso nem sempre chega num processo iniciado por atalho. Por isso
    tem uma lista de lugares conhecidos como reserva.
    """
    achado = shutil.which("node")
    if achado:
        return achado
    for p in (r"C:\Program Files\nodejs\node.exe",
              r"C:\Program Files (x86)\nodejs\node.exe",
              str(Path.home() / "AppData/Roaming/npm/node.exe"),
              str(Path.home() / "AppData/Local/Programs/nodejs/node.exe")):
        if Path(p).exists():
            return p
    return None


def subir_servidor(raiz: Path) -> subprocess.Popen | None:
    """Sobe o `editor-server.js` sem janela de console."""
    node = achar_node()
    if not node:
        log("ERRO: nao achei o node.exe (nem no PATH nem nos lugares padrao)")
        return None
    log(f"node: {node}")
    flags = 0
    si = None
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    # a saida do servidor vai pro log: se ele morrer na largada (porta ocupada,
    # modulo faltando), da pra ler o motivo em vez de adivinhar
    saida = open(BASE_CFG / "server.log", "a", encoding="utf-8", errors="replace")
    return subprocess.Popen(
        [node, "editor-server.js"], cwd=str(raiz),
        stdout=saida, stderr=subprocess.STDOUT,
        creationflags=flags, startupinfo=si)


def esperar_servidor(proc: subprocess.Popen | None, limite=ESPERA_SERVIDOR) -> bool:
    t0 = time.time()
    while time.time() - t0 < limite:
        if porta_responde():
            return True
        if proc is not None and proc.poll() is not None:
            return False          # o node morreu antes de abrir a porta
        time.sleep(0.25)
    return False


def derrubar(proc: subprocess.Popen | None):
    """
    Mata o servidor E os filhos dele.

    `proc.terminate()` sozinho nao serve: o `editor-server.js` spawna ffmpeg,
    Chrome headless e Python durante um render, e esses ficariam orfaos
    comendo CPU depois que a janela fechasse.
    """
    if proc is None or proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                       capture_output=True)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        pass


def render_rodando() -> bool:
    """Pergunta ao servidor se tem render em andamento."""
    try:
        with urllib.request.urlopen(
                f"http://{HOST}:{PORTA}/api/render-forge/status", timeout=2) as r:
            return json.loads(r.read()).get("status") == "running"
    except Exception:
        return False


# ── janela ────────────────────────────────────────────────────────────────
def checar_backend() -> str | None:
    """
    Confere se a ponte pro WebView2 carrega, e devolve o erro DE VERDADE.

    O pywebview engole qualquer falha aqui e responde sempre "You must have
    pythonnet installed" — mesmo quando o pythonnet esta instalado e o problema
    e outro (DLL faltando no pacote, .NET ausente). Sem isto, o exe morre com
    uma mensagem que aponta pro lugar errado.
    """
    try:
        import clr  # noqa: F401
        return None
    except Exception:
        return traceback.format_exc()


def main() -> int:
    log(f"--- abrindo Klipe (frozen={getattr(sys, 'frozen', False)}) ---")
    log(f"executavel: {sys.executable}")
    erro_backend = checar_backend()
    if erro_backend:
        log("ERRO REAL ao carregar o clr/pythonnet:\n" + erro_backend)
    raiz = raiz_projeto()
    log(f"raiz do projeto: {raiz}")
    if raiz is None:
        # sem a pasta o app nao tem o que abrir — pede uma vez e guarda
        escolha = webview.create_window("Klipe", html="<p>escolhendo pasta…</p>",
                                        hidden=True)
        pasta = None

        def _pedir():
            nonlocal pasta
            r = escolha.create_file_dialog(webview.FOLDER_DIALOG)
            pasta = Path(r[0]) if r else None
            escolha.destroy()

        webview.start(_pedir, escolha)
        if not pasta or not (pasta / "editor-server.js").exists():
            return 1
        raiz = pasta.resolve()
        salvar_raiz(raiz)
    else:
        salvar_raiz(raiz)

    # Se o servidor ja estiver de pe (voce abriu pelo .bat), a janela so se
    # pluga nele — e ao fechar NAO derruba, porque nao foi ela que subiu.
    proc = None
    dono = False
    if porta_responde():
        log(f"porta {PORTA} ja responde — plugando no servidor existente")
    else:
        log(f"porta {PORTA} livre — subindo o servidor")
        proc = subir_servidor(raiz)
        dono = True
        if not esperar_servidor(proc):
            log("ERRO: o servidor nao respondeu a tempo (ver server.log)")
            derrubar(proc)
            aviso = webview.create_window(
                "Klipe", html=(
                    "<body style='font:14px system-ui;padding:28px;color:#eceff1;"
                    "background:#12151b'><h2 style='color:#E8940A'>Não consegui subir o servidor</h2>"
                    f"<p>Tentei rodar <code>node editor-server.js</code> em<br><code>{raiz}</code></p>"
                    "<p>Confira se o Node está instalado e se a porta "
                    f"<b>{PORTA}</b> está livre.</p></body>"),
                width=620, height=320)
            webview.start()
            return 1

    janela = webview.create_window(
        "Klipe", f"http://{HOST}:{PORTA}/",
        width=1500, height=950, min_size=(1024, 700),
        background_color="#12151b", text_select=True)

    def ao_fechar():
        # Fechar a janela no meio de um render mataria o render junto. Se a
        # janela e dona do servidor, pergunta antes.
        if dono and render_rodando():
            return janela.create_confirmation_dialog(
                "Render em andamento",
                "Tem um render rodando. Fechar agora cancela ele.\n\nFechar mesmo assim?")
        return True

    janela.events.closing += ao_fechar
    try:
        log("abrindo a janela")
        # private_mode=False guarda cookies: sem isso o login do Klipe seria
        # pedido de novo a cada abertura.
        webview.start(private_mode=False, storage_path=str(BASE_CFG / "webview"))
        log("janela fechada")
    finally:
        if dono:
            derrubar(proc)
            log("servidor derrubado")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        # sem console, um traceback nao aparece em lugar nenhum
        log("FALHA:\n" + traceback.format_exc())
        raise
