import os
import logging
from asyncio import run
from json import dumps, loads
from typing import Any, Callable, Dict, List, Optional
from inspect import iscoroutine

from redis import Redis

from .exceptions import DatabaseNotConnectedError


__all__ = ["WorkerManager", "Worker"]

logger = logging.getLogger("worker_engine")
logging.basicConfig(level=logging.INFO)


class Worker:
    """Represents a registered worker function task."""

    def __init__(self, name: str, fn: Callable[..., Any]):
        self.name = name
        self.fn = fn


class WorkerManager:
    """
    Manages background tasks using a Redis List Queue.
    Ensures safe, atomic task dispatching and balanced multi-worker distribution.
    """

    def __init__(self, channel: str):
        self.channel = channel
        self.workers: List[Worker] = []
        self.rclient: Redis | None = None


    def connect(self,
                uri: str | None = None,
                rclient: Redis | None = None) -> None:
        """Initializes the connection to the Redis backend."""
        if uri:
            self.rclient = Redis.from_url(uri)
        elif rclient:
            self.rclient = rclient


    def call(self, worker_name: str, args: Dict[str, Any]) -> None:
        """
        Pushes a task execution contract onto the Redis queue list.
        """
        if not self.rclient:
            raise DatabaseNotConnectedError("Redis client is not connected. Run manager.connect() first.")

        payload = dumps({
            "worker": worker_name,
            "args": args
        })

        self.rclient.lpush(self.channel, payload)
        logger.debug(f"Task '{worker_name}' queued into channel '{self.channel}'.")


    def worker(self, name: Optional[str] = None):
        """
        Decorator to register python functions as executable tasks.
        Usage:
            @manager.worker()
            def my_task(param): ...
        """
        def decorator(fn: Callable[..., Any]):
            worker_name = name or fn.__name__
            self.workers.append(Worker(worker_name, fn))
            return fn
        return decorator


    async def listen(self) -> None:
        """
        Starts the blocking operational pool loop to process queued jobs.
        Run this inside your isolated background process entrypoint script.
        """
        if not self.rclient:
            raise DatabaseNotConnectedError("Redis client is not connected. Run manager.connect() first.")

        # Map for efficient O(1) matching inside the daemon runtime
        worker_map = {w.name: w.fn for w in self.workers}

        logger.info(f"🚀 Worker Engine safely listening on queue queue-list: {self.channel!r}")
        logger.info(f"Registered tasks: {", ".join(list(worker_map.keys()))}")

        while True:
            try:
                # BRPOP blocks the execution thread efficiently with 0% CPU consumption
                # until a task is available. timeout=0 keeps the connection alive indefinitely.
                # Returns a tuple: (bytes_channel, bytes_data)
                result = self.rclient.brpop(self.channel, timeout=0)

                if not result:
                    continue

                if iscoroutine(result):
                    result = await result

                data = result[1] # type: ignore

                # Unpack and parse contract
                payload = loads(data)
                worker_name: str = payload["worker"]
                args: Dict[str, Any] = payload["args"]

                func = worker_map.get(worker_name)
    
                if not func:
                    logger.warning(f"⚠️ Unhandled task request received: '{worker_name}'")
                    continue

                logger.info(f"💼 Executing background task: '{worker_name}'")
                await func(**args)
                logger.info(f"✅ Finished background task: '{worker_name}'")

            except Exception as e:
                logger.error(f"❌ Worker loop execution error encountered: {e}", exc_info=True)


    def start(self) -> None:
        run(self.listen())
