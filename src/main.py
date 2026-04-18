"""Main entry point for the Cisco FMC MCP Server."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings, init_db
from src.core.mcp_server import FMCMCPServer
from src.services.database_init import initialize_database_defaults


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Cisco FMC MCP Server — Secure Firewall Management Center API platform"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="default",
        help="Name of the FMC device entry to connect to (must exist in database). Default: 'default'",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Override logging level from environment",
    )
    return parser.parse_args()


def setup_logging(log_level: str = None):
    settings = get_settings()
    level = log_level or settings.log_level
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


async def main():
    args = parse_arguments()
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting Cisco FMC MCP Server...")

        logger.info("Initializing database...")
        await init_db()

        logger.info("Initializing database defaults...")
        await initialize_database_defaults()

        device_name = args.device
        logger.info("Using FMC device: %s", device_name)

        server = FMCMCPServer(device_name=device_name)
        logger.info("Note: Edit mode is controlled via the database (security_config table)")
        await server.run()

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as exc:
        logger.error("Fatal error: %s", exc, exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Server stopped")


if __name__ == "__main__":
    asyncio.run(main())
