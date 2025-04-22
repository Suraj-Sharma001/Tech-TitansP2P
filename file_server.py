import socket
import threading
import os
import shutil
from PyQt5.QtCore import pyqtSignal, QObject

class ServerSignals(QObject):
    update_log = pyqtSignal(str)

class FileServerManager:
    def __init__(self):
        self.PORT = 5050
        self.SERVER = "192.168.174.10"  # Default to localhost
        self.BUFFER_SIZE = 4096
        self.SEPARATOR = "<SEPARATOR>"
        
        self.signals = ServerSignals()
        self.files_dir = "./shared_files"
        self.server_running = False
        self.server_thread = None
        
        # Create the directory if it doesn't exist
        if not os.path.exists(self.files_dir):
            os.makedirs(self.files_dir)
    
    def add_file(self, file_path):
        if not file_path:
            return False
            
        try:
            file_name = os.path.basename(file_path)
            destination = os.path.join(self.files_dir, file_name)
            
            # Copy the file to shared directory
            shutil.copy2(file_path, destination)
            self.signals.update_log.emit(f"Added file: {file_name}")
            return True
        except Exception as e:
            self.signals.update_log.emit(f"Failed to add file: {str(e)}")
            return False
    
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

    def get_shared_files(self):
        """Return a list of files that are currently being shared by this server"""
        if not hasattr(self, 'shared_files'):
            self.shared_files = {}

        return list(self.shared_files.keys())
    
    def run_server(self):
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind((self.SERVER, self.PORT))
            server.listen(5)
            self.signals.update_log.emit(f"Server is listening on {self.SERVER}:{self.PORT}")
            
            while self.server_running:
                try:
                    server.settimeout(1.0)  # Check every second if server should still be running
                    client_socket, addr = server.accept()
                    thread = threading.Thread(target=self.handle_client, args=(client_socket, addr))
                    thread.daemon = True
                    thread.start()
                    self.signals.update_log.emit(f"New connection from {addr[0]}:{addr[1]}")
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.server_running:  # Only log if not intentionally stopping
                        self.signals.update_log.emit(f"Error: {str(e)}")
                    break
        except Exception as e:
            self.signals.update_log.emit(f"Server error: {str(e)}")
        finally:
            server.close()
    
    def handle_client(self, client_socket, addr):
        try:
            # Receive command
            command = client_socket.recv(1024).decode()
            
            if command.startswith("LIST"):
                # Send list of files
                files = os.listdir(self.files_dir)
                response = self.SEPARATOR.join(files) if files else "NO_FILES"
                client_socket.send(response.encode())
                self.signals.update_log.emit(f"Sent file list to {addr[0]}")
                
            elif command.startswith("GET"):
                # Send a file
                _, filename = command.split(self.SEPARATOR)
                filepath = os.path.join(self.files_dir, filename)
                
                if os.path.exists(filepath):
                    # Send file info
                    filesize = os.path.getsize(filepath)
                    client_socket.send(f"{filename}{self.SEPARATOR}{filesize}".encode())
                    
                    # Wait for client ready signal
                    client_socket.recv(1024)
                    
                    # Send file data
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
                    
        except Exception as e:
            self.signals.update_log.emit(f"Error handling client {addr}: {str(e)}")
        finally:
            client_socket.close()
    
    def set_server_address(self, ip, port=None):
        self.SERVER = ip
        if port:
            self.PORT = port