import asyncio
from typing import Coroutine, Optional
from .. import event, task_logger
from ..automations import Automation
from . import Actor


class Automator(Actor):
    def __init__(self, default_automation: Coroutine = None) -> None:
        super().__init__()
        self.automation: Optional[Automation] = None
        self.default_automation = default_automation
        event.register(event.Id.PAUSE_AUTOMATIONS, self.pause)

    @property
    def is_stopped(self) -> bool:
        return self.automation is None or self.automation.is_stopped

    @property
    def is_running(self) -> bool:
        return self.automation is not None and self.automation.is_running

    @property
    def is_paused(self) -> bool:
        return self.automation is not None and self.automation.is_paused

    def start(self, coro: Optional[Coroutine] = None):
        self.stop(because='new automation starts')
        coro_ = coro or self.default_automation or asyncio.sleep(0)
        self.automation = Automation(coro_, self._handle_exception)
        task_logger.create_task(asyncio.wait([self.automation]), name='automation')

    def pause(self, because: str):
        if self.is_running:
            self.automation.pause()
            event.emit(event.Id.PAUSE_AUTOMATIONS, because)
            event.emit(event.Id.NEW_NOTIFICATION, f'pausing automation because {because}')

    def resume(self):
        if self.is_paused:
            self.automation.resume()

    def stop(self, because: str):
        if not self.is_stopped:
            self.automation.stop()
            event.emit(event.Id.PAUSE_AUTOMATIONS, because)
            event.emit(event.Id.NEW_NOTIFICATION, f'stopping automation because {because}')

    def _handle_exception(self, e: Exception):
        self.stop(because='an exception occurred in an automation')

    async def tear_down(self):
        await super().tear_down()
        self.stop()
