import pytest
from world.clock import Clock
from world.robot import Robot
from world.world import World


@pytest.mark.asyncio
async def test_intervals():

    robot = Robot(width=0.5)
    clock = Clock(interval=0.1)
    world = World(clock=clock, robot=robot)

    await world.simulate(seconds=1.0)
    assert world.clock.time > 1.0

    await world.simulate(seconds=1.0)
    assert world.clock.time > 2.0
