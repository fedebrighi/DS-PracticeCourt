import logging
import sys
from config import get_settings


def setup_logging() -> None:
    # CONFIGURO IL LOGGING GLOBALE DEL NODO, CHIAMATA UNA VOLTA SOLO NEL LIFESPAN DI OGNI NODO
    settings = get_settings()
    log_level = logging.DEBUG if settings.debug else logging.INFO

    # ASCTIME È IL TIMESTAMP, NAME È IL MODULO
    frmt = "%(asctime)s | %(levelname)-8s | {node} | %(name)s | %(message)s".format(node=settings.node_id)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(frmt, datefmt="%Y-%m-%dT%H:%M:%S"))

    # RIMUOVO HANDLER PRECEDENTI PRIMA DI CONFIGURARE PER EVITARE DUPLICATI
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # SILENZIO LOGGER DI LIBRERIE TERZE DI CUI NON MI INTERESSA
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)