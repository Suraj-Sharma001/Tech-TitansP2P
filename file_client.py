# file_client.py
import socket
import os
import threading
import json
import hashlib
from PyQt5.QtCore import QThread, pyqtSignal, QObject

class ClientSignals(QObject):
    progress_update = pyqtSignal(int)
    download_complete = pyqtSignal(str)
    error = pyqtSignal(str)
    metadata_received = pyqtSignal(str)

class ChunkDownloadWorker(QThread):
    def __init__(self, peer_ip, filename, chunk_index, chunk_hash, output_dir, signals):
        super().__init__()
        self.peer_ip = peer_ip
        self.filename = filename
        self.chunk_index = chunk_index
        self.chunk_hash = chunk_hash
        self.output_dir = output_dir
        self.signals = signals
        self.port = 5050  # Default chunk transfer port
        self.separator = "<SEPARATOR>"
        self.buffer_size = 4096
        
    def run(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.peer_ip, self.port))
            
            # Request specific chunk
            s.send(f"GET_CHUNK{self.separator}{self.filename}{self.separator}{self.chunk_index}".encode())
            
            # Receive chunk info
            response = s.recv(self.buffer_size).decode()
            
            if response.startswith("ERROR"):
                self.signals.error.emit(response.split(self.separator)[1])
                s.close()
                return False
                
            _, chunk_size = response.split(self.separator)
            chunk_size = int(chunk_size)
            
            # Send ready signal
            s.send("READY".encode())
            
            # Receive chunk data
            chunk_filename = f"{self.chunk_index}_{self.chunk_hash}"
            chunk_path = os.path.join(self.output_dir, chunk_filename)
            received_bytes = 0
            
            with open(chunk_path, "wb") as f:
                while received_bytes < chunk_size:
                    bytes_read = s.recv(self.buffer_size)
                    if not bytes_read:
                        break
                        
                    f.write(bytes_read)
                    received_bytes += len(bytes_read)
                    
            s.close()
            
            # Verify integrity
            with open(chunk_path, "rb") as f:
                data = f.read()
                calculated_hash = hashlib.md5(data).hexdigest()
                
            if calculated_hash != self.chunk_hash:
                os.remove(chunk_path)  # Remove corrupted chunk
                return False
                
            return True
            
        except Exception as e:
            self.signals.error.emit(f"Chunk download error: {str(e)}")
            return False


class MetadataWorker(QThread):
    def __init__(self, peer_ip, filename, signals):
        super().__init__()
        self.peer_ip = peer_ip
        self.filename = filename
        self.signals = signals
        self.port = 5050
        self.separator = "<SEPARATOR>"
        self.buffer_size = 4096
        
    def run(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.peer_ip, self.port))
            
            # Request metadata
            s.send(f"GET_METADATA{self.separator}{self.filename}".encode())
            
            # Receive metadata
            response = s.recv(self.buffer_size).decode()
            
            if response.startswith("ERROR"):
                self.signals.error.emit(response.split(self.separator)[1])
                s.close()
                return
            
            metadata_size = int(response)
            s.send("READY".encode())
            
            metadata_json = ""
            received_bytes = 0
            
            while received_bytes < metadata_size:
                data = s.recv(self.buffer_size).decode()
                if not data:
                    break
                    
                metadata_json += data
                received_bytes += len(data.encode())
            
            s.close()
            
            # Save metadata
            metadata = json.loads(metadata_json)
            
            # Create metadata directory if it doesn't exist
            metadata_dir = "./metadata"
            if not os.path.exists(metadata_dir):
                os.makedirs(metadata_dir)
                
            file_hash = self.get_file_hash(metadata['filename'])
            metadata_path = os.path.join(metadata_dir, f"{file_hash}.json")
            
            with open(metadata_path, "w") as f:
                json.dump(metadata, f)
                
            self.signals.metadata_received.emit(metadata['filename'])
            
        except Exception as e:
            self.signals.error.emit(f"Metadata download error: {str(e)}")
    
    def get_file_hash(self, filename):
        """Create a unique identifier for a file"""
        return hashlib.md5(filename.encode()).hexdigest()


# Continuing from previous FileClientManager class

class FileClientManager:
    def __init__(self):
        self.SERVER_IP = "172.21.12.181"  # Default server IP
        self.PORT = 8000
        self.BUFFER_SIZE = 4096
        self.SEPARATOR = "<SEPARATOR>"
        
        self.signals = ClientSignals()
        self.download_worker = None
        self.metadata_workers = []
        self.chunk_workers = []
    
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
        """Traditional file download (for compatibility)"""
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
    
    def download_chunk(self, peer_ip, filename, chunk_index, chunk_hash, output_dir):
        """Download a specific chunk from a peer"""
        worker = ChunkDownloadWorker(
            peer_ip,
            filename,
            chunk_index,
            chunk_hash,
            output_dir,
            self.signals
        )
        self.chunk_workers.append(worker)
        worker.start()
        worker.wait()  # Wait for this chunk to complete
        
        # Check if the download was successful by looking for the file
        chunk_filename = f"{chunk_index}_{chunk_hash}"
        chunk_path = os.path.join(output_dir, chunk_filename)
        
        if os.path.exists(chunk_path):
            # Update the metadata to include this peer
            self.update_peer_in_metadata(filename, peer_ip)
            return True
        return False
    
    def update_peer_in_metadata(self, filename, peer_ip):
        """Update metadata to record which peer has a chunk"""
        file_hash = self.get_file_hash(filename)
        metadata_path = os.path.join("./metadata", f"{file_hash}.json")
        
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                if 'peers' not in metadata:
                    metadata['peers'] = []
                
                if peer_ip not in metadata['peers']:
                    metadata['peers'].append(peer_ip)
                
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f)
            except Exception as e:
                print(f"Error updating metadata: {e}")
    
    def request_metadata(self, filename):
        """Request metadata for a file from the network"""
        # Broadcast request for metadata
        message = f"METADATA_REQUEST:{filename}"
        # This would be sent through the chat server in the main app
    
    def fetch_metadata(self, peer_ip, filename):
        """Fetch metadata from a specific peer"""
        worker = MetadataWorker(
            peer_ip,
            filename,
            self.signals
        )
        self.metadata_workers.append(worker)
        worker.start()
    
    def get_file_hash(self, filename):
        """Create a unique identifier for a file"""
        return hashlib.md5(filename.encode()).hexdigest()
    
    def set_server(self, ip, port=None):
        self.SERVER_IP = ip
        if port:
            self.PORT = port


class DownloadWorker(QThread):
    """Original download worker (kept for compatibility)"""
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