"""Owned local server lifecycle, independent of the desktop GUI."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import threading
import time
import urllib.request


def free_port(start=3002, exclude=()):
    for port in range(start, start + 80):
        if port in exclude:
            continue
        try:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    raise RuntimeError('Nenhuma porta local livre para iniciar o Klipe.')


def runtime_config(root):
    file = root / '.klipe-runtime.json'
    data = json.loads(file.read_text(encoding='utf-8-sig')) if file.exists() else {}
    for name in ('node', 'python', 'ffmpeg', 'ffprobe'):
        candidate = data.get(name)
        if candidate and Path(candidate).is_file():
            continue
        candidates = []
        if name == 'python':
            candidates += [root / '.venv/Scripts/python.exe']
            candidates += [Path.home() / base / 'envs/klipe/python.exe'
                           for base in ('anaconda3', 'miniconda3')]
        if name == 'node':
            candidates += [Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'nodejs/node.exe']
        if name in ('ffmpeg', 'ffprobe'):
            candidates += [Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Klipe/ffmpeg/bin' / (name + '.exe'),
                           Path('C:/ffmpeg/bin') / (name + '.exe')]
        found = next((str(p) for p in candidates if p.is_file()), None) or shutil.which(name)
        if not found:
            raise RuntimeError(f'{name} nao encontrado. Execute Instalar Klipe.bat nesta pasta.')
        data[name] = found
    return data


class DesktopServer:
    def __init__(self, root, logs):
        self.root = Path(root).resolve()
        self.logs = Path(logs)
        self.proc = None
        self.output = None
        self.token = secrets.token_urlsafe(32)
        self.port = free_port()
        self.motion_port = free_port(3011, (self.port,))
        self.url = f'http://127.0.0.1:{self.port}'
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def ready(self):
        if self.proc is None or self.proc.poll() is not None:
            return False
        try:
            req = urllib.request.Request(self.url + '/api/desktop/health', headers={'X-Klipe-Desktop': self.token})
            with self.http.open(req, timeout=1) as response:
                data = json.load(response)
                return data.get('app') == 'klipe' and data.get('pid') == self.proc.pid
        except (OSError, ValueError):
            return False

    def start(self, timeout=40):
        runtime = runtime_config(self.root)
        env = os.environ.copy()
        env.update(PORT=str(self.port), MOTIONCORE_PORT=str(self.motion_port),
                   PYTHON_EXE=runtime['python'], KLIPE_FFMPEG=runtime['ffmpeg'],
                   KLIPE_FFPROBE=runtime['ffprobe'], KLIPE_DESKTOP_TOKEN=self.token)
        env['PATH'] = os.pathsep.join([str(Path(runtime['node']).parent), str(Path(runtime['ffmpeg']).parent), env.get('PATH', '')])
        self.logs.mkdir(parents=True, exist_ok=True)
        self.output = (self.logs / f'desktop-server-{os.getpid()}.log').open('a', encoding='utf-8')
        try:
            self.proc = subprocess.Popen([runtime['node'], 'editor-server.js'], cwd=self.root, env=env,
                                         stdin=subprocess.DEVNULL, stdout=self.output, stderr=subprocess.STDOUT,
                                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                                         start_new_session=os.name != 'nt')
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self.ready():
                    return self.url
                if self.proc.poll() is not None:
                    break
                time.sleep(.2)
            raise RuntimeError(f'O servidor nao iniciou. Consulte os logs em {self.logs}')
        except Exception:
            self.stop()
            raise

    def render_running(self):
        try:
            with self.http.open(self.url + '/api/render-forge/status', timeout=2) as response:
                return json.load(response).get('status') == 'running'
        except (OSError, ValueError):
            return False

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/T', '/F', '/PID', str(self.proc.pid)],
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
            else:
                os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait(timeout=15)
        if self.output:
            self.output.close()
            self.output = None


class AsyncCloseGuard:
    """Release the UI close event before querying WebView or showing dialogs."""

    def __init__(self, check, destroy):
        self.check = check
        self.destroy = destroy
        self.allowed = False
        self.pending = False
        self.lock = threading.Lock()
        self.worker = None

    def request(self):
        with self.lock:
            if self.allowed:
                return True
            if not self.pending:
                self.pending = True
                self.worker = threading.Thread(target=self._check, daemon=True)
                self.worker.start()
        return False

    def _check(self):
        try:
            if self.check():
                with self.lock:
                    self.allowed = True
                self.destroy()
        finally:
            with self.lock:
                self.pending = False


def close_reasons(state, rendering=False):
    reasons = []
    if state.get('saving'):
        reasons.append('O projeto ainda esta sendo salvo.')
    if state.get('dirty'):
        reasons.append('Existem alteracoes nao salvas. Volte e use Save para guarda-las.')
    if rendering:
        reasons.append('O render em andamento sera cancelado.')
    return reasons
