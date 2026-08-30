import asyncio
from desktop_app import App
from backend import AsyncBackend
from core.logger import setup_logging
from adapters.llm import GroqProvider

setup_logging()

async def main():
    backend = AsyncBackend(ai_provider=GroqProvider())
    app = App(backend=backend)
    app.mainloop()
    backend.stop()

if __name__ == "__main__":
    asyncio.run(main())