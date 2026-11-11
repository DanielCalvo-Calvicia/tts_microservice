
import uvicorn
from dotenv import find_dotenv, load_dotenv
from shared_logging import get_logger, init_logging

from composition_root.containers.http_container import new_http_container
from infrastructure.config.server_config import ServerConfig
from infrastructure.config.tts_config import TtsConfig

logger = get_logger(__name__)


async def run_http() -> None:
    load_dotenv(find_dotenv(".env"))
    server_cfg = ServerConfig.from_env()
    tts_cfg = TtsConfig.from_env()
    init_logging("tts")

    container = new_http_container(server_cfg, tts_cfg)
    server = uvicorn.Server(
        uvicorn.Config(
            container.app,
            host=server_cfg.host,
            port=server_cfg.port,
            log_config=None,
            timeout_keep_alive=60,
        )
    )
    logger.info(
        "Starting server",
        service_name=server_cfg.service_name,
        host=server_cfg.host,
        port=server_cfg.port,
    )
    await server.serve()  # returns after SIGINT/SIGTERM; nothing holds a device to release
    logger.info("Server stopped")
