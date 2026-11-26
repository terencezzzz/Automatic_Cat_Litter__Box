"""USB controller for the local monitor. No commands are replayed after reconnect."""
from threading import Event, Lock
from time import monotonic


class Cleaning:
    def __init__(self, port, window):
        self.port = port
        self.window = window
        self.lock = Lock()
        self.closed = Event()
        self.clear = None
        self.clear_since = None
        self.present = None
        self.frame_at = 0
        self.requested = False
        self.stop_requested = False
        self.status = 'Disconnected'
        self.result = ''

    def observe(self, present, started):
        with self.lock:
            if present is not False or started - self.frame_at > 4:
                self.clear_since = None
                self.requested = False
            if present is False and self.clear_since is None:
                self.clear_since = started
            self.frame_at = started
            self.present = present
            self.clear = started if present is False else None

    def snapshot(self):
        with self.lock:
            return dict(motor=self.status, result=self.result,
                        catPresent=self.present if monotonic() - self.frame_at < 3 else None,
                        canRun=self.can_run())

    def can_run(self):
        now = monotonic()
        return (self.status == 'Ready' and not self.requested and not self.stop_requested
                and self.clear is not None and now - self.clear < 3
                and self.clear_since is not None and self.clear - self.clear_since >= 10)

    def run_once(self):
        with self.lock:
            if not self.can_run():
                return False
            self.result = 'Start requested'
            self.requested = True
            return True

    def stop(self):
        with self.lock:
            self.requested = False
            self.stop_requested = True
            self.clear = self.clear_since = None

    def loop(self):
        import serial

        while not self.closed.is_set():
            try:
                with serial.Serial(self.port, 9600, timeout=.15, write_timeout=.2) as link:
                    try:
                        self.session(link)
                    finally:
                        link.write(b'x\n')
            except (OSError, serial.SerialException):
                pass
            with self.lock:
                self.status = 'Disconnected'
                self.requested = False
                self.result = 'Check USB and PawLog controller firmware'
            self.closed.wait(2)

    def session(self, link):
        if self.closed.wait(2):
            return
        link.reset_input_buffer()
        link.write(f'x\nw {self.window[0]} {self.window[1]}\n'.encode('ascii'))
        if link.readline().strip() != b'pawlog-controller-v1':
            return
        sent_frame = None
        last_reply = monotonic()
        while not self.closed.is_set() and monotonic() - last_reply < 2:
            with self.lock:
                now = monotonic()
                fresh = self.clear if self.clear is not None and now - self.clear < 3 else None
                if self.stop_requested or fresh is None:
                    link.write(b'x\n')
                    self.stop_requested = self.requested = False
                    sent_frame = None
                elif fresh != sent_frame:
                    link.write(b'c\n')
                    sent_frame = fresh
                if self.requested and fresh is not None:
                    self.requested = False
                    self.status = 'Starting'
                    link.write(b'r\n')
                link.write(b's\n')
            while not self.closed.is_set():
                reply = link.readline().strip()
                if reply not in (b'ready', b'blocked', b'running', b'fault', b'returned', b'rejected'):
                    break
                last_reply = monotonic()
                with self.lock:
                    if reply in (b'returned', b'rejected', b'fault'):
                        self.result = {
                            b'returned': 'Cycle complete · tray at home',
                            b'rejected': 'Start blocked by Arduino',
                            b'fault': 'Stopped · inspect and reset Arduino',
                        }[reply]
                    self.status = {
                        b'ready': 'Ready', b'blocked': 'Blocked', b'running': 'Running',
                        b'fault': 'Fault', b'returned': 'Returned', b'rejected': 'Blocked',
                    }[reply]
            self.closed.wait(.1)
