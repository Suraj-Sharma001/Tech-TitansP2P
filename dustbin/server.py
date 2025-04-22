# server.py - Server implementation for P2P file sharing
import socket
import threading
import os
import json
import time
from pathlib import Path

class Server:
    def __init__(self, host='0.0.0.0', port=5051):
        self.HOST = host
        self.PORT = port
        self.ADDR = (self.HOST, self.PORT)
        self.HEADER = 64
        self.FORMAT = 'utf-8'
        self.DISCONNECT_MESSAGE = "DISCONNECT"
        
        # Create storage directory
        self.STORAGE_DIR = Path("shared_files")
        self.STORAGE_DIR.mkdir(exist_ok=True)
        
        # Keep track of connected clients and available files
        self.clients = []
        self.files = {}  # {filename: {size, owner, path}}
        
        # Set up server socket
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(self.ADDR)
    
    def start(self):
        print(f"[SERVER] Starting on {self.HOST}:{self.PORT}")
        self.server.listen()
        print(f"[SERVER] Listening for connections...")
        
        while True:
            conn, addr = self.server.accept()
            thread = threading.Thread(target=self.handle_client, args=(conn, addr))
            thread.daemon = True
            thread.start()
            print(f"[SERVER] Active connections: {threading.active_count() - 1}")
    
    def handle_client(self, conn, addr):
        print(f"[SERVER] New connection: {addr}")
        self.clients.append(conn)
        
        # Send list of available files
        self.send_file_list(conn)
        
        connected = True
        while connected:
            try:
                msg_length = conn.recv(self.HEADER).decode(self.FORMAT)
                if msg_length:
                    msg_length = int(msg_length)
                    msg = conn.recv(msg_length).decode(self.FORMAT)
                    
                    if msg == self.DISCONNECT_MESSAGE:
                        connected = False
                    
                    if msg.startswith("CMD:"):
                        self.handle_command(conn, msg[4:])
                    else:
                        # Regular chat message - broadcast to other clients
                        self.broadcast(msg, conn)
            except Exception as e:
                print(f"[ERROR] {e}")
                break
        
        print(f"[SERVER] Connection closed: {addr}")
        self.clients.remove(conn)
        conn.close()
    
    def broadcast(self, message, sender_conn=None):
        for client in self.clients:
            if client != sender_conn:  # Don't send back to sender
                try:
                    self.send_message(client, message)
                except:
                    pass
    
    def send_message(self, conn, msg):
        message = msg.encode(self.FORMAT)
        msg_length = len(message)
        send_length = str(msg_length).encode(self.FORMAT)
        send_length += b' ' * (self.HEADER - len(send_length))
        conn.send(send_length)
        conn.send(message)
    
    def handle_command(self, conn, cmd_str):
        try:
            cmd_data = json.loads(cmd_str)
            cmd = cmd_data.get("cmd")
            
            if cmd == "UPLOAD_REQUEST":
                self.handle_upload_request(conn, cmd_data)
            elif cmd == "DOWNLOAD_REQUEST":
                self.handle_download_request(conn, cmd_data)
            elif cmd == "LIST_FILES":
                self.send_file_list(conn)
        except Exception as e:
            print(f"[ERROR] Command handling error: {e}")
    
    def handle_upload_request(self, conn, data):
        filename = data.get("filename")
        filesize = data.get("filesize")
        
        # Inform client upload can start
        self.send_message(conn, json.dumps({"cmd": "UPLOAD_APPROVED"}))
        
        # Receive file
        filepath = self.STORAGE_DIR / filename
        received = 0
        with open(filepath, "wb") as f:
            while received < filesize:
                bytes_to_receive = min(4096, filesize - received)
                data = conn.recv(bytes_to_receive)
                if not data:
                    break
                f.write(data)
                received += len(data)
        
        # Add to file list
        self.files[filename] = {
            "size": filesize,
            "path": str(filepath),
            "owner": conn
        }
        
        # Send success message
        self.send_message(conn, json.dumps({"cmd": "UPLOAD_COMPLETE", "filename": filename}))
        
        # Broadcast file list update to all clients
        self.broadcast_file_list()
    
    def handle_download_request(self, conn, data):
        filename = data.get("filename")
        
        if filename in self.files:
            filepath = self.files[filename]["path"]
            filesize = os.path.getsize(filepath)
            
            # Send approval with filesize
            self.send_message(conn, json.dumps({
                "cmd": "DOWNLOAD_APPROVED", 
                "filename": filename,
                "filesize": filesize
            }))
            
            # Send file
            with open(filepath, "rb") as f:
                while True:
                    bytes_read = f.read(4096)
                    if not bytes_read:
                        break
                    conn.sendall(bytes_read)
            
            # Give client time to process
            time.sleep(0.5)
            self.send_message(conn, json.dumps({"cmd": "DOWNLOAD_COMPLETE", "filename": filename}))
        else:
            # File not found
            self.send_message(conn, json.dumps({"cmd": "ERROR", "message": "File not found"}))
    
    def send_file_list(self, conn):
        file_list = list(self.files.keys())
        self.send_message(conn, json.dumps({
            "cmd": "FILE_LIST",
            "files": file_list
        }))
    
    def broadcast_file_list(self):
        file_list = list(self.files.keys())
        for client in self.clients:
            try:
                self.send_message(client, json.dumps({
                    "cmd": "FILE_LIST",
                    "files": file_list
                }))
            except:
                pass

# start.py - Simple wrapper to start the server
def start():
    server = Server()
    server.start()

if __name__ == "__main__":
    start()