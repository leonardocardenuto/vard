import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.inference_launcher import InferenceProcesses

CAMERA = '221eacf3-8e94-4cb2-926c-03349d99f4b8'


@unittest.skipUnless(os.name == 'posix', 'Launcher usa sinais POSIX')
class InferenceLauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.messages = []
        self.manager = InferenceProcesses(repo=self.tmp.name, python=sys.executable,
                                          emit=self.messages.append, grace_seconds=.2, force_seconds=.1)
        self.manager.command = lambda *args: [sys.executable, '-u', '-c', 'import time; time.sleep(60)']

    def tearDown(self):
        for kind in self.manager.instances:
            self.manager.stop(kind)
        self.tmp.cleanup()

    def test_start_uses_real_pid_and_stop_waits_for_it(self):
        pid = self.manager.start('fall', CAMERA)
        process = self.manager.instances['fall'].process
        self.assertEqual(pid, process.pid)
        self.assertTrue(self.manager.snapshot()['fall']['running'])
        self.manager.stop('fall')
        self.assertIsNotNone(process.poll())
        self.assertFalse(self.manager.snapshot()['fall']['running'])
        self.assertTrue(any(f'PID {pid} (SIGTERM)' in message for message in self.messages))

    def test_two_detectors_are_independent_and_start_is_idempotent(self):
        fall_pid = self.manager.start('fall', CAMERA)
        other_pid = self.manager.start('confrontation', CAMERA)
        self.assertNotEqual(fall_pid, other_pid)
        self.assertEqual(self.manager.start('fall', CAMERA), fall_pid)
        self.manager.stop('fall')
        self.assertTrue(self.manager.snapshot()['confrontation']['running'])

    def test_restart_reaps_old_pid_before_creating_new_one(self):
        old_pid = self.manager.start('fall', CAMERA)
        old_process = self.manager.instances['fall'].process
        new_pid = self.manager.restart('fall', CAMERA)
        self.assertIsNotNone(old_process.poll())
        self.assertNotEqual(old_pid, new_pid)
        self.assertTrue(self.manager.snapshot()['fall']['running'])

    def test_invalid_restart_does_not_stop_working_process(self):
        pid = self.manager.start('fall', CAMERA)
        with self.assertRaises(ValueError):
            self.manager.restart('fall', 'not-a-uuid')
        self.assertEqual(self.manager.snapshot()['fall']['pid'], pid)
        self.assertTrue(self.manager.snapshot()['fall']['running'])

    def test_force_kill_after_grace_timeout(self):
        ready = Path(self.tmp.name) / 'ready'
        code = ("import signal,time; from pathlib import Path; "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                f"Path({str(ready)!r}).touch(); time.sleep(60)")
        self.manager.command = lambda *args: [sys.executable, '-u', '-c', code]
        self.manager.start('fall', CAMERA)
        process = self.manager.instances['fall'].process
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(ready.exists())
        self.manager.stop('fall')
        self.assertEqual(process.returncode, -signal.SIGKILL)
        self.assertTrue(any('nao encerrou no prazo' in message for message in self.messages))

    def test_stop_does_not_kill_unrelated_process(self):
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        try:
            self.manager.start('fall', CAMERA)
            self.manager.stop('fall')
            self.assertIsNone(unrelated.poll())
        finally:
            unrelated.terminate()
            unrelated.wait(timeout=5)

    def test_stop_closes_preview_child_in_owned_process_group(self):
        ready = Path(self.tmp.name) / 'child-pid'
        code = ("import subprocess,sys,time; from pathlib import Path; "
                "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                f"Path({str(ready)!r}).write_text(str(child.pid)); time.sleep(60)")
        self.manager.command = lambda *args: [sys.executable, '-u', '-c', code]
        self.manager.start('fall', CAMERA)
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(ready.exists())
        child_pid = int(ready.read_text())
        self.manager.stop('fall')
        # An orphan can briefly be a zombie waiting for the OS reaper; it is no
        # longer running and cannot keep the preview or camera open.
        status = subprocess.run(['ps', '-p', str(child_pid), '-o', 'stat='],
                                capture_output=True, text=True).stdout.strip()
        try:
            self.assertTrue(not status or status.startswith('Z'), status)
        finally:
            if status and not status.startswith('Z'):
                os.kill(child_pid, signal.SIGKILL)

    def test_commands_use_detector_preview_flag_and_project_python(self):
        manager = InferenceProcesses(repo=self.tmp.name, python=sys.executable)
        for kind in ('fall', 'confrontation'):
            for preview in (True, False):
                command = manager.command(kind, CAMERA, preview)
                self.assertEqual(command[0], sys.executable)
                self.assertEqual(command[command.index('--detector') + 1], kind)
                self.assertIn('--show-preview' if preview else '--no-preview', command)

    def test_preview_cli_defaults_and_overrides(self):
        from scripts.run_fall_monitor_jobs import parse_args
        for options, expected in (([], None), (['--show-preview'], True), (['--no-preview'], False)):
            with patch.object(sys, 'argv', ['monitor', *options]):
                self.assertIs(parse_args().show_preview, expected)

    def test_pose_controls_apply_only_to_fall_process(self):
        manager = InferenceProcesses(repo=self.tmp.name, python=sys.executable)
        command = manager.command('fall', CAMERA, True, True, 'assist', 0.06, '/tmp/pose model.pt')
        self.assertIn('--person-crop', command)
        self.assertEqual(command[command.index('--pose-mode') + 1], 'assist')
        self.assertEqual(command[command.index('--pose-weight') + 1], '0.06')
        self.assertIn('/tmp/pose model.pt', command)
        confrontation = manager.command('confrontation', CAMERA, True, True, 'assist', 0.06)
        self.assertNotIn('--pose-mode', confrontation)
        self.assertNotIn('--person-crop', confrontation)
        with self.assertRaises(ValueError):
            manager.command('fall', CAMERA, True, pose_weight=0.5)

    def test_pose_cli_validation(self):
        from scripts.run_fall_monitor_jobs import parse_args
        with patch.object(sys, 'argv', ['monitor', '--person-crop', '--pose-mode', 'observe', '--pose-weight', '0.05']):
            args = parse_args()
            self.assertTrue(args.person_crop)
            self.assertEqual(args.pose_mode, 'observe')
            self.assertEqual(args.pose_weight, 0.05)
        with patch.object(sys, 'argv', ['monitor', '--pose-weight', '0.5']), self.assertRaises(SystemExit):
            parse_args()


if __name__ == '__main__':
    unittest.main()
