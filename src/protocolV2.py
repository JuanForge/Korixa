import time
import cbor2
import queue
import socket
import struct
import secrets
import traceback
import threading

from functools import wraps
from datetime import datetime, timezone

class errors:
    class BlockSizeTooLarge(Exception): pass
    class BlockSizeTooLargeOnStream(Exception): pass

class v2:
    def __init__(self, sock: socket.socket, maxSizeBuffer: int = int(0.5 * 1024 *1024)): # 0.5 MB # 0.5 * 1024 *1024
        """
        Cette version du protocole est physiquement limitée a ce que chaque bloc ne dépasse pas 4 Go.
        """
        self.sock = sock
        self.buffer = b""
        self.lock = threading.RLock() # RLock # Lock
        self.lockRecv = threading.RLock()
        self.lockSend = threading.RLock()
        #self.QueueIN = queue.Queue()
        #self.QueueOUT = queue.Queue()
        self.maxSizeBuffer = maxSizeBuffer

    def _wrapperStream(func):
        def wrapper(*args, **kwargs):
            gen = func(*args, **kwargs)
            next(gen)
            return gen
        return wrapper


    def _wrapper(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.monotonic_ns()
            result = func(*args, **kwargs)
            end_time = time.monotonic_ns()
            duration_ms = (end_time - start_time) / 1_000_000
            print(f"[Ping] {func.__name__}: {duration_ms:.3f} ms")
            return result
        return wrapper
    
    def _encodeInt(self, value: int) -> bytes: # I == 4 Go # 4 bytes
        return struct.pack("!I", value)
    
    def _decodeInt(self, value: bytes) -> int:
        print(f"Decoding int from bytes: {value}")
        return struct.unpack("!I", value)[0]
    
    def _send(self, obj: dict):
        #print(f"Sending: {str(obj)[:256]}")
        ID = secrets.token_hex(8)
        payload = {"data": obj, "id": ID, "datetime": datetime.now(timezone.utc)}  # received
        payload = cbor2.dumps(payload)
        #print(f"Payload size: {len(payload)} bytes")
        size = self._encodeInt(len(payload))
        with self.lockSend:
            self.sock.sendall(size + payload) # msgpack.packb(data)

    def _recvall(self, size: int) -> bytes:
        with self.lockRecv:
            buffer = b""
            while True:
                data = self.sock.recv(size - len(buffer))
                if not data:
                    raise RuntimeError("PKG socket : ERROR : data size == 0")
                buffer += data
                if len(buffer) == size:
                    break
            return buffer
    
    def _recv(self) -> dict:
        dataSize = self._decodeInt(self._recvall(4))
        if dataSize > self.maxSizeBuffer:
            raise errors.BlockSizeTooLarge(f"71 : BUFFER OVERFLOW : data size > maxSizeBuffer, received size_data: {dataSize}, maxSizeBuffer: {self.maxSizeBuffer}")
        dataRaw = self._recvall(dataSize)
        entry: dict = cbor2.loads(dataRaw)
        return entry["data"]
    """
    def _recv(self) -> dict:
        buffer = b""
        size_data = None
        while True:
            data = self.sock.recv(self.maxSizeBuffer)
            if not data:
                raise RuntimeError("PKG socket : ERROR : data size == 0")
            buffer += data

            if len(buffer) >= 4 and size_data is None:
                size_data = self._decodeInt(buffer[:4])
                buffer = buffer[4:]
                if size_data > self.maxSizeBuffer:
                    raise errors.BlockSizeTooLarge(f"64 : BUFFER OVERFLOW : data size > maxSizeBuffer, received size_data: {size_data}, maxSizeBuffer: {self.maxSizeBuffer}")
            
            if len(buffer) > self.maxSizeBuffer:
                raise errors.BlockSizeTooLargeOnStream("67 : BUFFER OVERFLOW : buffer size > maxSizeBuffer")

            if size_data is not None: # return
                if len(buffer) >= size_data:
                    entry: dict = cbor2.loads(buffer[:size_data])
                    return entry["data"]
    """

    
    def recv(self, stream: bool = False):
        return self._recv()

    def send(self, obj: dict):
        self._send(obj)
        
    @_wrapperStream
    def sendStream(self):
        """Fonction non encore intégrée"""
        raise NotImplementedError("Fonction non encore intégrée")
        total = 0
        while True:
            data = (yield)
            if data is None:
                break
            total += data
            print(f"Reçu: {data}, total: {total}")
        return total
    
    #@_wrapper
    def apiPing(self):
        self._send({"type": "ping"})
        # if self._recv()["status"] == True:
        #     return True
        # else:
        #     return False

    @_wrapper
    def apiVersion(self) -> str:
        self._send({"type": "getVesrion"})
        return self._recv()["version"]
    
    @_wrapper
    def apiGetGroupList(self) -> list:
        self._send({"type": "GET-group-LIST"})
        data = self._recv()
        if isinstance(data, dict) and data["status"] == False:
            raise BaseException("V2:143 : Vous devez etre connecté pour obtenir la liste des salons.")
        else:
            return data
    
    @_wrapper
    def apiConnectTextRoom(self, ID: str = None) -> bool:
        self._send({"type": "CONNECT room@chat", "roomID": ID})
        if self._recv()["status"] == True:
            return True
        else:
            raise BaseException("V2:151 : Impossible de se connecter au salon de discussion.")
    
    @_wrapper
    def apiSendMessageTextRoom(self, message: str) -> bool:
        self._send({"type": "send-message", "message": message})
        """
        data = self._recv()
        if data["status"] == True:
            return True
        else:
            raise BaseException("V2:160 : Impossible d'envoyer le message au salon de discussion.")
        """
    
    @_wrapper
    def apiSyncroTextRoom(self) -> list:
        """Future api pour restorer les messages manquants"""
        self._send({"type": "syncro room@chat"})
        data = self._recv()
        if data["status"] == True:
            return True
        else:
            raise BaseException("V2:171 : Impossible de synchroniser le salon de discussion.")
    
    @_wrapper
    def apiRegister(self, username: str, password: str) -> bool:
        self._send({"type": "register", "Username": username, "Password": password})
        data = self._recv()
        if data.get("status") == True:
            return True
        elif data.get("status") == "already_exists":
            print("Ce username est deja utilisé.")
            return False
        else:
            raise BaseException(f"V2:152 : {data.get('status')}")

    @_wrapper
    def apiLogin(self, username: str, password: str) -> bool:
        self._send({"type": "login", "Username": username, "Password": password})
        data = self._recv()
        if data.get("status") == True:
            return True
        elif data.get("status") == "404user":
            print("Compte introuvable")
            return False
        elif data.get("status") == "403user":
            print("Mot de passe invalide.")
            return False
        else:
            raise BaseException(f"V2:164 : {data.get('status')}")
    
    @_wrapper
    def apiConnectAudioRoom(self, ID) -> bool:
        self._send({"type": "CONNECT room@audio", "roomID": ID})
        if self._recv()["data"]["status"] == True:
            return True
        else:
            return False
    
    def apiSendAudioChunk(self, chunk: bytes, RATE: int, CHANNELS: int, FRAME: int):
        self._send({"type": "AUDIO chunk",
                    "RATE": RATE, "CHANNELS": CHANNELS,
                    "FRAME": FRAME, "chunk": chunk})

if __name__ == "__main__":
    import pyaudio

    def codeThread():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", 12347))
            s.listen()
            conn, addr = s.accept()
            user = v2(conn)
            while True:
                data = user.recv()
                print(f"Received: {data}")
                #user.send({"status": True})
    
    thread = threading.Thread(target=codeThread, daemon=True)
    thread.start()
    time.sleep(2)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 12347))
    session = v2(sock, maxSizeBuffer=1 * 1024)
    for i in range(80000):
        session.send({"message": f"Hello {i}"})
        #session.apiPing()
    time.sleep(5)