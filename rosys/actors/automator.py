from enum import auto
from typing import Coroutine, List, Optional

from rosys.actors.esp import Esp
from ..world.world import World, AutomationState
from ..automations import drive_path
from .actor import Actor
from .. import event


class Automator(Actor):
    interval: float = 0.1

    def __init__(self, esp: Esp, default_automation: Coroutine = None) -> None:
        super().__init__()
        self.routines: List[Coroutine] = []
        self.esp = esp
        self.default_automation = default_automation
        event.register(event.Id.PAUSE_AUTOMATIONS, self._pause)

    def add(self, coro: Coroutine):
        self.routines.append(coro)

    def replace(self, coro: Coroutine):
        [r.close() for r in self.routines]  # NOTE: this ensures we do not get warnings about missing await for our routines
        self.routines.clear()
        self.add(coro)

    async def step(self):
        if not self.routines or self.world.automation_state == AutomationState.DISABLED:
            if not self.routines:
                if self.default_automation:
                    self.log.info('automations where disabled, now using default automation')
                    self.add(self.default_automation)
                elif self.world.path:
                    self.log.info('automations where disabled, now using world.path')
                    self.add(drive_path(self.world, self.esp))
            if self.routines:
                self.world.automation_state = AutomationState.STOPPED

        if self.world.automation_state != AutomationState.RUNNING:
            return

        for coro in self.routines:
            try:
                coro.send(None)
            except StopIteration:
                self.routines.remove(coro)
                if not self.routines:
                    await self.pause_automations(because='the last one has completed')
                    self.world.automation_state = AutomationState.DISABLED
            except:
                await self.pause_automations(because='an exception occurred in an automation')
                self.routines.clear()
                self.log.exception(f'paused and cleared automations due to exception in {coro}')
                self.world.automation_state = AutomationState.DISABLED

    async def _pause(self, because: Optional[str] = None):
        '''Pauses the automation. 

        Only to be used internally. The proper way is to use runtime.pause(...) or fire event.Id.PAUSE_AUTOMATION. See rosys.io/automations.
        '''
        if self.world.automation_state == AutomationState.PAUSED:
            return
        self.world.automation_state = AutomationState.PAUSED
        if because:
            await event.call(event.Id.NEW_NOTIFICATION, f'pausing automations because {because}')
