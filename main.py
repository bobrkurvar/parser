import asyncio
from desktop_app import App
from backend import AsyncBackend
from core.logger import setup_logging

setup_logging()

async def main():
    backend = AsyncBackend()
    app = App(backend=backend)
    app.mainloop()
    backend.stop()

if __name__ == "__main__":
    asyncio.run(main())