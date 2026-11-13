"""Cross-platform synthesized UI sounds; generated WAV clips are cached in temp storage."""
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import wave


class SoundService:
    SAMPLE_RATE = 44100
    _cache = {}
    _cache_lock = threading.Lock()

    def __init__(self, enabled=True):
        self.enabled = bool(enabled)

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)

    def play_queued(self):
        self._play("queued")

    def play_completed(self):
        self._play("completed")

    def play_error(self):
        self._play("error")

    def play_pop(self):
        """Play Apple-style acoustic Pop tone."""
        self._play("queued")

    def play_glass_chime(self):
        """Play Apple-style acoustic Glass Chime chord."""
        self._play("completed")

    def play_soft_bump(self):
        """Play Apple-style acoustic Soft Bump tone."""
        self._play("error")

    def _play(self, effect):
        if not self.enabled:
            return
        try:
            path = self._cached_clip(effect)
            threading.Thread(
                target=self._play_file, args=(path,),
                name="vortexdl-sound", daemon=True,
            ).start()
        except Exception:
            return

    @classmethod
    def _cached_clip(cls, effect):
        with cls._cache_lock:
            if effect in cls._cache and os.path.isfile(cls._cache[effect]):
                return cls._cache[effect]
            samples = cls._synthesize(effect)
            fd, path = tempfile.mkstemp(prefix=f"vortexdl-{effect}-", suffix=".wav")
            os.close(fd)
            with wave.open(path, "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(cls.SAMPLE_RATE)
                output.writeframes(b"".join(struct.pack("<h", x) for x in samples))
            cls._cache[effect] = path
            return path

    @classmethod
    def _synthesize(cls, effect):
        durations = {"queued": 0.09, "completed": 0.32, "error": 0.18}
        count = int(cls.SAMPLE_RATE * durations[effect])
        samples = []
        phase = 0.0
        for index in range(count):
            t = index / cls.SAMPLE_RATE
            if effect == "queued":
                envelope = min(1.0, t / 0.008) * min(1.0, (durations[effect] - t) / 0.03)
                value = (math.sin(2 * math.pi * 523 * t) + math.sin(2 * math.pi * 659 * t)) * 0.24 * envelope
            elif effect == "completed":
                envelope = math.exp(-t * 8.0)
                value = sum(math.sin(2 * math.pi * hz * t) for hz in (523, 784, 1046)) * 0.25 * envelope
            else:
                frequency = 220.0 - 45.0 * (t / durations[effect])
                phase += 2 * math.pi * frequency / cls.SAMPLE_RATE
                envelope = min(1.0, t / 0.012) * min(1.0, (durations[effect] - t) / 0.045)
                value = math.sin(phase) * 0.38 * envelope
            samples.append(max(-32767, min(32767, int(value * 32767))))
        return samples

    @staticmethod
    def _play_file(path):
        try:
            if sys.platform == "win32":
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif sys.platform == "darwin":
                subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                player = shutil.which("paplay") or shutil.which("aplay")
                if player:
                    subprocess.Popen([player, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            return
