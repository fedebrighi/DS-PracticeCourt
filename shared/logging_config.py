import logging
import sys
from shared.config import get_settings
import time

def setup_logging() -> None:
    # CONFIGURO IL LOGGING GLOBALE DEL NODO, CHIAMATA UNA VOLTA SOLO NEL LIFESPAN DI OGNI NODO
    settings = get_settings()
    log_level = logging.DEBUG if settings.debug else logging.INFO

    # ASCTIME È IL TIMESTAMP, NAME È IL MODULO
    frmt = "%(asctime)s | %(levelname)s | {node} | %(name)s | %(message)s".format(node=settings.node_id)

    formatter = logging.Formatter(frmt, datefmt="%Y-%m-%d T: %H:%M:%S")
    formatter.converter = time.localtime

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # RIMUOVO HANDLER PRECEDENTI PRIMA DI CONFIGURARE PER EVITARE DUPLICATI
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # SILENZIO LOGGER DI LIBRERIE TERZE DI CUI NON MI INTERESSA
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)