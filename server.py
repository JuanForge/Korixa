import os
import ssl
import json
import time
import queue
import socket
import orjson
import argparse
import traceback
import threading

from tqdm import tqdm
from ssl import SSLContext

from src.db import db as dbimport
from src.VERSION import VERSION
from src.protocol import client as life
from src.protocolV2 import v2 as lifeV2

def send_message(clientLocal, tableChat: dict, tableChatLock, message: str, by: str = None):
    if not by:
        by = clientLocal["username"]
    with tableChatLock:
        for key, value in tableChat[clientLocal["room@chat"]]["userConnected"].items():
            key: lifeV2
            value: dict
            try:
                key.send({"type": "chunk room@chat", "message": message, "by": by}) # {"type": "chunk room@chat", "message": "Bonjour"}
            except Exception as e:
                print(f"29 : Error send message by {by} : {e}")

def handle_client(client: socket.socket, addr, event: threading.Event,
                  debug: bool, db: dict, dbLock: threading.Lock, tableChat: dict,
                  tableChatLock: threading.RLock, contextssl: SSLContext, max_rate,
                  unpacker_buffer_size): # msgpack
    #user = None
    userV2 = None
    clientLocal = {"connected": False}
    try:
        if contextssl:
            client = contextssl.wrap_socket(client, server_side=True)
        
        if debug:
            print(f"Connexion de {addr}")
        
        client.settimeout(20)
        
        if client.recv(32) == b"PING":
            client.sendall(b"PONG")
        
        #user = life(sock=client, QueueIN=queue.Queue(), QueueOUT=queue.Queue(), boot=True, debug=debug, type="server", kbps=max_rate, unpacker_buffer_size=unpacker_buffer_size)
        userV2 = lifeV2(sock=client)

        while not event.is_set():
            data: dict = userV2.recv()

            #returne = data.get("returne", None)
            #ID = data.get("id", None)
            
            if data["type"] == "ping":
                # userV2.send({"status": True})
                continue
            
            elif data["type"] == "register":
                with dbLock:
                    if not str(data["Username"]) in db["user"]:
                        db["user"][str(data["Username"])] = {"Password": str(data["Password"]),
                                                             "roles": []}
                        clientLocal["connected"] = True
                        clientLocal["username"] = str(data["Username"])
                        userV2.send({"status": True})
                    else:
                        userV2.send({"status": "already_exists"})
            
            elif data["type"] == "login":
                with dbLock:
                    if str(data["Username"]) in db["user"]:
                        if db["user"][str(data["Username"])]["Password"] == str(data["Password"]):
                            clientLocal["connected"] = True
                            clientLocal["username"] = str(data["Username"])
                            userV2.send({"status": True})
                        else:
                            userV2.send({"status": "403user"})
                    else:
                        userV2.send({"status": "404user"})
            
            elif data["type"] == "getVesrion":
                userV2.send({"version": VERSION.VERSION})
            
            elif data["type"] == "GET-group-LIST":
                if clientLocal["connected"]:
                    with dbLock:
                        userV2.send(db["salon"])
                else:
                    userV2.send({"status": False})
            
            elif data["type"] == "CONNECT room@chat":
                if clientLocal["connected"]:
                    with dbLock:
                        if data["roomID"] != None:
                            if any(salon["id"] == str(data["roomID"]) for salon in db["salon"]):
                                clientLocal["room@chat"] = str(data["roomID"])
                                with tableChatLock:
                                    tableChat[clientLocal["room@chat"]]["userConnected"][userV2] = {} # .append({"user": user})
                                
                                userV2.send({"status": True})

                                send_message(clientLocal, tableChat, tableChatLock,
                                             message=f"{clientLocal['username']} nous a rejoint.", by="System#0")
                        else:
                            with tableChatLock:
                                del tableChat[clientLocal["room@chat"]]["userConnected"][userV2]
                            
                            userV2.send({"status": True})

                            send_message(clientLocal, tableChat, tableChatLock,
                                    message=f"{clientLocal['username']} nous a quittés.", by="System#0")
                            del clientLocal["room@chat"]
                else:
                    userV2.send({"status": False})
                
            elif data["type"] == "CONNECT room@audio":
                if clientLocal["connected"]:
                    with dbLock:
                        if data["roomID"] != None:
                            if any(salon["id"] == str(data["roomID"]) for salon in db["salon"]):
                                clientLocal["room@audio"] = str(data["roomID"])
                                with tableChatLock:
                                    tableChat[clientLocal["room@audio"]]["userConnected"][userV2] = {}
                                userV2.send({"status": True})
                        else:
                            with tableChatLock:
                                del tableChat[clientLocal["room@audio"]]["userConnected"][userV2]
                            userV2.send({"status": True})
                else:
                    userV2.send({"status": False})
            
            elif data["type"] == "AUDIO chunk":
                if clientLocal["connected"]:
                    with tableChatLock:
                        for key, value in tableChat[clientLocal["room@audio"]]["userConnected"].items():
                            key: lifeV2
                            value: dict
                            print(f"{userV2} != {key}")
                            if userV2 != key:
                                try:
                                    key.send({"type": "AUDIO chunk", "username": clientLocal["username"],
                                              "chunk": data["chunk"], "rate": data["RATE"], "frame": data["FRAME"]})
                                except Exception as e:
                                    print(f"Error sending audio chunk: {e}")
                else:
                    pass

            elif data["type"] == "send-message":
                if clientLocal["connected"]:
                    send_message(clientLocal=clientLocal,tableChat=tableChat,
                                 tableChatLock=tableChatLock, message=str(data["message"]))
                    #userV2.send({"status": True})
                else:
                    #userV2.send({"status": False})
                    pass
            
            elif data["type"] == "syncro room@chat":
                if clientLocal["connected"]:
                    userV2.send({"status": True})
                else:
                    userV2.send({"status": False})
            else:
                raise BaseException(f"Type inconnu : {data['type']}")
                
    except Exception as e:
        print(e)
        print(traceback.format_exc())
    finally:
        try:
            if clientLocal.get("room@chat"):
                send_message(clientLocal, tableChat, tableChatLock,
                             message=f"{clientLocal['username']} nous a quittés.", by="System#0")
                with tableChatLock:
                    tableChat[clientLocal["room@chat"]]["userConnected"].pop(userV2, None)
            if debug:
                print(f"exit for the client : {addr}...")
            
            if clientLocal.get("room@audio"):
                with tableChatLock:
                    tableChat[clientLocal["room@audio"]]["userConnected"].pop(userV2, None)

            try:
                client.close()
            except:
                pass

            if debug:
                print(f"exit for the client : {addr} : OK")
        except Exception as e:
            print(f"Internal error : {e}")
            print(traceback.format_exc())
            os._exit(116)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Server")
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Adresse IP ou hostname du serveur."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=12347,
        help="Port TCP sur lequel le serveur écoute."
    )
    parser.add_argument("--max-rooms", type=int, default=100,help="Nombre maximal de personnes dans un même salon.")
    parser.add_argument("--max-connections", type=int, default=4, help="Nombre maximum de clients connectés simultanément.")
    parser.add_argument("--max-rate", type=int, default=768, help="Débit entrant maximal de chaque client en kbps (kilobits par seconde).")
    parser.add_argument("--unpacker-buffer-size", type=int, default=65536, help="Taille maximale du buffer MessagePack de chaque client (en octets, 40_000_000).")
    parser.add_argument("--ssl", action="store_true", help="Active le chiffrement TLS.")
    parser.add_argument("--tls13", action="store_true", help="Forcer l’utilisation de TLS 1.3 uniquement (nécessite --ssl).")
    parser.add_argument("--debug", action="store_true", help="Mode verbeux.")
    args = parser.parse_args()

    if args.ssl:
        contextssl = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        contextssl.load_cert_chain(certfile="server.crt", keyfile="server.key")
        if args.tls13:
            contextssl.minimum_version = ssl.TLSVersion.TLSv1_3
            contextssl.maximum_version = ssl.TLSVersion.TLSv1_3
    else:
        print("\x1b[93m Avertissement : SSL/TLS non activé. Les connexions sont en clair.\n Avertissement : Recommandé : activer SSL/TLS pour sécuriser le trafic réseau.\x1b[0m\n")
        contextssl = None
    
    print("Load DB...")
    if not os.path.isfile("db.json"):
        with open("db.json", "w") as f:
            f.write(json.dumps(dbimport().db, indent=4))
    with open("db.json", "r") as f:
        db = json.loads(f.read())
    dbLock = threading.RLock()


    print("ini table@chat...")
    tableChat = {}
    tableChatLock = threading.RLock()
    for salon in db["salon"]:
        tableChat[salon["id"]] = {"userConnected": {}, "log": []}

    print(f"Serveur : {args.host}:{args.port}")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            with tqdm(total=args.max_connections, desc="Clients", dynamic_ncols=True, leave=True) as bar:
                bar.n = 0
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((args.host, args.port))
                s.listen(10)
                s.settimeout(5)
                threads = []
                try:
                  event = threading.Event()
                  while True:
                    try:
                        conn, addr = s.accept()
                        if len(threads)+1 <= (args.max_connections):
                            thread = threading.Thread(target=handle_client, args=(conn, addr, event, args.debug, db, dbLock,
                                                                                  tableChat, tableChatLock, contextssl, args.max_rate,
                                                                                  args.unpacker_buffer_size), daemon=True)
                            thread.start()
                            threads.append(thread)
                        else:
                            conn.close()
                    except socket.timeout:
                        pass
                    for i in threads:
                        if not i.is_alive():
                            i.join()
                            threads.remove(i)
                    bar.n = len(threads)
                    bar.refresh()
                except KeyboardInterrupt:
                    print("exit...")
                    event.set()
                    for thread in threads:
                        thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        with open("db.json", "w") as f:
            f.write(json.dumps(db, indent=4))
        print("Server stopped.")