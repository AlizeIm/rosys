from __future__ import annotations
from pydantic import BaseModel
from typing import Optional
import PIL.Image
import PIL.ImageDraw
import io
from .detection import Detection
import urllib.parse


class ImageSize(BaseModel):
    width: int
    height: int

    @property
    def tuple(self):
        return (self.width, self.height)


class Image(BaseModel):
    camera_id: str
    size: ImageSize
    time: float  # World time of recording
    data: Optional[bytes] = None
    detections: Optional[list[Detection]] = None

    @property
    def url(self) -> str:
        return f'camera/{urllib.parse.quote_plus(self.camera_id)}/{self.time}'

    @property
    def id(self) -> str:
        return f'{self.camera_id}/{self.time}'

    @staticmethod
    def create_placeholder(text: str, time: float = None) -> Image:
        img = PIL.Image.new('RGB', (260, 200), color=(73, 109, 137))
        d = PIL.ImageDraw.Draw(img)
        d.text((img.width/2-len(text)*3, img.height/2-5), text, fill=(255, 255, 255))
        bytesio = io.BytesIO()
        img.save(bytesio, format='PNG')
        image = Image(camera_id='no_cam_id', time=time or 0, size=ImageSize(width=img.width, height=img.height))
        image.data = bytesio.getvalue()
        return image

    def __hash__(self) -> int:
        return hash(self.id)
