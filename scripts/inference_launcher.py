#!/usr/bin/env python3
"""Janela local para controlar processos de inferencia por PID (macOS/Linux)."""
from __future__ import annotations

import argparse
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DETECTORS = {'fall': 'Quedas', 'confrontation': 'Confrontos'}


@dataclass
class Instance:
    process: subprocess.Popen | None = None
    camera_id: str = ''
    stopping: bool = False
    last_pid: int | None = None
    last_exit: int | None = None


class InferenceProcesses:
    """Owns only processes created here; never searches/kills unrelated Python PIDs."""

    def __init__(self, repo=REPO_ROOT, python=None, emit=print, grace_seconds=20, force_seconds=3):
        self.repo = Path(repo)
        candidate = self.repo / '.venv' / 'bin' / 'python'
        self.python = str(python or (candidate if candidate.exists() else sys.executable))
        self.emit = emit
        self.grace_seconds = grace_seconds
        self.force_seconds = force_seconds
        self.instances = {kind: Instance() for kind in DETECTORS}
        self.lock = threading.RLock()

    def command(self, detector, camera_id, preview):
        return [self.python, '-u', '-m', 'scripts.run_fall_monitor_jobs',
                '--camera-id', camera_id, '--detector', detector,
                '--show-preview' if preview else '--no-preview',
                '--log-file', str(self.repo / 'var' / 'logs' / f'gui_{detector}.log')]

    def start(self, detector, camera_id, preview=True):
        camera_id = str(uuid.UUID(camera_id.strip()))
        with self.lock:
            state = self.instances[detector]
            if state.stopping:
                raise RuntimeError('Aguarde o encerramento do processo anterior.')
            if state.process is not None:
                if state.process.poll() is None:
                    if state.camera_id != camera_id:
                        raise RuntimeError(f'{DETECTORS[detector]} ja esta ativo em outra camera. Use Reiniciar.')
                    self.emit(f'{DETECTORS[detector]} ja esta ativo: PID {state.process.pid}.')
                    return state.process.pid
                # Never signal an old PID that may have been reused after exit.
                state.process = None
            env = os.environ.copy()
            env['REDIS_URL'] = ''
            env['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
            env['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp|allowed_media_types;video'
            logs = self.repo / 'var' / 'logs'
            logs.mkdir(parents=True, exist_ok=True)
            with (logs / f'gui_{detector}_console.log').open('ab', buffering=0) as output:
                process = subprocess.Popen(self.command(detector, camera_id, preview), cwd=self.repo,
                                           env=env, stdin=subprocess.DEVNULL, stdout=output,
                                           stderr=subprocess.STDOUT, start_new_session=True)
            state.process = process
            state.camera_id = camera_id
            state.last_pid = process.pid
            state.last_exit = None
            self.emit(f'{DETECTORS[detector]} iniciado: PID {process.pid} | camera {camera_id}.')
            return process.pid

    def _clean_group(self, pid):
        """Also close a leftover preview child in the group created by start_new_session."""
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except PermissionError:
            if not self._group_has_live_members(pid):
                return
            raise
        deadline = time.monotonic() + self.force_seconds
        while time.monotonic() < deadline:
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                return
            except PermissionError:
                # macOS can report EPERM for a group containing only orphaned
                # zombies. Verify process states instead of treating it as live.
                if not self._group_has_live_members(pid):
                    return
                raise
            time.sleep(.05)
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            if self._group_has_live_members(pid):
                raise

    @staticmethod
    def _group_has_live_members(pid):
        result = subprocess.run(['ps', '-axo', 'pgid=,stat='], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) >= 2 and fields[0] == str(pid) and not fields[1].startswith('Z'):
                return True
        return False

    def stop(self, detector):
        with self.lock:
            state = self.instances[detector]
            if state.process is None:
                self.emit(f'{DETECTORS[detector]} ja esta parado.')
                return
            if state.stopping:
                raise RuntimeError('Este processo ja esta sendo encerrado.')
            state.stopping = True
            process = state.process
            pid = process.pid
        try:
            was_running = process.poll() is None
            if was_running:
                self.emit(f'Encerrando {DETECTORS[detector]} pelo PID {pid} (SIGTERM)...')
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=self.grace_seconds)
                except subprocess.TimeoutExpired:
                    self.emit(f'PID {pid} nao encerrou no prazo; encerrando grupo do processo.')
                    self._clean_group(pid)
                    process.wait(timeout=5)
            # Parent can finish before its preview; clean the owned group too.
            if was_running:
                self._clean_group(pid)
            code = process.wait(timeout=5)
            with self.lock:
                state.last_exit = code
                state.process = None
            self.emit(f'{DETECTORS[detector]} encerrado: PID {pid}, saida {code}.')
        finally:
            with self.lock:
                state.stopping = False

    def restart(self, detector, camera_id, preview=True):
        # Validate before stopping a working instance.
        camera_id = str(uuid.UUID(camera_id.strip()))
        self.stop(detector)
        return self.start(detector, camera_id, preview)

    def snapshot(self):
        with self.lock:
            result = {}
            for kind, state in self.instances.items():
                code = state.process.poll() if state.process else state.last_exit
                running = state.process is not None and code is None
                result[kind] = {'running': running, 'stopping': state.stopping,
                                'pid': state.process.pid if state.process else None,
                                'last_pid': state.last_pid, 'exit': code}
            return result


class LauncherWindow:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk
        self.root, self.tk, self.ttk = root, tk, ttk
        self.events = queue.Queue()
        self.manager = InferenceProcesses(emit=lambda message: self.events.put(('log', message)))
        self.config_path = REPO_ROOT / 'var' / 'launcher' / 'settings.json'
        try:
            previous = json.loads(self.config_path.read_text())
        except (OSError, ValueError):
            previous = {}
        self.camera = tk.StringVar(value=previous.get('camera_id', '221eacf3-8e94-4cb2-926c-03349d99f4b8'))
        self.preview = tk.BooleanVar(value=previous.get('preview', True))
        self.busy = False
        self.closing = False
        self.close_requested = False
        self.exits_seen = set()
        self.buttons = []
        root.title('VARD · Inferências')
        root.geometry('780x570')
        root.minsize(680, 520)
        root.protocol('WM_DELETE_WINDOW', self.close)
        frame = ttk.Frame(root, padding=18)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Controle de inferências', font=('Helvetica', 19, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Parâmetros do .env são carregados a cada início ou reinício.').pack(anchor='w', pady=(5, 14))
        selection = ttk.Frame(frame)
        selection.pack(fill='x')
        ttk.Label(selection, text='Câmera / camera-id').pack(anchor='w')
        row = ttk.Frame(selection)
        row.pack(fill='x', pady=(5, 8))
        self.camera_box = ttk.Combobox(row, textvariable=self.camera)
        self.camera_box.pack(side='left', fill='x', expand=True)
        self.refresh_button = ttk.Button(row, text='Buscar câmeras', command=self.refresh_cameras)
        self.refresh_button.pack(side='left', padx=(8, 0))
        self.preview_box = ttk.Checkbutton(selection, text='Mostrar vídeo das inferências', variable=self.preview)
        self.preview_box.pack(anchor='w', pady=(0, 14))
        self.status_labels = {}
        for kind, title in DETECTORS.items():
            section = ttk.LabelFrame(frame, text=title, padding=10)
            section.pack(fill='x', pady=(0, 10))
            self.status_labels[kind] = ttk.Label(section, text='Parado', width=33)
            self.status_labels[kind].pack(side='left', fill='x', expand=True)
            for action, text in (('start', 'Iniciar'), ('stop', 'Parar'), ('restart', 'Reiniciar')):
                button = ttk.Button(section, text=text, width=10,
                                    command=lambda a=action, k=kind: self.action(a, [k]))
                button.pack(side='left', padx=(5, 0))
                self.buttons.append(button)
        together = ttk.Frame(frame)
        together.pack(fill='x', pady=(0, 12))
        for action, text in (('start', 'Iniciar as duas'), ('stop', 'Parar as duas'), ('restart', 'Reiniciar as duas')):
            button = ttk.Button(together, text=text, command=lambda a=action: self.action(a, list(DETECTORS)))
            button.pack(side='left', expand=True, fill='x', padx=3)
            self.buttons.append(button)
        self.activity = tk.StringVar(value='Pronto. Nenhuma inferência foi iniciada.')
        ttk.Label(frame, textvariable=self.activity).pack(anchor='w', pady=(0, 5))
        log_frame = ttk.Frame(frame)
        log_frame.pack(fill='both', expand=True)
        self.log = tk.Text(log_frame, height=8, wrap='word', state='disabled', font=('Menlo', 11))
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        ttk.Label(frame, text='Logs: var/logs/gui_fall.log e gui_confrontation.log. Fechar a janela encerra as instâncias abertas aqui.',
                  wraplength=730).pack(anchor='w', pady=(9, 0))
        self.root.after(150, self.tick)

    def camera_id(self):
        return str(uuid.UUID(self.camera.get().split(' | ')[-1].strip()))

    def set_busy(self, busy):
        self.busy = busy
        state = 'disabled' if busy else 'normal'
        for widget in self.buttons + [self.camera_box, self.preview_box]:
            widget.configure(state=state)

    def action(self, action, detectors):
        if self.busy or self.closing:
            return
        if action != 'stop':
            try:
                camera_id = self.camera_id()
            except ValueError:
                self.write('Informe um camera-id UUID válido ou selecione uma câmera em Buscar câmeras.')
                return
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(json.dumps({'camera_id': camera_id, 'preview': self.preview.get()}))
        else:
            camera_id = ''
        preview = self.preview.get()
        self.set_busy(True)
        self.activity.set('Executando ação… aguarde.')
        def work():
            try:
                for detector in detectors:
                    try:
                        method = getattr(self.manager, action)
                        method(detector) if action == 'stop' else method(detector, camera_id, preview)
                    except Exception as exc:
                        self.events.put(('log', f'Erro em {DETECTORS[detector]}: {exc}'))
            finally:
                self.events.put(('done', None))
        threading.Thread(target=work, daemon=True).start()

    def refresh_cameras(self):
        self.refresh_button.configure(state='disabled')
        def work():
            try:
                if str(REPO_ROOT) not in sys.path:
                    sys.path.insert(0, str(REPO_ROOT))
                from sqlalchemy import select
                from api.db import SessionLocal
                from api.models import Camera, Workspace
                with SessionLocal() as db:
                    cameras = db.execute(select(Camera.id, Camera.name, Workspace.name).join(
                        Workspace, Workspace.id == Camera.workspace_id).where(Camera.is_active.is_(True)).order_by(
                        Workspace.name, Camera.name)).all()
                self.events.put(('cameras', [f'{workspace} / {name} | {camera_id}' for camera_id, name, workspace in cameras]))
            except Exception as exc:
                self.events.put(('camera_error', f'Não foi possível consultar câmeras ({type(exc).__name__}). Você pode colar o ID manualmente.'))
        threading.Thread(target=work, daemon=True).start()

    def write(self, message):
        self.log.configure(state='normal')
        self.log.insert('end', f'[{time.strftime("%H:%M:%S")}] {message}\n')
        if int(self.log.index('end-1c').split('.')[0]) > 300:
            self.log.delete('1.0', '51.0')
        self.log.see('end')
        self.log.configure(state='disabled')

    def tick(self):
        try:
            while True:
                event, value = self.events.get_nowait()
                if event == 'log':
                    self.write(value)
                elif event == 'done':
                    self.set_busy(False)
                    self.activity.set('Pronto.')
                elif event == 'cameras':
                    self.camera_box.configure(values=value)
                    selected = self.camera.get().split(' | ')[-1]
                    match = next((label for label in value if label.endswith(selected)), None)
                    if match:
                        self.camera.set(match)
                    self.refresh_button.configure(state='normal')
                    self.write(f'{len(value)} câmera(s) ativa(s) encontrada(s).')
                elif event == 'camera_error':
                    self.refresh_button.configure(state='normal')
                    self.write(value)
                elif event == 'closed':
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        for kind, status in self.manager.snapshot().items():
            if status['stopping']:
                text = f'Encerrando PID {status["pid"]}…'
            elif status['running']:
                text = f'Processo ativo · PID {status["pid"]}'
            elif status['last_pid'] is not None:
                text = f'Parado · último PID {status["last_pid"]}'
                key = (kind, status['last_pid'])
                if status['pid'] and key not in self.exits_seen:
                    self.write(f'{DETECTORS[kind]} terminou (PID {status["pid"]}, saída {status["exit"]}). Consulte o log para diagnóstico.')
                    self.exits_seen.add(key)
            else:
                text = 'Parado'
            self.status_labels[kind].configure(text=text)
        if self.close_requested and not self.busy and not self.closing:
            self.close()
        self.root.after(200, self.tick)

    def close(self):
        self.close_requested = True
        if self.busy or self.closing:
            return
        self.closing = True
        self.set_busy(True)
        self.refresh_button.configure(state='disabled')
        self.activity.set('Encerrando processos por PID antes de fechar…')
        def finish():
            errors = []
            for kind in DETECTORS:
                try:
                    self.manager.stop(kind)
                except Exception as exc:
                    errors.append(f'Falha ao encerrar {DETECTORS[kind]}: {exc}')
            if errors:
                for error in errors:
                    self.events.put(('log', error))
                self.closing = False
                self.close_requested = False
                self.events.put(('done', None))
            else:
                self.events.put(('closed', None))
        threading.Thread(target=finish, daemon=True).start()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-test', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.name != 'posix':
        raise SystemExit('Este launcher usa sinais POSIX e foi preparado para macOS/Linux.')
    import fcntl
    import tkinter as tk
    from tkinter import messagebox
    lock_path = REPO_ROOT / 'var' / 'launcher' / 'window.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+') as lock:
        root = tk.Tk()
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            root.withdraw()
            messagebox.showinfo('VARD', 'O controle de inferências já está aberto.')
            root.destroy()
            return
        window = LauncherWindow(root)
        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, lambda *_: root.after(0, window.close))
        if args.smoke_test:
            root.after(1000, window.close)
        try:
            root.mainloop()
        finally:
            for kind in DETECTORS:
                window.manager.stop(kind)


if __name__ == '__main__':
    main()
