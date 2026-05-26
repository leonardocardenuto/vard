from __future__ import annotations

import logging
import signal
import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.core.config import get_settings
from api.services.fall_monitor import CameraMonitorSupervisor


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    configure_logging()
    logger = logging.getLogger("fall_monitor.jobs")
    stop_event = threading.Event()
    supervisor = CameraMonitorSupervisor(get_settings())

    def _stop(*_):
        logger.info("Encerrando jobs de monitoramento de cameras.")
        stop_event.set()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    supervisor.start()
    logger.info("Jobs de monitoramento ativos. Pressione Ctrl+C para encerrar.")
    try:
        while not stop_event.wait(1.0):
            pass
    finally:
        supervisor.stop()


if __name__ == "__main__":
    main()
