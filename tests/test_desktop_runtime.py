import importlib.util
import io
import json
from pathlib import Path
import socket
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('desktop_runtime', ROOT / 'app/desktop_runtime.py')
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)


class DesktopTests(unittest.TestCase):
    def test_close_check_runs_off_the_ui_thread_and_retries_after_approval(self):
        entered, release = threading.Event(), threading.Event()
        origin = threading.get_ident()
        threads = []
        def check():
            threads.append(threading.get_ident())
            entered.set()
            release.wait(2)
            return True
        destroy = Mock()
        guard = desktop.AsyncCloseGuard(check, destroy)
        self.assertFalse(guard.request())
        self.assertTrue(entered.wait(1))
        self.assertFalse(guard.request())
        release.set()
        guard.worker.join(2)
        self.assertFalse(guard.worker.is_alive())
        self.assertNotEqual(threads, [origin])
        self.assertEqual(len(threads), 1)
        destroy.assert_called_once()
        self.assertTrue(guard.request())

    def test_cancelled_close_leaves_editor_open_and_allows_retry(self):
        check, destroy = Mock(return_value=False), Mock()
        guard = desktop.AsyncCloseGuard(check, destroy)
        self.assertFalse(guard.request())
        guard.worker.join(2)
        destroy.assert_not_called()
        self.assertFalse(guard.allowed)
        check.return_value = True
        self.assertFalse(guard.request())
        guard.worker.join(2)
        destroy.assert_called_once()

    def test_occupied_port_is_not_reused(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
            self.assertNotEqual(desktop.free_port(port), port)

    def test_close_warning_covers_unsaved_edits_and_render(self):
        self.assertEqual(len(desktop.close_reasons({'dirty': True}, True)), 2)
        self.assertTrue(desktop.close_reasons({'saving': True}))
        self.assertEqual(desktop.close_reasons({}, False), [])

    def test_health_requires_owned_pid_not_just_open_port(self):
        server = desktop.DesktopServer(ROOT, ROOT / 'logs')
        server.proc = Mock(pid=123)
        server.proc.poll.return_value = None
        server.http = Mock()
        server.http.open.return_value = io.StringIO(json.dumps({'app':'klipe','pid':999}))
        self.assertFalse(server.ready())
        server.http.open.return_value = io.StringIO(json.dumps({'app':'klipe','pid':123}))
        self.assertTrue(server.ready())
        request = server.http.open.call_args.args[0]
        self.assertEqual(request.get_header('X-klipe-desktop'), server.token)

    def test_unstarted_server_does_not_kill_anything(self):
        server = desktop.DesktopServer(ROOT, ROOT / 'logs')
        with patch.object(desktop.subprocess, 'run') as run:
            server.stop()
            run.assert_not_called()

    def test_build_never_kills_an_existing_editor_by_name(self):
        source = (ROOT / 'app/build_exe.py').read_text(encoding='utf-8')
        self.assertNotIn('"/IM"', source)


if __name__ == '__main__':
    unittest.main()
