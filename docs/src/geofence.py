#!/usr/bin/env python3
import rosys.ui
from nicegui import ui
from rosys import runtime
from rosys.actors import Automator, Driver, Odometer
from rosys.hardware import WheelsSimulation
from rosys.world import PathSegment, Pose, Robot, Spline


class GeoFenceGuard:

    def __init__(self, odometer: Odometer, automator: Automator) -> None:
        self.odometer = odometer
        self.automator = automator
        runtime.on_repeat(self.check_position, 0.1)

    def check_position(self) -> None:
        if abs(self.odometer.prediction.x) > 3 or abs(self.odometer.prediction.y) > 3:
            self.automator.PAUSE_AUTOMATION.emit('robot left the area')


# setup
robot = Robot()
odometer = Odometer()
wheels = WheelsSimulation(odometer)
driver = Driver(wheels)
automator = Automator()
geo_fence_guard = GeoFenceGuard(odometer, automator)

# ui
runtime.NEW_NOTIFICATION.register(ui.notify)
with ui.scene():
    rosys.ui.robot_object(robot, odometer)
label = ui.label()
ui.timer(0.1, lambda: label.set_text(f'pose: {odometer.prediction}'))


async def automation():
    await driver.drive_path([PathSegment(spline=Spline.from_poses(Pose(), Pose(x=5, y=1)))])
rosys.ui.automation_controls(automator, default_automation=automation)

# start
ui.on_startup(runtime.startup())
ui.on_shutdown(runtime.shutdown())
ui.run(title='RoSys')
