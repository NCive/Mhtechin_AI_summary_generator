"""Lightweight, persistent SQLite-backed background worker."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import settings
from app.core.locks import HEAVY_JOB_LOCK
from app.db.database import get_db
from app.services.llm import LLMUnavailable, is_server_ready
from app.services.pipeline import process_meeting_pipeline

logger = logging.getLogger(__name__)


def claim_pending_meeting() -> str | None:
    """Atomically find and claim one eligible pending meeting.

    Only meetings with source='upload' and non-null media_path are claimed.
    Online meetings without media (source='join') are ignored.
    """
    with get_db() as conn:
        row = conn.execute(
            """SELECT id FROM meetings
               WHERE status = 'pending' AND source = 'upload' AND media_path IS NOT NULL
               ORDER BY created_at ASC, rowid ASC LIMIT 1"""
        ).fetchone()

        if not row:
            return None

        meeting_id = row["id"]
        cursor = conn.execute(
            "UPDATE meetings SET status = 'processing', error = NULL WHERE id = ? AND status = 'pending'",
            (meeting_id,),
        )
        if cursor.rowcount > 0:
            logger.info("Worker claimed meeting %s for processing.", meeting_id)
            return meeting_id

        return None


def recover_interrupted_meetings() -> int:
    """Safely reset meetings that were interrupted mid-processing (e.g. server restart) back to 'pending'."""
    with get_db() as conn:
        cursor = conn.execute(
            """UPDATE meetings
               SET status = 'pending'
               WHERE status = 'processing' AND source = 'upload'"""
        )
        count = cursor.rowcount
        if count > 0:
            logger.info("Worker recovered %d interrupted meeting(s) to 'pending'.", count)
        return count


async def worker_loop() -> None:
    """Continuous background worker loop polling for pending meetings."""
    logger.info("Background worker loop started.")
    # 1. Recover any interrupted jobs from previous runs
    try:
        recover_interrupted_meetings()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to recover interrupted meetings on worker startup: %s", exc)

    server_was_down = False
    while True:
        try:
            if not is_server_ready():
                if not server_was_down:
                    logger.warning(
                        "LLM server is not ready; worker is waiting before claiming meetings."
                    )
                    server_was_down = True
                await asyncio.sleep(settings.WORKER_POLL_INTERVAL)
                continue
            elif server_was_down:
                logger.info("LLM server is now ready; worker resuming meeting claims.")
                server_was_down = False

            meeting_id = claim_pending_meeting()
            if meeting_id:
                logger.info("Processing meeting %s in threadpool...", meeting_id)
                try:
                    # Offload CPU/IO intensive operations outside the API event loop
                    # Protect against memory exhaustion with shared heavy job lock
                    async with HEAVY_JOB_LOCK:
                        await asyncio.to_thread(process_meeting_pipeline, meeting_id)
                except LLMUnavailable as exc:
                    logger.warning(
                        "Meeting %s deferred back to pending (LLM unavailable: %s)",
                        meeting_id,
                        exc,
                    )
                    with get_db() as conn:
                        conn.execute(
                            "UPDATE meetings SET status = 'pending', error = ? WHERE id = ?",
                            (f"Deferred: {exc}", meeting_id),
                        )
                    await asyncio.sleep(settings.WORKER_POLL_INTERVAL)
                except Exception as exc:
                    logger.exception("Failed to process meeting %s", meeting_id)
                    # Persist actionable error in DB
                    with get_db() as conn:
                        conn.execute(
                            "UPDATE meetings SET status = 'failed', error = ? WHERE id = ?",
                            (str(exc)[:500], meeting_id),
                        )
                # Check immediately for another meeting before sleeping
                continue

            # Sleep between polling attempts
            await asyncio.sleep(settings.WORKER_POLL_INTERVAL)
        except asyncio.CancelledError:
            logger.info("Background worker loop received shutdown signal. Exiting.")
            break
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error in worker loop: %s", exc)
            await asyncio.sleep(settings.WORKER_POLL_INTERVAL)


class WorkerManager:
    """Manages the background worker lifecycle."""

    def __init__(self) -> None:
        self._task: asyncio.Task[Any] | None = None

    def start(self) -> None:
        if not settings.ENABLE_BACKGROUND_WORKER:
            logger.info("Background worker is disabled by configuration.")
            return

        if self._task is None or self._task.done():
            self._task = asyncio.create_task(worker_loop(), name="meeting-worker-loop")
            logger.info("Started background worker task.")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            logger.info("Stopping background worker task...")
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None
                logger.info("Background worker task stopped.")


worker_manager = WorkerManager()
