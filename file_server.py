import socket
import threading
import os
import shutil
import json
import hashlib
from PyQt5.QtCore import pyqtSignal, QObject

class ServerSignals(QObject):
    update_log = pyqtSignal(str)

class FileServerManager:
    def __init__(self):
        self.PORT = 8080
        self.SERVER =  "192.168.234.191"
        self.BUFFER_SIZE = 4096
        self.SEPARATOR = "<SEPARATOR>"
        
        self.signals = ServerSignals()
        self.files_dir = "./shared_files"
        self.chunk_dir = "./chunks"
        self.metadata_dir = "./metadata"
        self.server_running = False
        self.server_thread = None
        
        for directory in [self.files_dir, self.chunk_dir, self.metadata_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
    
    def add_file(self, file_path):
        if not file_path:
            return False
            
        try:
            file_name = os.path.basename(file_path)
            destination = os.path.join(self.files_dir, file_name)
            
            shutil.copy2(file_path, destination)
            self.signals.update_log.emit(f"Added file: {file_name}")
            return True
        except Exception as e:
            self.signals.update_log.emit(f"Failed to add file: {str(e)}")
            return False
    
    def add_file_reference(self, filename):
        try:
            file_hash = self.get_file_hash(filename)
            metadata_path = os.path.join(self.metadata_dir, f"{file_hash}.json")
            
            if not os.path.exists(metadata_path):
                self.signals.update_log.emit(f"No metadata found for file: {filename}")
                return False
            
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            my_ip = socket.gethostbyname(socket.gethostname())
            if 'peers' not in metadata:
                metadata['peers'] = [my_ip]
            elif my_ip not in metadata['peers']:
                metadata['peers'].append(my_ip)
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f)
            
            self.signals.update_log.emit(f"Added file reference: {filename}")
            return True
            
        except Exception as e:
            self.signals.update_log.emit(f"Failed to add file reference: {str(e)}")
            return False
    
    def get_file_hash(self, filename):
        return hashlib.md5(filename.encode()).hexdigest()
    
    def start_server(self):
        if self.server_running:
            return
            
        self.server_running = True
        self.server_thread = threading.Thread(target=self.run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        self.signals.update_log.emit(f"Server started on {self.SERVER}:{self.PORT}")
    
    def stop_server(self):
        self.server_running = False
        self.signals.update_log.emit("Server stopped")
    
    def run_server(self):
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind((self.SERVER, self.PORT))
            server.listen(5)
            self.signals.update_log.emit(f"Server is listening on {self.SERVER}:{self.PORT}")
            
            while self.server_running:
                try:
                    server.settimeout(1.0)
                    client_socket, addr = server.accept()
                    thread = threading.Thread(target=self.handle_client, args=(client_socket, addr))
                    thread.daemon = True
                    thread.start()
                    self.signals.update_log.emit(f"New connection from {addr[0]}:{addr[1]}")
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.server_running:  
                        self.signals.update_log.emit(f"Error: {str(e)}")
                    break
        except Exception as e:
            self.signals.update_log.emit(f"Server error: {str(e)}")
        finally:
            server.close()
    
    def handle_client(self, client_socket, addr):
        try:
            command = client_socket.recv(1024).decode()
            
            if command.startswith("LIST"):
                files = []
                if os.path.exists(self.metadata_dir):
                    for metadata_file in os.listdir(self.metadata_dir):
                        if metadata_file.endswith('.json'):
                            try:
                                with open(os.path.join(self.metadata_dir, metadata_file), 'r') as f:
                                    metadata = json.load(f)
                                    files.append(metadata['filename'])
                            except:
                                pass

                if os.path.exists(self.files_dir):
                    for file in os.listdir(self.files_dir):
                        if os.path.isfile(os.path.join(self.files_dir, file)) and file not in files:
                            files.append(file)
                
                response = self.SEPARATOR.join(files) if files else "NO_FILES"
                client_socket.send(response.encode())
                self.signals.update_log.emit(f"Sent file list to {addr[0]}")
                
            elif command.startswith("GET"):
                _, filename = command.split(self.SEPARATOR)
                filepath = os.path.join(self.files_dir, filename)
                
                if os.path.exists(filepath):
                    filesize = os.path.getsize(filepath)
                    client_socket.send(f"{filename}{self.SEPARATOR}{filesize}".encode())
                    
                    client_socket.recv(1024)
                    
                    with open(filepath, "rb") as f:
                        while True:
                            bytes_read = f.read(self.BUFFER_SIZE)
                            if not bytes_read:
                                break
                            client_socket.sendall(bytes_read)
                            
                    self.signals.update_log.emit(f"Sent file {filename} to {addr[0]}")
                else:
                    client_socket.send(f"ERROR{self.SEPARATOR}File not found".encode())
                    self.signals.update_log.emit(f"File {filename} not found")
            
            elif command.startswith("GET_CHUNK"):
                _, filename, chunk_index = command.split(self.SEPARATOR)
                chunk_index = int(chunk_index)

                file_hash = self.get_file_hash(filename)
                chunk_dir = os.path.join(self.chunk_dir, file_hash)
                
                if not os.path.exists(chunk_dir):
                    client_socket.send(f"ERROR{self.SEPARATOR}Chunk directory not found".encode())
                    return
                
                chunk_file = None
                for file in os.listdir(chunk_dir):
                    if file.startswith(f"{chunk_index}_"):
                        chunk_file = file
                        break
                
                if not chunk_file:
                    client_socket.send(f"ERROR{self.SEPARATOR}Chunk not found".encode())
                    return
                
                chunk_path = os.path.join(chunk_dir, chunk_file)
                chunk_size = os.path.getsize(chunk_path)
                
                client_socket.send(f"CHUNK{self.SEPARATOR}{chunk_size}".encode())
                
                client_socket.recv(1024)
               
                with open(chunk_path, "rb") as f:
                    while True:
                        bytes_read = f.read(self.BUFFER_SIZE)
                        if not bytes_read:
                            break
                        client_socket.sendall(bytes_read)
                
                self.signals.update_log.emit(f"Sent chunk {chunk_index} of {filename} to {addr[0]}")
            
            elif command.startswith("GET_METADATA"):
                _, filename = command.split(self.SEPARATOR)
                file_hash = self.get_file_hash(filename)
                metadata_path = os.path.join(self.metadata_dir, f"{file_hash}.json")
                
                if not os.path.exists(metadata_path):
                    client_socket.send(f"ERROR{self.SEPARATOR}Metadata not found".encode())
                    return
                
                with open(metadata_path, "r") as f:
                    metadata_json = f.read()
                
                client_socket.send(str(len(metadata_json.encode())).encode())
                
                client_socket.recv(1024)
                
                client_socket.sendall(metadata_json.encode())
                
                self.signals.update_log.emit(f"Sent metadata for {filename} to {addr[0]}")
                    
        except Exception as e:
            self.signals.update_log.emit(f"Error handling client {addr}: {str(e)}")
        finally:
            client_socket.close()
    
    def set_server_address(self, ip, port=None):
        self.SERVER = ip
        if port:
            self.PORT = port

            