import gc
import logging
import os
import tracemalloc
from typing import Optional

import psutil
from fastapi import Request
from psutil._common import bytes2human
from starlette.applications import ASGIApp
from starlette.middleware.base import BaseHTTPMiddleware

import rosys

log = logging.getLogger('rosys.analysis.memory')


class MemoryMiddleware(BaseHTTPMiddleware):

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.last_mem: Optional[int] = None

    async def dispatch(self, request: Request, call_next):
        mem = get_process_memory()
        response = await call_next(request)
        if response.headers.get('x-nicegui-content') == 'page' and self.last_mem is not None:
            log.info(f'GET {request.get("path")} increased memory by {bytes2human(mem - self.last_mem)} '
                     f'and is now {bytes2human(mem)}')
        self.last_mem = mem
        return response


def get_process_memory() -> int:
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    return mem_info.rss


def get_humanreadable_process_memory() -> int:
    return bytes2human(get_process_memory())


def compare_tracemalloc_snapshots(snapshot, prev_snapshot):
    stats = snapshot.compare_to(prev_snapshot, 'traceback')
    for stat in stats[:10]:
        trace = '\n'.join(stat.traceback.format())
        usage = f'{bytes2human(stat.size_diff)} new, {bytes2human(stat.size)} total; {stat.count_diff} new memory blocks, {stat.count} total'
        log.info(f'{trace}"\n"{usage}')


def observe_memory_growth(with_tracemalloc: bool = False) -> None:
    log.info('Observing memory growth')
    prev_memory: int = 0
    prev_snapshot: Optional[tracemalloc.Snapshot] = None
    if with_tracemalloc:
        tracemalloc.start(10)

    async def stats() -> None:
        nonlocal prev_memory
        nonlocal prev_snapshot
        gc.collect()
        growth = rosys.analysis.memory.get_process_memory() - prev_memory
        # log.info('==============')
        log.info(
            f'memory growth: {bytes2human(growth)}, '
            f"now it's {rosys.analysis.memory.get_humanreadable_process_memory()}"
        )
        # log.info('==============')
        prev_memory = rosys.analysis.memory.get_process_memory()
        if with_tracemalloc:
            snapshot = tracemalloc.take_snapshot()
            if growth > 4 * 1e-6 and prev_snapshot is not None:
                await rosys.run.cpu_bound(compare_tracemalloc_snapshots, snapshot, prev_snapshot)
            prev_snapshot = snapshot

    rosys.on_repeat(stats, 60.0)
