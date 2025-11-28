import socket
import msgpack
class v2:
    def __init__(self, sock: socket.socket, unpacker_buffer_size: int = 1024 * 1024):
        self.sock = sock
        self.unpacker = msgpack.Unpacker(max_buffer_size=unpacker_buffer_size)
    
    def _send(self, data: dict):
        self.sock.sendall(msgpack.packb(data))
    
    def _recv(self):
        while True:
            data = self.sock.recv(4*1024)
            if not data:
                raise RuntimeError("PKG socket : ERROR : data size == 0")
            self.unpacker.feed(data)
            for obj in self.unpacker:
                return obj
    
    def apiConnectTextRoom(self, ID) -> bool:
        self._send({"type": "CONNECT room@chat", "roomID": ID})
        if self._recv()["data"]["status"] == True:
            return True
        else:
            return False

if __name__ == "__main__":
    session = v2()
    v2.apiConnectTextRoom()