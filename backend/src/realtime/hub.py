import asyncio
import logging
from collections import defaultdict
from collections.abc import Iterable
from typing import Any, Protocol

logger = logging.getLogger(__name__)

ACCOUNT_DELETED_CLOSE_CODE = 4401


class Connection(Protocol):
    async def send_json(
        self, data: Any, mode: str = "text"
    ) -> None: ...

    async def close(
        self, code: int = 1000, reason: str | None = None
    ) -> None: ...


class RealtimeHub:
    def __init__(self, send_timeout: float = 1.0) -> None:
        self._send_timeout = send_timeout
        self._connections: defaultdict[int, set[Connection]] = (
            defaultdict(set)
        )

    def connect(self, user_id: int, websocket: Connection) -> None:
        self._connections[user_id].add(websocket)

    def disconnect(self, user_id: int, websocket: Connection) -> None:
        sockets = self._connections.get(user_id)
        if sockets is None:
            return
        sockets.discard(websocket)
        if not sockets:
            del self._connections[user_id]

    def connections(self, user_id: int) -> int:
        return len(self._connections.get(user_id, ()))

    async def send(
        self, user_ids: Iterable[int], event: dict[str, Any]
    ) -> None:
        await asyncio.gather(
            *(
                self._send_one(user_id, websocket, event)
                for user_id in set(user_ids)
                for websocket in list(
                    self._connections.get(user_id, ())
                )
            )
        )

    async def _send_one(
        self, user_id: int, websocket: Connection, event: dict[str, Any]
    ) -> None:
        try:
            async with asyncio.timeout(self._send_timeout):
                await websocket.send_json(event)
        except Exception:
            logger.warning("Dropping broken websocket of %s", user_id)
            self.disconnect(user_id, websocket)
            try:
                async with asyncio.timeout(self._send_timeout):
                    await websocket.close(code=1013, reason="RECONNECT")
            except Exception:
                logger.debug(
                    "Socket already unavailable for %s", user_id
                )

    async def close_user(self, user_id: int) -> None:
        for websocket in list(self._connections.pop(user_id, ())):
            try:
                async with asyncio.timeout(self._send_timeout):
                    await websocket.close(
                        code=ACCOUNT_DELETED_CLOSE_CODE,
                        reason="ACCOUNT_DELETED",
                    )
            except Exception:
                logger.warning(
                    "Failed to close websocket of %s", user_id
                )


hub = RealtimeHub()
