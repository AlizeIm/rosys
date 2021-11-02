import numpy as np
from nicegui.ui import Ui
from nicegui.events import KeyEventArguments
from rosys.world.point import Point
from rosys.actors.steerer import Steerer


class KeyboardControl:

    # these will be set by rosys.ui.configure
    steerer: Steerer = None
    ui: Ui = None

    def __init__(self, *, default_speed: float = 2.0):
        self.ui.keyboard(on_key=self.handle_keys)
        self.direction = Point(x=0, y=0)
        self.speed = default_speed

    def handle_keys(self, e: KeyEventArguments):
        if e.action.repeat:
            return

        # change speed via number key
        if e.action.keydown and e.key.number is not None:
            self.speed = e.key.number
            self.direction.y = self.speed * np.sign(self.direction.y)
            self.direction.x = self.speed * np.sign(self.direction.x)
            self.steerer.update(self.direction.y, self.direction.x)

        # update individual speed components via arrow keys
        if e.modifiers.shift and e.key.is_cursorkey:
            if e.action.keydown and self.direction.x == 0 and self.direction.y == 0:
                self.steerer.start()

            new_speed = self.speed if e.action.keydown else 0
            if e.key.arrow_left:
                self.direction.y = -new_speed
            elif e.key.arrow_right:
                self.direction.y = +new_speed
            elif e.key.arrow_up:
                self.direction.x = +new_speed
            elif e.key.arrow_down:
                self.direction.x = -new_speed
            self.steerer.update(self.direction.y, self.direction.x)

            if e.action.keyup and self.direction.x == 0 and self.direction.y == 0:
                self.steerer.stop()

        # stop when releasing shift key
        if e.key.shift and e.action.keyup:
            self.direction.y = 0
            self.direction.x = 0
            self.steerer.stop()
