"""
build_exe.py — gera o `Klipe.exe`.

    python app/build_exe.py

Sai em `app/dist/Klipe.exe`. Copie (ou faca atalho) pra onde quiser: o app
descobre a pasta do projeto sozinho e, se nao achar, pergunta uma vez e guarda
a resposta em `%APPDATA%/Klipe/app.json`.

O exe NAO empacota navegador: usa o WebView2 que ja vem no Windows. Por isso
fica em ~15 MB em vez de ~200 MB. Tambem nao empacota o Klipe em si — ele abre
o `editor-server.js` que esta na pasta do projeto, entao editar o editor
continua valendo na hora, sem recompilar nada.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
NOME = "Klipe"


def dlls_do_ctypes() -> list[str]:
    """
    DLLs que o `_ctypes` do Anaconda precisa e que o PyInstaller nao acha.

    Num Python do Anaconda, o `_ctypes.pyd` esta em `DLLs/` mas depende da
    `ffi-*.dll`, que vive em `Library/bin/` — uma pasta que o PyInstaller nao
    varre. Sem elas, o exe abre e morre com
    `ImportError: DLL load failed while importing _ctypes`, e o pywebview
    disfarca isso como "You must have pythonnet installed" — mensagem que
    aponta pro lugar errado e faz perder tempo.
    """
    libbin = Path(sys.executable).parent / "Library" / "bin"
    achadas = []
    for nome in ("ffi.dll", "ffi-8.dll", "ffi-7.dll", "libffi-8.dll", "libffi-7.dll"):
        p = libbin / nome
        if p.exists():
            achadas.append(f"{p}{os.pathsep}.")
    return achadas


def main() -> int:
    icone = APP / "klipe.ico"
    if not icone.exists():
        print(f"faltou o icone: {icone}")
        return 1

    # Um Klipe.exe aberto trava o arquivo e o PyInstaller morre com "Acesso
    # negado" bem no fim do build — depois de varios minutos de trabalho.
    # Melhor fechar antes do que descobrir no fim.
    if os.name == "nt":
        r = subprocess.run(["taskkill", "/T", "/F", "/IM", f"{NOME}.exe"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            print(f"(fechei um {NOME}.exe que estava aberto)")
            time.sleep(1.5)

    extras = []
    for b in dlls_do_ctypes():
        extras += ["--add-binary", b]
    print(f"DLLs de ctypes incluidas: {len(extras)//2}")

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",
        "--windowed",                      # sem console preto atras
        f"--name={NOME}",
        f"--icon={icone}",
        f"--distpath={APP / 'dist'}",
        f"--workpath={APP / 'build'}",
        f"--specpath={APP}",
        # O pywebview carrega o backend por NOME em tempo de execucao, entao o
        # PyInstaller nao enxerga a dependencia sozinho — sem isso o exe abre e
        # morre com "You must have pythonnet installed".
        "--hidden-import=webview.platforms.edgechromium",
        "--collect-all=webview",
        # o pythonnet e a ponte pro WebView2 do Windows; ele tambem e carregado
        # dinamicamente e leva DLLs junto
        "--hidden-import=clr",
        "--collect-all=pythonnet",
        "--collect-all=clr_loader",
        *extras,
        str(APP / "klipe_app.py"),
    ]
    print(" ".join(args), "\n")
    r = subprocess.run(args, cwd=str(APP))
    if r.returncode != 0:
        return r.returncode

    exe = APP / "dist" / f"{NOME}.exe"
    if not exe.exists():
        print("o PyInstaller terminou mas nao gerou o exe")
        return 1
    print(f"\npronto: {exe}  ({exe.stat().st_size/1e6:.1f} MB)")

    # limpeza do intermediario (o build/ do PyInstaller nao serve pra nada
    # depois e ocupa algumas centenas de MB)
    shutil.rmtree(APP / "build", ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
