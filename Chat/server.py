import socket
import threading

HEADER = 64
PORT = 5050
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "DISCONNECT"
SERVER = socket.gethostbyname(socket.gethostname())
ADDR = (SERVER, PORT)

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(ADDR)

clients = []  

def broadcast(message, _conn=None):
    for client in clients:
        if client != _conn:
            try:
                client.send(message.encode(FORMAT))
            except:
                clients.remove(client)

def handle_client(conn, addr):
    print(f"[NEW CONNECTION] connected to {addr}")
    clients.append(conn)
    connected = True
    while connected:
        try:
            msg_length = conn.recv(HEADER).decode(FORMAT)
            if msg_length:
                msg_length = int(msg_length)
                msg = conn.recv(msg_length).decode(FORMAT)
                if msg == DISCONNECT_MESSAGE:
                    connected = False
                else:
                    print(f"[{addr}] {msg}")
                    broadcast(f"[{addr}] {msg}", conn)
                    conn.send("Message sent to group.".encode(FORMAT))
        except:
            break
    conn.close()
    clients.remove(conn)
    print(f"[DISCONNECTED] {addr} disconnected.")

def server_chat():
    while True:
        msg = input()
        if msg.lower() == "exit":
            print("Shutting down server...")
            break
        broadcast(f"[SERVER] {msg}")

def start():
    server.listen()
    print(f"[LISTENING] server is listening on {SERVER}")
    threading.Thread(target=server_chat, daemon=True).start()
    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()
        print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")

print(f"[STARTING] server is starting...")
start()
