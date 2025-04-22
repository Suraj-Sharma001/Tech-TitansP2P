# Updates to main.py

# Add/modify imports
import sys
import socket
import threading
import os
import json
import hashlib
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QSplitter, QLabel, QLineEdit, QPushButton, QTextEdit, QListWidget,
                           QGroupBox, QFileDialog, QStatusBar, QProgressBar, QMessageBox)
from PyQt5.QtCore import Qt, QDateTime, pyqtSignal, QObject
from file_client import FileClientManager
from file_server import FileServerManager

CHUNK_SIZE = 1024 * 1024  # 1MB chunks
PEERS = []  # Connected peers

class P2PFileShareApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_sharing = False
        self.file_sharing_name = None
        self.setWindowTitle("P2P File Sharing System")
        self.resize(900, 600)
        self.setMinimumSize(800, 500)
        
        # Initialize file managers
        self.file_client = FileClientManager()
        self.file_server = FileServerManager()
        
        # Initialize chunk management
        self.chunk_dir = "./chunks"
        if not os.path.exists(self.chunk_dir):
            os.makedirs(self.chunk_dir)
        
        # Initialize metadata storage
        self.metadata_dir = "./metadata"
        if not os.path.exists(self.metadata_dir):
            os.makedirs(self.metadata_dir)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        file_widget = QWidget()
        splitter.addWidget(file_widget)
        file_layout = QVBoxLayout(file_widget)
        
        file_section = self.create_file_section()
        file_layout.addWidget(file_section)
        
        chat_widget = QWidget()
        splitter.addWidget(chat_widget)
        chat_layout = QVBoxLayout(chat_widget)
        
        chat_section = self.create_chat_section()
        chat_layout.addWidget(chat_section)
        
        splitter.setSizes([450, 450])
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setMaximumHeight(16)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        self.HEADER = 64
        self.PORT = 5050
        self.FORMAT = 'utf-8'
        self.DISCONNECT_MESSAGE = "DISCONNECT"
        self.SERVER = "192.168.234.191"
        self.ADDR = (self.SERVER, self.PORT)
        self.my_ip = socket.gethostbyname(socket.gethostname())

        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client.connect(self.ADDR)
            self.status_bar.showMessage("Connected to chat server")
            threading.Thread(target=self.receive_messages, daemon=True).start()
        except Exception as e:
            self.status_bar.showMessage(f"Connection failed: {e}")
            
        # Connect signals from file managers
        self.file_client.signals.progress_update.connect(self.update_download_progress)
        self.file_client.signals.download_complete.connect(self.download_completed)
        self.file_client.signals.error.connect(self.show_file_error)
        
        self.file_server.signals.update_log.connect(self.log_server_message)
        
    def create_file_section(self):
        # Same as original code
        file_group = QGroupBox("P2P File Operations: ")
        layout = QVBoxLayout()
        
        # File selection area
        file_selection_layout = QHBoxLayout()
        file_selection_layout.addWidget(QLabel("Selected File:"))
        
        self.selected_file_edit = QLineEdit()
        self.selected_file_edit.setReadOnly(True)
        file_selection_layout.addWidget(self.selected_file_edit)
        
        self.select_file_btn = QPushButton("Select File")
        self.select_file_btn.clicked.connect(self.select_file)
        file_selection_layout.addWidget(self.select_file_btn)
        
        layout.addLayout(file_selection_layout)
        
        # Server controls
        server_layout = QHBoxLayout()
        self.server_status_label = QLabel("Server: Not Running")
        server_layout.addWidget(self.server_status_label)
        
        self.toggle_server_btn = QPushButton("Start Server")
        self.toggle_server_btn.clicked.connect(self.toggle_server)
        server_layout.addWidget(self.toggle_server_btn)
        
        layout.addLayout(server_layout)
        
        # File operations area
        file_ops_layout = QHBoxLayout()
        
        self.upload_btn = QPushButton("Upload File")
        self.upload_btn.clicked.connect(self.upload_file)
        file_ops_layout.addWidget(self.upload_btn)
        
        self.share_btn = QPushButton("Share File")
        self.share_btn.clicked.connect(self.share_file)
        file_ops_layout.addWidget(self.share_btn)
        
        self.download_btn = QPushButton("Download Selected")
        self.download_btn.clicked.connect(self.download_file)
        file_ops_layout.addWidget(self.download_btn)
        
        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.clicked.connect(self.refresh_file_list)
        file_ops_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(file_ops_layout)
        
        layout.addWidget(QLabel("Available Shared Files:"))
        
        self.files_list = QListWidget()
        self.files_list.itemDoubleClicked.connect(self.file_selected)
        layout.addWidget(self.files_list)
        
        # Transfer status area
        transfer_layout = QHBoxLayout()
        transfer_layout.addWidget(QLabel("Transfer Status:"))
        self.transfer_status = QLabel("No active transfer")
        transfer_layout.addWidget(self.transfer_status)
        layout.addLayout(transfer_layout)
        
        # Add a log area for file operations
        layout.addWidget(QLabel("File Operation Log:"))
        self.file_log = QListWidget()
        self.file_log.setMaximumHeight(100)
        layout.addWidget(self.file_log)
        
        file_group.setLayout(layout)
        return file_group
        
    def create_chat_section(self):
        # Same as original code
        chat_group = QGroupBox("Chat")
        layout = QVBoxLayout()
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)
        
        message_layout = QHBoxLayout()
        
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type your message here...")
        self.message_input.returnPressed.connect(self.send_message)
        message_layout.addWidget(self.message_input)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        message_layout.addWidget(self.send_btn)
        
        layout.addLayout(message_layout)
        
        peer_layout = QHBoxLayout()
        peer_layout.addStretch()
        layout.addLayout(peer_layout)
        
        chat_group.setLayout(layout)
        return chat_group
    
    # Updated file operations methods
    def select_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select File to Share", "", "All Files (*)")
        if file_name:
            self.selected_file_edit.setText(file_name)
            self.status_bar.showMessage(f"File selected: {file_name}")
    
    def toggle_server(self):
        if not self.file_server.server_running:
            self.file_server.start_server()
            self.server_status_label.setText(f"Server: Running on {self.file_server.SERVER}:{self.file_server.PORT}")
            self.toggle_server_btn.setText("Stop Server")
        else:
            self.file_server.stop_server()
            self.server_status_label.setText("Server: Not Running")
            self.toggle_server_btn.setText("Start Server")
    
    def upload_file(self):
        if not self.selected_file_edit.text():
            self.status_bar.showMessage("No file selected")
            return
            
        file_path = self.selected_file_edit.text()
        filename = os.path.basename(file_path)
        
        # Create chunks and metadata
        self.create_chunks(file_path)
        
        # Add file reference to server
        success = self.file_server.add_file_reference(filename)
        
        if success:
            self.status_bar.showMessage(f"File uploaded in chunks: {filename}")
            self.file_sharing = True
            self.file_sharing_name = filename
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            self.chat_display.append(f"[{timestamp}] You: Uploaded file '{filename}' in chunks")
            
            # Announce file availability to network
            share_msg = f"FILESHARE:{filename}"
            self.send_to_server(share_msg)
            
            # Refresh local file list
            self.refresh_file_list()
        else:
            self.status_bar.showMessage("Failed to upload file")
    
    def create_chunks(self, file_path):
        """Create chunks from a file and generate metadata"""
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        # Create a directory for this file's chunks
        file_chunk_dir = os.path.join(self.chunk_dir, self.get_file_hash(filename))
        if not os.path.exists(file_chunk_dir):
            os.makedirs(file_chunk_dir)
        
        # Initialize metadata
        chunks = []
        chunk_index = 0
        
        # Read and split the file
        with open(file_path, "rb") as f:
            while True:
                chunk_data = f.read(CHUNK_SIZE)
                if not chunk_data:
                    break
                
                # Generate chunk hash for integrity checking
                chunk_hash = hashlib.md5(chunk_data).hexdigest()
                
                # Save chunk to file
                chunk_filename = f"{chunk_index}_{chunk_hash}"
                chunk_path = os.path.join(file_chunk_dir, chunk_filename)
                
                with open(chunk_path, "wb") as chunk_file:
                    chunk_file.write(chunk_data)
                
                # Add to metadata
                chunks.append({
                    "index": chunk_index,
                    "hash": chunk_hash,
                    "size": len(chunk_data)
                })
                
                chunk_index += 1
        
        # Create metadata file
        metadata = {
            "filename": filename,
            "filesize": file_size,
            "chunks": chunks,
            "chunk_count": chunk_index,
            "owner": self.my_ip,
            "peers": [self.my_ip]  # Initially, we're the only peer with chunks
        }
        
        # Save metadata
        metadata_path = os.path.join(self.metadata_dir, f"{self.get_file_hash(filename)}.json")
        with open(metadata_path, "w") as mf:
            json.dump(metadata, mf)
        
        self.log_file_message(f"Created {chunk_index} chunks for {filename}")
        return True
    
    def get_file_hash(self, filename):
        """Create a unique identifier for a file"""
        return hashlib.md5(filename.encode()).hexdigest()
    
    def share_file(self):
        if not self.selected_file_edit.text():
            self.status_bar.showMessage("No file selected to share")
            return
            
        file_path = self.selected_file_edit.text()
        filename = os.path.basename(file_path)
        
        # Create chunks and metadata
        self.create_chunks(file_path)
        
        # Add file reference to server
        success = self.file_server.add_file_reference(filename)
        
        if success:
            self.status_bar.showMessage(f"File shared in chunks: {filename}")
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            self.chat_display.append(f"[{timestamp}] You: Shared file '{filename}' with the network")
            
            # Announce file share in chat
            share_msg = f"FILESHARE:{filename}"
            self.send_to_server(share_msg)
            
            # Refresh local file list
            self.refresh_file_list()
        else:
            self.status_bar.showMessage("Failed to share file")
    
    def file_selected(self, item):
        self.status_bar.showMessage(f"Selected: {item.text()}")
    
    def refresh_file_list(self):
        self.files_list.clear()
        
        # Get files from local metadata directory
        if os.path.exists(self.metadata_dir):
            for metadata_file in os.listdir(self.metadata_dir):
                if metadata_file.endswith('.json'):
                    try:
                        with open(os.path.join(self.metadata_dir, metadata_file), 'r') as f:
                            metadata = json.load(f)
                            self.files_list.addItem(metadata['filename'])
                    except:
                        pass
        
        # Also get files from network
        network_files = self.file_client.get_file_list()
        if network_files and isinstance(network_files, list):
            for file in network_files:
                # Add only if not already in the list
                found = False
                for i in range(self.files_list.count()):
                    if self.files_list.item(i).text() == file:
                        found = True
                        break
                
                if not found:
                    self.files_list.addItem(file)
    
    def download_file(self):
        selected_items = self.files_list.selectedItems()
        
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a file to download")
            return
            
        filename = selected_items[0].text()
        
        # Check if we have metadata for this file
        file_hash = self.get_file_hash(filename)
        metadata_path = os.path.join(self.metadata_dir, f"{file_hash}.json")
        
        # Update status
        self.transfer_status.setText(f"Downloading: {filename}")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        
        if os.path.exists(metadata_path):
            # We have metadata - use multi-peer download
            threading.Thread(target=self.download_from_peers, args=(filename,), daemon=True).start()
        else:
            # Try to get metadata from a peer first
            self.file_client.request_metadata(filename)
            self.status_bar.showMessage(f"Requesting metadata for {filename}")
    
    def download_from_peers(self, filename):
        """Download file chunks from multiple peers"""
        file_hash = self.get_file_hash(filename)
        metadata_path = os.path.join(self.metadata_dir, f"{file_hash}.json")
        
        try:
            # Load metadata
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Ensure chunk directory exists
            file_chunk_dir = os.path.join(self.chunk_dir, file_hash)
            if not os.path.exists(file_chunk_dir):
                os.makedirs(file_chunk_dir)
            
            # Download each chunk from available peers
            chunk_count = metadata['chunk_count']
            total_downloaded = 0
            
            for chunk_info in metadata['chunks']:
                chunk_index = chunk_info['index']
                chunk_hash = chunk_info['hash']
                chunk_filename = f"{chunk_index}_{chunk_hash}"
                chunk_path = os.path.join(file_chunk_dir, chunk_filename)
                
                # Skip if we already have this chunk
                if os.path.exists(chunk_path):
                    total_downloaded += 1
                    progress = int((total_downloaded / chunk_count) * 100)
                    self.signals.progress_update.emit(progress)
                    continue
                
                # Find a peer with this chunk
                found_peer = False
                for peer in metadata.get('peers', []):
                    if peer == self.my_ip:
                        continue  # Skip ourselves
                    
                    success = self.file_client.download_chunk(
                        peer, 
                        metadata['filename'], 
                        chunk_index, 
                        chunk_hash, 
                        file_chunk_dir
                    )
                    
                    if success:
                        found_peer = True
                        total_downloaded += 1
                        progress = int((total_downloaded / chunk_count) * 100)
                        self.signals.progress_update.emit(progress)
                        break
                
                if not found_peer:
                    self.signals.error.emit(f"Could not find a peer with chunk {chunk_index}")
                    return
            
            # Reassemble file
            output_path = self.reassemble_file(metadata)
            if output_path:
                self.signals.download_complete.emit(output_path)
            else:
                self.signals.error.emit("Failed to reassemble file")
                
        except Exception as e:
            self.signals.error.emit(f"Download error: {str(e)}")
    
    def reassemble_file(self, metadata):
        """Reassemble file from chunks"""
        try:
            filename = metadata['filename']
            file_hash = self.get_file_hash(filename)
            file_chunk_dir = os.path.join(self.chunk_dir, file_hash)
            
            # Ensure download directory exists
            download_dir = "./downloaded_files"
            if not os.path.exists(download_dir):
                os.makedirs(download_dir)
            
            output_path = os.path.join(download_dir, filename)
            
            # Open output file
            with open(output_path, 'wb') as outfile:
                # Process each chunk in order
                for i in range(metadata['chunk_count']):
                    # Find the chunk file
                    chunk_info = None
                    for chunk in metadata['chunks']:
                        if chunk['index'] == i:
                            chunk_info = chunk
                            break
                    
                    if not chunk_info:
                        raise Exception(f"Missing chunk info for index {i}")
                    
                    chunk_filename = f"{i}_{chunk_info['hash']}"
                    chunk_path = os.path.join(file_chunk_dir, chunk_filename)
                    
                    if not os.path.exists(chunk_path):
                        raise Exception(f"Missing chunk file: {chunk_filename}")
                    
                    # Read and write chunk
                    with open(chunk_path, 'rb') as infile:
                        outfile.write(infile.read())
            
            return output_path
        except Exception as e:
            self.log_file_message(f"Reassembly error: {str(e)}")
            return None
    
    # Chat methods
    def send_message(self):
        message = self.message_input.text().strip()
        if message:
            self.send_to_server(message)
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            self.chat_display.append(f"[{timestamp}] You: {message}")
            self.message_input.clear()
    
    def send_to_server(self, msg):
        try:
            message = msg.encode(self.FORMAT)
            msg_length = len(message)
            send_length = str(msg_length).encode(self.FORMAT)
            send_length += b' ' * (self.HEADER - len(send_length))
            self.client.send(send_length)
            self.client.send(message)
        except Exception as e:
            self.chat_display.append(f"[ERROR] Could not send message: {e}")
    
    def receive_messages(self):
        global PEERS
        while True:
            try:
                msg = self.client.recv(2048).decode(self.FORMAT)
                if msg:
                    timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")

                    # If it's a file share message
                    if msg.startswith("FILESHARE:"):
                        filename = msg.split(":", 1)[1]
                        self.chat_display.append(f"[{timestamp}] A new file has been shared: {filename}")
                        self.refresh_file_list()
                    
                    # If it's a metadata request
                    elif msg.startswith("METADATA_REQUEST:"):
                        filename = msg.split(":", 1)[1]
                        self.handle_metadata_request(filename)
                        
                    # If it's a metadata response
                    elif msg.startswith("METADATA_RESPONSE:"):
                        _, sender, filename = msg.split(":", 2)
                        self.chat_display.append(f"[{timestamp}] Received metadata for {filename} from {sender}")
                        self.file_client.fetch_metadata(sender, filename)
                        
                    # If it's an IP address
                    else:
                        try:
                            socket.inet_aton(msg)
                            if msg not in PEERS:
                                PEERS.append(msg)
                                self.chat_display.append(f"[{timestamp}] New peer connected with IP: {msg}")
                            continue  # Don't treat as chat message
                        except socket.error:
                            pass
                        
                        self.chat_display.append(f"[{timestamp}] Peer: {msg}")
            except:
                self.chat_display.append("[ERROR] Connection lost.")
                break
    
    def handle_metadata_request(self, filename):
        """Handle request for file metadata from a peer"""
        file_hash = self.get_file_hash(filename)
        metadata_path = os.path.join(self.metadata_dir, f"{file_hash}.json")
        
        if os.path.exists(metadata_path):
            # We have the metadata - announce availability
            response = f"METADATA_RESPONSE:{self.my_ip}:{filename}"
            self.send_to_server(response)
    
    # Signal handlers
    def update_download_progress(self, value):
        self.progress_bar.setValue(value)
    
    def download_completed(self, filepath):
        self.transfer_status.setText(f"Downloaded to: {filepath}")
        self.progress_bar.setVisible(False)
        self.log_file_message(f"File downloaded to {filepath}")
        QMessageBox.information(self, "Download Complete", f"File downloaded to {filepath}")
    
    def show_file_error(self, message):
        self.progress_bar.setVisible(False)
        self.transfer_status.setText("Transfer failed")
        self.log_file_message(f"Error: {message}")
        QMessageBox.critical(self, "File Operation Error", message)
    
    def log_file_message(self, message):
        self.file_log.addItem(message)
        self.file_log.scrollToBottom()
    
    def log_server_message(self, message):
        self.file_log.addItem(f"Server: {message}")
        self.file_log.scrollToBottom()
    
    def closeEvent(self, event):
        # Stop server if running
        if self.file_server.server_running:
            self.file_server.stop_server()
        
        # Close chat connection
        try:
            self.send_to_server(self.DISCONNECT_MESSAGE)
        except:
            pass
        
        event.accept()