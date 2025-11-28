import copy
import time
import queue
import socket
import secrets
import msgpack
import traceback
import threading
from typing import Literal
class client:
    def __init__(self, sock: socket.socket, QueueIN: queue.Queue = queue.Queue(10),
                 QueueOUT: queue.Queue = queue.Queue(), boot: bool = False, debug = False,
                 type: Literal["client", "server"] = None, kbps: int = 1024, unpacker_buffer_size: int = 40 * 1024 * 1024):
        self.sock = sock
        self.lock = threading.RLock()
        self.debug = debug
        self.table = {}
        self.tableLock = threading.RLock()
        self.lockSock = threading.RLock()
        self.QueueIN = QueueIN
        self.QueueOUT = QueueOUT
        self.unpacker = msgpack.Unpacker(max_buffer_size=unpacker_buffer_size)
        self.stop_event = threading.Event()
        self.Boot = boot
        self.type = type
        self.total_recv = 0
        self._recv_bytes_read = 0
        self._recv_start_time = time.monotonic()
        self.max_bps = kbps * 1000
        if self.Boot:
            self.boot()
    
    def send(self, data: dict, _returne: bool = False, ID: str = None) -> str:
        defautID = ID
        if defautID == None:
            ID = secrets.token_hex(8)
        else:
            ID = defautID
        data = {"data": data, "id": ID, "timeNS": time.perf_counter_ns()}
        if _returne or defautID:
            if self.type == "client":
                data["returne"] = True
                with self.tableLock:
                    self.table[ID] = {"event": threading.Event(), "result": None}
            else:
                data["returne"] = True
        self.QueueIN.put(data)
        return ID
    
    def sendwait(self, data: dict, timeout: float = 20) -> bytes:
        ID = self.send(data, _returne=True)
        with self.tableLock:
            event = self.table[ID]["event"]
        if event.wait(timeout):
            with self.tableLock:
                result = copy.deepcopy(self.table[ID]["result"])
                del self.table[ID]
            return result
        else:
            return None
    
    def _recv(self):
        try:
            while not self.stop_event.is_set():
                data = self.sock.recv(2048)
                if not data:
                    return False
                    #raise RuntimeError("PKG socket : ERROR : data = 0")
                
                self._recv_bytes_read += len(data)
                self.unpacker.feed(data)
    
                for obj in self.unpacker:
                    obj = dict(obj)
                    if self.debug:
                        #print(f"Time NS : {time.perf_counter_ns() - obj["timeNS"]}")
                        print(f"Lib : recu : {obj}")
                    #self.QueueOUT.put(obj)
                    if self.type == "client":
                        if obj.get("returne"): # and obj.get("returne")
                            with self.tableLock:
                                if obj["id"] in self.table:
                                    self.table[obj["id"]]["result"] = obj
                                    self.table[obj["id"]]["event"].set()
                        else:
                            self.QueueOUT.put(obj)
                    else:
                        self.QueueOUT.put(obj)
                
                elapsed = time.monotonic() - self._recv_start_time
                if elapsed > 0:
                    current_speed = self._recv_bytes_read / elapsed
                    if current_speed > self.max_bps:
                        time.sleep((self._recv_bytes_read / self.max_bps) - elapsed)
                
                if elapsed >= 1:
                    self._recv_start_time = time.monotonic()
                    self._recv_bytes_read = 0
        except Exception as e:
            print(e)
            print(traceback.format_exc())
    
    
    def _send(self):
        try:
            while not self.stop_event.is_set():
                try:
                    data = self.QueueIN.get(timeout=1)
                    if data != None:
                        if self.debug:
                            print(f"Lib : envoyer : {data}")
                        with self.lockSock:
                            self.sock.sendall(msgpack.packb(data))
                except queue.Empty:
                    pass
        except Exception as e:
            print(e)
            print(traceback.format_exc())
    #def _sendWrapper(self):

    
    def stop(self):
        self.stop_event.set()
        try:
            self.QueueIN.put_nowait(None)
        except Exception:
            pass
        if self.Boot:
            self.thread_send.join()
            self.thread_recv.join()
    
    def status(self):
        if self.Boot:
            if not self.thread_send.is_alive():
                print("Thread : _send : DEAD")
                data = False
            elif not self.thread_recv.is_alive():
                print("Thread : _recv : DEAD")
                data = False
            else:
                data = True
        return data
    
    def boot(self):
        self.thread_send = threading.Thread(target=self._send, daemon=True)
        self.thread_send.start()

        self.thread_recv = threading.Thread(target=self._recv, daemon=True)
        self.thread_recv.start()