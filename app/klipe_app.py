"""Klipe Desktop: native WebView2 window over an owned local Klipe server."""
from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
import traceback

from desktop_runtime import AsyncCloseGuard, DesktopServer, close_reasons

BASE = Path(os.environ.get('APPDATA', str(Path.home()))) / 'Klipe'


def root_path(explicit=None):
    base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    if explicit:
        candidates = [Path(explicit)]
    else:
        candidates = ([Path(os.environ['KLIPE_DIR'])] if os.environ.get('KLIPE_DIR') else [])
        candidates += [base, base.parent, base.parent.parent]
        try:
            candidates.append(Path(json.loads((BASE / 'app.json').read_text(encoding='utf-8'))['raiz']))
        except (OSError, ValueError, KeyError):
            pass
    for root in candidates:
        if (root / 'editor-server.js').is_file() and (root / 'editor.html').is_file():
            return root.resolve()
    raise RuntimeError('Pasta do Klipe nao encontrada. Mantenha o aplicativo na pasta instalada ou use --root CAMINHO.')


def message(text):
    if os.name == 'nt':
        ctypes.windll.user32.MessageBoxW(None, str(text), 'Klipe Desktop', 0x40)
    else:
        print(text)


def evaluate(window, expression):
    # Video streams can keep NavigationCompleted pending after the editor is
    # usable. Use the native WebView2 executor instead of waiting for onload.
    if os.name == 'nt':
        return window.native.browser.evaluate_js('JSON.stringify(' + expression + ')', True)
    return window.evaluate_js(expression)


class SingleInstance:
    def __init__(self, root):
        self.handle = None
        if os.name == 'nt':
            api = ctypes.windll.kernel32
            api.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            api.CreateMutexW.restype = ctypes.c_void_p
            name = hashlib.sha256(str(root).lower().encode()).hexdigest()[:24]
            self.handle = api.CreateMutexW(None, False, 'Local\\KlipeDesktop-' + name)
            if not self.handle:
                raise RuntimeError('Nao foi possivel criar a janela do Klipe.')
            if api.GetLastError() == 183:
                self.close()
                raise RuntimeError('O Klipe Desktop desta pasta ja esta aberto. Procure a janela na barra de tarefas.')

    def close(self):
        if self.handle:
            api = ctypes.windll.kernel32
            api.CloseHandle.argtypes = [ctypes.c_void_p]
            api.CloseHandle(self.handle)
            self.handle = None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root')
    parser.add_argument('--project', default='')
    parser.add_argument('--smoke-test', metavar='REPORT_JSON')
    parser.add_argument('--smoke-close-test', action='store_true')
    args = parser.parse_args()
    if args.project and not re.fullmatch(r'[a-zA-Z0-9_-]+', args.project):
        raise RuntimeError('Identificador de projeto invalido.')
    root = root_path(args.root)
    instance = SingleInstance(root)
    BASE.mkdir(parents=True, exist_ok=True)
    if not args.smoke_test:
        (BASE / 'app.json').write_text(json.dumps({'raiz': str(root)}), encoding='utf-8')
    server = DesktopServer(root, BASE / 'logs')
    try:
        url = server.start()
        import webview
        webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = True
        webview.settings['ALLOW_DOWNLOADS'] = True
        window = webview.create_window('Klipe Desktop', url + ('/p/' + args.project if args.project else '/'),
                                       width=1440, height=900, min_size=(960, 640),
                                       background_color='#111318', text_select=True,
                                       hidden=bool(args.smoke_test and not args.project))
        testing = threading.Event()
        report = {}

        def confirm_close():
            try:
                state = evaluate(window, """(() => {
                  if (typeof NLE === 'undefined' || !NLE.sm || !NLE.liveSync) return {};
                  return {saving:!!NLE.liveSync.saving,
                    dirty:!!NLE.liveSync.savedFingerprint && NLE.liveSync.fingerprint() !== NLE.liveSync.savedFingerprint};
                })()""") or {}
                if state.get('saving'):
                    window.create_confirmation_dialog('Salvando projeto', 'Aguarde o salvamento terminar antes de fechar.')
                    return False
                reasons = close_reasons(state, server.render_running())
            except Exception:
                reasons = ['Nao foi possivel conferir se existem alteracoes nao salvas.']
            return not reasons or window.create_confirmation_dialog('Fechar Klipe?', '\n\n'.join(reasons) + '\n\nFechar mesmo assim?')

        close_guard = AsyncCloseGuard(confirm_close, window.destroy)
        window.events.closing += lambda: True if testing.is_set() else close_guard.request()

        def smoke():
            if not args.smoke_test:
                return
            try:
                if not window.events.shown.wait(30):
                    raise RuntimeError('A janela nao abriu em 30 segundos.')
                prepared = False
                for _ in range(300):
                    time.sleep(.2)
                    report.update(evaluate(window, """({title:document.title, url:location.href,
                      ready:document.readyState, body:document.body.innerText.length,
                      editor:typeof NLE !== 'undefined' && !!NLE.sm,
                      player:typeof NLE !== 'undefined' && !!NLE.preview?.p,
                      width:innerWidth, height:innerHeight})""") or {})
                    if report.get('ready') in ('interactive', 'complete') and report.get('body', 0) > 30:
                        if not args.project:
                            report['ok'] = True
                            break
                        if report.get('editor'):
                            if not prepared:
                                time.sleep(2)
                                prepared = bool(evaluate(window, """(() => {
                                  const p=NLE.preview?.p; if(!p?.video) return false;
                                  const t=Math.min(2,Math.max(0,NLE.sm.getState().videoDuration-.1));
                                  NLE.sm.dispatch('SET_PLAYHEAD',t); p.seek(t); return true;
                                })()"""))
                                continue
                            preview = evaluate(window, """(() => {
                              const p = NLE.preview?.p;
                              if (!p?.gl || !p.video || p.video.readyState < 2) return {visible:0,player:!!p,gl:!!p?.gl,video:!!p?.video,state:p?.video?.readyState,src:p?.video?.currentSrc};
                              p.desenhar();
                              const brolls=(p.cfg.brolls||[]).filter(b=>p.t>=b.startSec&&p.t<b.endSec);
                              const titles=(p.cfg.titles||[]).filter(t=>p.t>=t.startSec&&p.t<t.endSec);
                              if (brolls.some(b=>{const v=p._brolls.get(b.id||b.src);return !v||v.readyState<2||v.seeking||v._klipeWarming;}) ||
                                  titles.some(t=>!p._quadrosTitulos?.get(t.id??t.startSec)?.bitmap && !p._pedirTitulo(t).pronto)) return {visible:0,waiting:'layers'};
                              const gl=p.gl, w=p.canvas.width, h=p.canvas.height;
                              const pixels=new Uint8Array(w*h*4); gl.readPixels(0,0,w,h,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
                              let visible=0; for(let i=0;i<pixels.length;i+=64) if(pixels[i]+pixels[i+1]+pixels[i+2]>35) visible++;
                              return {visible,width:w,height:h,time:p.t,brolls:brolls.length,titles:titles.length,png:visible>0?p.canvas.toDataURL('image/png'):null};
                            })()""")
                            report['preview'] = preview
                            if preview and preview.get('visible', 0) > 0:
                                Path(args.smoke_test).with_suffix('.png').write_bytes(base64.b64decode(preview.pop('png').split(',', 1)[1]))
                                report.update(ok=True, preview=preview)
                                break
                report.setdefault('ok', False)
                report['serverPid'] = server.proc.pid
            except Exception as exc:
                report.update(ok=False, error=str(exc))
            finally:
                if not args.smoke_close_test:
                    testing.set()
                window.destroy()

        webview.start(smoke, gui='edgechromium' if os.name == 'nt' else None,
                      icon=str(Path(__file__).resolve().parent / 'klipe.ico'),
                      private_mode=False, storage_path=str(BASE / 'webview-desktop'))
        if args.smoke_test:
            server.stop()
            report['serverStopped'] = server.proc.poll() is not None
            report['guardedClose'] = close_guard.allowed
            Path(args.smoke_test).write_text(json.dumps(report, indent=2), encoding='utf-8')
            return 0 if report.get('ok') and report['serverStopped'] else 1
        return 0
    finally:
        server.stop()
        instance.close()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        BASE.mkdir(parents=True, exist_ok=True)
        with (BASE / 'app.log').open('a', encoding='utf-8') as output:
            output.write(traceback.format_exc() + '\n')
        if '--smoke-test' not in sys.argv:
            message(f'{exc}\n\nDetalhes em {BASE / "app.log"}')
        raise SystemExit(1)
