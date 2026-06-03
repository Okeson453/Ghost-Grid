"""GHOST GRID production entry point."""

import asyncio
import logging
from config import get_settings

async def main():
    settings = get_settings()
    logging.info(f"Starting GHOST GRID, paper={settings.paper_trading}")
    # TODO: wire components

if __name__ == "__main__":
    asyncio.run(main())
