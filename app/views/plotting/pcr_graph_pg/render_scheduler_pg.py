# app/views/plotting/pcr_graph_pg/render_scheduler_pg.py
# -*- coding: utf-8 -*-
"""
Render Scheduler for PCR Graph.

Deferred and batched rendering with frame rate limiting.
"""

from __future__ import annotations

import logging
from time import perf_counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def schedule_render(
    renderer,
    *,
    full: bool = False,
    overlay: bool = False,
    force_flush: bool = False,
) -> None:
    """Schedule render operation with optional force flush."""
    renderer._pending_full_draw = renderer._pending_full_draw or full
    renderer._pending_overlay = renderer._pending_overlay or overlay

    if force_flush:
        if renderer._render_timer.isActive():
            renderer._render_timer.stop()
        flush_pending_render(renderer)
        return

    elapsed_ms = (perf_counter() - renderer._last_render_ts) * 1000.0
    delay = max(0, int(renderer._frame_interval_ms - elapsed_ms))

    if renderer._render_timer.isActive():
        return

    renderer._render_timer.start(delay)


def flush_pending_render(renderer) -> None:
    """Flush pending render operations."""
    full = renderer._pending_full_draw
    overlay = renderer._pending_overlay or full

    renderer._pending_full_draw = False
    renderer._pending_overlay = False

    if full or overlay:
        renderer.update()

    renderer._last_render_ts = perf_counter()


def cancel_pending_render(renderer) -> None:
    """Cancel pending render operations."""
    if renderer._render_timer.isActive():
        renderer._render_timer.stop()

    renderer._pending_full_draw = False
    renderer._pending_overlay = False


def set_frame_interval(renderer, interval_ms: int) -> None:
    """Set frame rate limit interval."""
    if interval_ms <= 0:
        logger.warning("Invalid frame interval: %dms, ignoring", interval_ms)
        return
    renderer._frame_interval_ms = interval_ms