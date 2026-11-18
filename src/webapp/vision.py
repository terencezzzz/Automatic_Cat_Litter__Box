"""Adapters for the existing detector and a bounded private-network camera fetch."""
import io
import ipaddress
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
MAX_IMAGE = 8 * 1024 * 1024


def camera_address(value):
    value = value.strip()
    if not value:
        return ''
    if '://' not in value:
        value = 'http://' + value
    url = urlsplit(value)
    if (url.scheme != 'http' or not url.hostname or url.username or url.password
            or url.port not in (None, 80, 8080) or url.query or url.fragment
            or url.path not in ('', '/', '/capture')):
        raise ValueError('相机必须是局域网 HTTP 地址，端口为 80 或 8080，路径为 /capture。')
    # Resolve once and use the checked numeric address for the actual request.
    addresses = socket.getaddrinfo(url.hostname, url.port or 80, type=socket.SOCK_STREAM)
    address = ipaddress.ip_address(addresses[0][4][0])
    if not (address.version == 4 and any(address in net for net in (
            ipaddress.ip_network('10.0.0.0/8'), ipaddress.ip_network('172.16.0.0/12'),
            ipaddress.ip_network('192.168.0.0/16')))):
        raise ValueError('相机地址必须位于家中的私有局域网。')
    return f'http://{address}:{url.port or 80}/capture'


def normalise_image(data):
    if len(data) > MAX_IMAGE:
        raise ValueError('照片不能超过 8 MB。')
    with Image.open(io.BytesIO(data)) as photo:
        if photo.width * photo.height > 20_000_000:
            raise ValueError('照片分辨率过大。')
        photo = photo.convert('RGB')
        photo.thumbnail((1600, 1600))
        output = io.BytesIO()
        photo.save(output, 'JPEG', quality=90)
        return output.getvalue()


def fetch_photo(source):
    address = camera_address(source)
    if not address:
        raise ValueError('请先在设置中填写相机地址。')
    started = time.monotonic()
    with requests.Session() as client:
        client.trust_env = False
        with client.get(address, timeout=(2, 3), allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                raise ValueError(f'相机返回 HTTP {response.status_code}。')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > MAX_IMAGE or time.monotonic() - started > 4:
                    raise ValueError('相机响应过大或超时。')
    return normalise_image(data)


class Detector:
    def __init__(self):
        # The standalone scripts intentionally use sibling imports.
        path = str(ROOT / 'src' / 'vision')
        if path not in sys.path:
            sys.path.insert(0, path)
        from detect import YOLO
        self.cat_model = YOLO(str(ROOT / 'models' / 'yolo26n.pt'))
        self.waste_model = YOLO(str(ROOT / 'models' / 'weights.pt'))

    def decode(self, data):
        import cv2
        import numpy as np
        return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)

    def cat(self, data):
        from detect_cat import predict_cat
        _, cats = predict_cat(self.cat_model, self.decode(data), 0.35)
        return bool(cats)

    def waste(self, data):
        import cv2
        from detect import predict_waste
        result, report = predict_waste(self.waste_model, self.decode(data), 0.32)
        ok, encoded = cv2.imencode('.jpg', result.plot())
        if not ok:
            raise ValueError('无法保存检测照片。')
        return report, encoded.tobytes()
