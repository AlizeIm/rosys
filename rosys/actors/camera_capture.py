import numpy as np

import cv2
import re

from .actor import Actor
from ..world.camera import Camera, Frame


class CameraCapture(Actor):
    interval: float = 0.30

    def __init__(self):
        super().__init__()
        self.devices = {}  # mapping camera ids to opencv devices

    async def step(self):
        await super().step()
        await self.update_device_list()
        for uid, camera in self.world.cameras.items():
            if not camera.capture:
                return
            bytes = await self.run_io_bound(self.capture_frame, uid)
            camera.frames.append(Frame(data=bytes, time=self.world.time))

    def capture_frame(self, id):
        _, frame = self.devices[id].read()
        bytes = cv2.imencode('.jpg', frame)[1].tobytes()
        return bytes

    async def update_device_list(self):
        self.log.info(self.world.cameras)
        output = await self.run_sh(['v4l2-ctl', '--list-devices'])
        for line in output.splitlines():
            if 'Camera' in line:
                uid = re.search('\((.*)\)', line).group(1)
                if uid not in self.world.cameras:
                    self.world.cameras[uid] = Camera(id=uid)
                    self.log.info(f'adding camera {uid}')
            if '/dev/video' in line:
                num = int(line.strip().lstrip('/dev/video'))
                if uid not in self.devices:
                    self.devices[uid] = self.get_capture_device(num)

    def get_capture_device(self, index: int):
        try:
            capture = cv2.VideoCapture(index)
            if capture is None or not capture.isOpened():
                self.log.error(f'{index} is unavailable device')
            else:
                return capture
        except:
            self.log.exception(f'{index} device failed')

    async def tear_down(self):
        await super().tear_down()
        for capture in self.devices.values():
            capture.release()

    @staticmethod
    def is_operable():
        from shutil import which
        return which('v4l2-ctl') is not None
