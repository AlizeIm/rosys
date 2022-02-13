import gc
import psutil
from .actor import Actor
from .. import sleep


class GarbageCollector(Actor):
    ''' Disableing Python's automatic garbage collection to optimize performance.
    '''

    interval: float = 10*60
    mbit_limit: int = 300

    starting_msg = 'performing garbage collection'
    finished_msg = 'finished garbage collection'

    def __init__(self) -> None:
        super().__init__()
        gc.disable()

    async def step(self):
        await super().step()
        if psutil.virtual_memory().free < self.mbit_limit * 1000000:
            self.log.warning(f'less than {self.mbit_limit} mb of memory remaining -> {self.starting_msg}')
            gc.collect()
            await sleep(1)  # NOTE yield execution to make sure all warnings appear before we send the "finish" message
            self.log.warning(self.finished_msg)
