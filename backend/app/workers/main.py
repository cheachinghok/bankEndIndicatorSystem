"""Worker runtime entrypoint.

Runs the price stream + candle poller concurrently. Both are independent — if
one crashes, the other keeps running (with its own retry policy). Ctrl-C or
SIGTERM cancels both and shuts down cleanly.

Run:
    python -m app.workers.main
"""
import asyncio
import logging
import signal

from app.core.config import get_settings
from app.services.market_data.oanda_provider import OandaProvider
from app.workers.candle_poller import run_candle_poller
from app.workers.price_stream import run_price_stream
from app.workers.signal_worker import run_signal_worker

SYMBOLS = ["XAUUSD"]


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


async def _amain() -> None:
    settings = get_settings()
    _configure_logging(settings.log_level)
    log = logging.getLogger("workers")

    if not settings.oanda_api_token:
        raise RuntimeError("OANDA_API_TOKEN is not set. See .env.example.")
    if not settings.oanda_account_id:
        raise RuntimeError("OANDA_ACCOUNT_ID is not set. See .env.example.")

    provider = OandaProvider(
        api_token=settings.oanda_api_token,
        api_url=settings.oanda_api_url,
        account_id=settings.oanda_account_id,
    )

    stop_event = asyncio.Event()

    def _handle_signal() -> None:
        log.info("shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    stream_task = asyncio.create_task(
        run_price_stream(provider, SYMBOLS), name="price_stream"
    )
    poller_task = asyncio.create_task(
        run_candle_poller(provider, SYMBOLS), name="candle_poller"
    )
    signal_tasks = [
        asyncio.create_task(run_signal_worker(s), name=f"signal_worker[{s}]")
        for s in SYMBOLS
    ]
    stop_task = asyncio.create_task(stop_event.wait(), name="stop")

    all_workers = [stream_task, poller_task, *signal_tasks]
    log.info("workers started: %s", SYMBOLS)
    try:
        done, pending = await asyncio.wait(
            {*all_workers, stop_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        # Propagate any exception from a worker that died.
        for task in done:
            if task is stop_task:
                continue
            exc = task.exception()
            if exc:
                log.error("worker %s exited with %r", task.get_name(), exc)
    finally:
        for task in all_workers:
            task.cancel()
        await asyncio.gather(*all_workers, return_exceptions=True)
        await provider.aclose()
        log.info("workers stopped")


def main() -> None:
    try:
        asyncio.run(_amain())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
