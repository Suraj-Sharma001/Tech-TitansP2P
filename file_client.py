import socket
import os
import threading
from PyQt5.QtCore import QThread, pyqtSignal, QObject

class ClientSignals(QObject):
    progress_update = pyqtSignal(int)
    download_complete = pyqtSignal(str)
    error = pyqtSignal(str)

class DownloadWorker(QThread):
    def __init__(self, filename, server_ip, port, separator, buffer_size, signals):
        super().__init__()
        self.filename = filename
        self.server_ip = server_ip
        self.port = port
        self.separator = separator
        self.buffer_size = buffer_size
        self.signals = signals
        
    def run(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.server_ip, self.port))
            
            # Request file
            s.send(f"GET{self.separator}{self.filename}".encode())
            
            # Receive file info
            response = s.recv(self.buffer_size).decode()
            
            if response.startswith("ERROR"):
                self.signals.error.emit(response.split(self.separator)[1])
                s.close()
                return
                
            filename, filesize = response.split(self.separator)
            filesize = int(filesize)
            
            # Send ready signal
            s.send("READY".encode())
            
            # Create download directory if it doesn't exist
            download_dir = "./downloaded_files"
            if not os.path.exists(download_dir):
                os.makedirs(download_dir)
                
            # Receive file data
            filepath = os.path.join(download_dir, filename)
            received_bytes = 0
            
            with open(filepath, "wb") as f:
                while received_bytes < filesize:
                    bytes_read = s.recv(self.buffer_size)
                    if not bytes_read:
                        break
                        
                    f.write(bytes_read)
                    received_bytes += len(bytes_read)
                    
                    # Update progress
                    progress = int((received_bytes / filesize) * 100)
                    self.signals.progress_update.emit(progress)
                    
            s.close()
            self.signals.download_complete.emit(filepath)
            
        except Exception as e:
            self.signals.error.emit(str(e))

class FileClientManager:
    def __init__(self):
        self.SERVER_IP = "192.168.174.10"  # Default server IP
        self.PORT = 5000
        self.BUFFER_SIZE = 4096
        self.SEPARATOR = "<SEPARATOR>"
        
        self.signals = ClientSignals()
        self.download_worker = None
    
    def get_file_list(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.SERVER_IP, self.PORT))
            
            # Request file list
            s.send("LIST".encode())
            
            # Receive file list
            response = s.recv(self.BUFFER_SIZE).decode()
            s.close()
            
            if response == "NO_FILES":
                return []
                
            files = response.split(self.SEPARATOR)
            return files
            
        except Exception as e:
            return f"Connection error: {str(e)}"
    
    def download_file(self, filename):
        # Start download in separate thread
        self.download_worker = DownloadWorker(
            filename, 
            self.SERVER_IP, 
            self.PORT, 
            self.SEPARATOR, 
            self.BUFFER_SIZE,
            self.signals
        )
        self.download_worker.start()
    
    def set_server(self, ip, port=None):
        self.SERVER_IP = ip
        if port:
            self.PORT = port