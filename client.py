import os
import sys
import ssl
import time
import queue
import socks
import socket
import anstrip
import argparse
import traceback
import threading
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import button_dialog
from prompt_toolkit.shortcuts import radiolist_dialog
from prompt_toolkit.validation import Validator, ValidationError

from textual.app import App, ComposeResult
from textual.widgets import Input, Log

from src.VERSION import VERSION
from src.protocol import client as life
from src.notification import notification

class errors:
    class ClientIncompatibleServerVersion(Exception): pass

def viewSalonMenu(user: life):
    salon = user.sendwait({"type": "GET-group-LIST"})["data"]
    #data = ["Chat#1", ","] * 100
    values = [(item["id"], f"{item['name']}@{item['type']}") for item in salon]
    values = [(None, "❌ Quitter")] + values
    
    result = radiolist_dialog(
        title='Liste des salons',
        text='Salon',
        values=values,
    ).run()
    if result == None:
        return None, None
    name = next((item[1] for item in values if item[0] == result), None)
    return result, name

    
    #print("Vous avez choisi :", result)
    user.send({"type": "CONNECT room@chat", "roomID": result})
    #print(f"table : {user.table}")
    ini = user.sendwait({"type": "syncro room@chat"})
    #print(ini)
    #print(f"table after : {user.table}")

def viewSalon(user, salonName: str, notificationS: notification, cleintLocal):
    def data(user: life, event: threading.Event):
        try:
            while not event.is_set():
                try:
                    #yield str(user.QueueOUT.qsize())
                    if not user.status():
                        yield str(f"\x1b[93m\x1b[40mSystème : Vous avez été déconnecté.\x1b[0m\n")
                        return ''
                    entry = user.QueueOUT.get(timeout=1)
                    #yield str(entry)
                    #if isinstance(entry, dict):
                    #    yield "dict : OK\n"
                    if isinstance(entry["data"], dict) and entry.get("data") and entry["data"].get("type") == "chunk room@chat":
                        d = dict(entry["data"])
                        yield str(f"[{anstrip.strip(d['by'])}] {anstrip.strip(d['message'])}\n")
                    else:
                        #yield "vide\n"
                        user.QueueOUT.put(entry)
                except queue.Empty:
                    #yield "vide\n"
                    pass
        except Exception as e:
            yield traceback.format_exc()
            raise

    class Chat(App):
        def compose(self) -> ComposeResult:
            yield Log(id="chat")
            yield Input(placeholder=f"> Message ({salonName})", id="input")
    
        def on_mount(self) -> None:
            self.query_one("#input", Input).focus()
            def stream(user, data_event):
                for message in data(user, data_event):
                    if f"@{cleintLocal['username']}" in message:
                        notificationS.send(message=message, title=f"Korixa - {salonName}")
                    self.call_from_thread(
                        self.query_one("#chat", Log).write,
                        message
                    )
            self.data_event = threading.Event()
            self.data_thread = threading.Thread(target=stream, args=(user, self.data_event), daemon=True)
            self.data_thread.start()
    
        def on_input_submitted(self, event: Input.Submitted):
            chat = self.query_one("#chat", Log)
            if event.value:
                if not event.value[0] == "/":
                    user.send({"type": "send-message", "message": event.value})
                else:
                    commande = event.value[1:]
                    if commande == "help":
                        chat.write(f"Helper\n")
            event.input.value = ""
        def on_unmount(self) -> None:
            self.data_event.set()
            self.data_thread.join()
    Chat().run()
    return True


def main():
    parser = argparse.ArgumentParser(description="Main")
    parser.add_argument("--server", type=str, required=True, help="Adresse du serveur ( ex : 127.0.0.1:1234 )")
    parser.add_argument("--proxy", type=str, default=None, help="Adresse du proxy ( ex : 127.0.0.1:9050 )")
    parser.add_argument("--ssl", action="store_true", help="Active le chiffrement TLS. Nécessaire si le serveur exige TLS.")
    parser.add_argument("--debug", action="store_true", help="Mode verbeux")
    parser.add_argument("--no-notify", action="store_true", help="Désactive complètement l’envoi de notifications." )

    
    args = parser.parse_args()

    notificationS = notification(enable=not args.no_notify)
    notificationS.send(message="message", title=f"Korixa - salonName")
    
    def keepalive(user: life, event : threading.Event):
        start_time = time.monotonic()
        while not event.is_set():
            if time.monotonic() - start_time > 5:
                start_time = time.monotonic()
                with user.lock:
                    user.send({"type": "ping"})
            else:
                time.sleep(1)
    
    try:
        HOST, PORT = args.server.split(":")
        PORT = int(PORT)

        if args.proxy:
            proxyHOST, proxyPORT = args.proxy.split(":")
            proxyPORT = int(proxyPORT)
    except ValueError:
        raise ValueError("arg : Le format doit être host:port")
    
    user = None
    client = None
    clientLocal = {}
    event_keepalive = None
    thread_keepalive = None
    try:
        #client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #client.connect((HOST, int(PORT)))
        if args.proxy:
            client = socks.socksocket()
            client.set_proxy(socks.SOCKS5, proxyHOST, proxyPORT)
            client.connect((HOST, PORT))
        else:
            client = socket.create_connection((HOST, PORT))
        client.settimeout(4)

        if args.ssl:
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            context.load_verify_locations(os.path.join(os.path.dirname(__file__), "authority.pem"))
            client = context.wrap_socket(client, server_hostname=HOST)
        
        client.settimeout(None)

        client.sendall(b"PING")
        if client.recv(len(b"PONG")) == b"PONG":
            user = life(sock=client, QueueIN=queue.Queue(), QueueOUT=queue.Queue(), boot=True, debug=args.debug, type="client")
            if user.sendwait({"type": "version"})["data"]["version"] != VERSION.VERSION:
                raise errors.ClientIncompatibleServerVersion()

            event_keepalive = threading.Event()
            thread_keepalive = threading.Thread(target=keepalive, args=(user,event_keepalive), daemon=True)
            thread_keepalive.start()

            result = button_dialog(
                title='Bienvenue',
                text='Que voulez-vous faire ?',
                buttons=[
                    ('Login', 'login'),
                    ('Register', 'register'),
                ],
            ).run()
            username = input("Username >")
            clientLocal["username"] = username
            password = prompt("Password >", is_password=True)

            data = user.sendwait({"type": result, "Username": username, "Password": password})["data"]

            if data.get("status") == True:
                print("Connecté !")
            elif data.get("status") == "already_exists":
                print("Ce username est deja utilisé.")
                sys.exit(65)
            elif data.get("status") == "404user":
                print("Compte introuvable")
                sys.exit(68)
            elif data.get("status") == "403user":
                print("Mot de passe invalide.")
                sys.exit(153)
            else:
                print(data)
                print(f"error 70: {data.get("status")}")
                sys.exit()
            
            while True:
                ID, name = viewSalonMenu(user)
                if ID:
                    user.send({"type": "CONNECT room@chat", "roomID": ID})
                    ini = user.sendwait({"type": "syncro room@chat"})
                    viewSalon(user, name, notificationS, clientLocal)
                    user.send({"type": "CONNECT room@chat", "roomID": None})
                else:
                    sys.exit()
    except KeyboardInterrupt:
        print("exit...")
    except ConnectionResetError as e:
        print("Le serveur n’a plus de capacité pour vous accueillir.")
        print(f"error server : {e}")
    except errors.ClientIncompatibleServerVersion:
        print("Vous n'avez pas la même version que le serveur.")
    except Exception as e:
        print(e)
    finally:
        try:
            if event_keepalive:
                event_keepalive.set()
            if thread_keepalive:
                thread_keepalive.join()
            if user:
                user.stop()
            if client:
                client.close()
        except Exception as e:
            print(e)
if __name__ == "__main__":
    main()