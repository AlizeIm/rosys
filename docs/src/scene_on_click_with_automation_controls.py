#!/usr/bin/env python3
import rosys.ui
from nicegui import ui
from rosys import runtime
from rosys.actors import Automator, Driver, Odometer
from rosys.hardware import WheelsSimulation
from rosys.world import Point, Robot

# setup
robot = Robot()
odometer = Odometer()
wheels = WheelsSimulation(odometer)
driver = Driver(wheels)
automator = Automator()


async def handle_click(msg):
    for hit in msg.hits:
        target = Point(x=hit.point.x, y=hit.point.y)
        automator.start(driver.drive_to(target))

# ui
runtime.NEW_NOTIFICATION.register(ui.notify)
with ui.scene(on_click=handle_click):
    rosys.ui.robot_object(robot, odometer, debug=True)
ui.label('click into the scene to drive the robot')
with ui.row():
    rosys.ui.automation_controls(automator)
ui.label('you can also pause/resume or stop the running automation')

# start
ui.on_startup(runtime.startup())
ui.on_shutdown(runtime.shutdown())
ui.run(title='RoSys', port=8080)
