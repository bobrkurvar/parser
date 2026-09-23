import asyncio
from desktop import App
from fl.backend import AsyncBackend as FlBackend
from hh.backend import AsyncBackend as HHBackend
from async_runtime import AsyncRuntime
from core.logger import setup_logging
from adapters.llm import YandexAIProvider
from hh.literals.search_keywords import SEARCH_QUERIES

setup_logging()

async def main():
    runtime = AsyncRuntime
    ai_provider = YandexAIProvider()
    fl_backend = FlBackend(runtime=runtime, ai_provider=ai_provider)
    hh_backend = HHBackend(runtime=runtime, ai_provider=ai_provider, queries=SEARCH_QUERIES)
    app = App(fl_backend=fl_backend, hh_backend=hh_backend, runtime=runtime)
    app.mainloop()

if __name__ == "__main__":
    asyncio.run(main())