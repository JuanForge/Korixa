opus_frame_limits = {
    8000:  {"min_frame": 20,   "max_frame": 960,  "min_ms": 2.5,  "max_ms": 120},
    12000: {"min_frame": 30,   "max_frame": 1440, "min_ms": 2.5,  "max_ms": 120},
    16000: {"min_frame": 40,   "max_frame": 1920, "min_ms": 2.5,  "max_ms": 120},
    24000: {"min_frame": 60,   "max_frame": 2880, "min_ms": 2.5,  "max_ms": 120},
    # 32000: {"min_frame": 80,   "max_frame": 3840, "min_ms": 2.5,  "max_ms": 120},
    # 44100: {"min_frame": 110,  "max_frame": 5292, "min_ms": 2.5,  "max_ms": 120},
    48000: {"min_frame": 120,  "max_frame": 5760, "min_ms": 2.5,  "max_ms": 120}
}
import time
import queue
import pyaudio
import threading
import numpy as np
from opuslib import Encoder, Decoder
class korixa:
    def __init__(self):
        self.audio = None
        self.RATE = 48000
        self.FRAME = opus_frame_limits[self.RATE]["max_frame"]
        self.BITRATE = 6000
        self.encoder = None
        self.decoder = None
        self.lockAudio = threading.RLock()

    def _AudioIN(self):
        with self.lockAudio:
            if self.audio == None:
                self.audio = pyaudio.PyAudio()
        stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1, # MONO
            rate=self.RATE, # 48kHz
            input=True,
            frames_per_buffer=self.FRAME
        )
        while True:
            yield stream.read(self.FRAME, exception_on_overflow=False)
    
    def AudioIN(self):
        audio_gen = self._AudioIN()
        next(audio_gen)
        return audio_gen
    
    def _AudioOUT(self):
        with self.lockAudio:
            if self.audio == None:
                self.audio = pyaudio.PyAudio()
        stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1, # MONO
            rate=self.RATE, # 48kHz
            output=True,
            frames_per_buffer=self.FRAME
        )
        while True:
            data = (yield)
            if data is None:
                break
            stream.write(data)
    def AudioOUT(self):
        audio_gen = self._AudioOUT()
        next(audio_gen)
        return audio_gen
    
    #def updateRATE(self, frequency: int):
    #    self.RATE = frequency
    #    self.FRAME = opus_frame_limits[frequency]["max_frame"]

    def encode(self, pcm: bytes) -> bytes:
        if self.encoder == None:
            self.encoder = Encoder(self.RATE, 1, "audio")
        self.encoder.bitrate = self.BITRATE
        return self.encoder.encode(pcm, self.FRAME)
    
    def decode(self, encoded: bytes) -> bytes:
        if self.decoder == None:
            self.decoder = Decoder(self.RATE, 1)
        return self.decoder.decode(encoded, self.FRAME)

    
    def updateBITRATE(self, bitrate: int):
        self.BITRATE = bitrate
        
    
    def assemblePCM(self, *pcms: bytes) -> bytes:
        arrays = [np.frombuffer(pcm, dtype=np.int16) for pcm in pcms]
    
        max_len = max(len(arr) for arr in arrays)
    
        arrays = [np.pad(arr, (0, max_len - len(arr)), 'constant') if len(arr) < max_len else arr
                  for arr in arrays]
    
        mixed = sum(arr.astype(int) for arr in arrays)
    
        mixed = np.clip(mixed, -32768, 32767)
    
        return mixed.astype(np.int16).tobytes()

class audio:
    def __init__(self, korixa_instance: korixa = None):
        self.korixa = korixa_instance
        self.buffer = {}
        self.start_time = None
        self.Queue = {}
        self.timebloc = 0.100  # 100 ms
    def add(self, pcm: bytes, username: str):
        if not self.start_time:
            self.start_time = time.monotonic()

        if not username in self.buffer:
            self.Queue[username] = queue.Queue()
            self.buffer[username] = {"chunks": [], "timestamp": time.monotonic()}
        # self.buffer[username]["chunks"].append(chunk)
        self.Queue[username].put(pcm)
        data: list[list[bytes]] = []
        if time.monotonic() - self.start_time >= self.timebloc:
            self.start_time = time.monotonic()
            #self.timebloc = 0.110
            for username, Queue in self.Queue.items():
                entry = []
                Queue: queue.Queue
                username: str
                print(f"User {username} has {Queue.qsize()} chunks in queue.")
                while not Queue.empty():
                    entry.append(Queue.get_nowait())
                if entry:
                    data.append(entry)
        out = []
        if data:
            max_len = max(len(user_chunks) for user_chunks in data)
        
            for index in range(max_len):
                entry = []
                for user_chunks in data:
                    if index < len(user_chunks):
                        entry.append(user_chunks[index])
                
                if entry:
                    out.append(self.korixa.assemblePCM(*entry))
            return out
        else:
            return None


if __name__ == "__main__":
    session = audio()
    session.add(b"test1", "user1")
    session.add(b"test2", "user1")

    import time

    kor = korixa()
    kor.BITRATE = 48000
    inAudio = kor.AudioIN()
    outAudio = kor.AudioOUT()
    
    for chunk in inAudio:
        print(f"Read {len(chunk)} bytes of audio data")
        chunk = kor.encode(chunk)
        print(f"Encoded to {len(chunk)} bytes")
        chunk = kor.decode(chunk)
        outAudio.send(chunk)
        #kor.BITRATE += 200
        
    print("Finished reading audio data.")
    time.sleep(5)