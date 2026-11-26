"""Camera-only MotorTest adapter. A serial fault requires a process restart."""
from time import monotonic, sleep


class TimedMotor:
    def __init__(self, link):
        self.link = link
        self.running = False
        self.blocked = False

    def verify(self):
        deadline = monotonic() + 6
        self.link.reset_input_buffer()
        while monotonic() < deadline:
            self.link.write(b's\n')
            for _ in range(4):
                reply = self.link.readline().strip()
                if reply == b'pawlog-motortest-v1':
                    return
                if not reply:
                    break
            sleep(.15)
        raise RuntimeError('No MotorTest identification received. Check the Uno port and upload the updated MotorTest.ino.')

    def observe(self, present, captured_at):
        if self.running:
            while self.link.in_waiting:
                message = self.link.readline().strip()
                if message.startswith(b'Cycle finished'):
                    self.running = False
                    print('MotorTest timed cycle finished. Check tray position.', flush=True)
                elif message.startswith((b'Camera timeout', b'Automatic start blocked', b'Busy')):
                    self.blocked = True
                    self.stop()
                elif not message:
                    break
            if self.running:
                if present is False and monotonic() - captured_at < 1:
                    self.link.write(b'c\n')
                else:
                    self.blocked = True
                    self.stop()

    def start(self, captured_at):
        if self.blocked or self.running or monotonic() - captured_at >= 1:
            return False
        self.running = True
        self.link.write(b'ca\n')
        return True

    def stop(self):
        self.running = False
        self.link.write(b'x\n')
