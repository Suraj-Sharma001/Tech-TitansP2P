import sys
import socket
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QSplitter, QLabel, QLineEdit, QPushButton, QTextEdit, QListWidget,
                             QGroupBox, QFileDialog, QStatusBar, QProgressBar, QMessageBox)
from PyQt5.QtCore import Qt, QDateTime, pyqtSignal, QObject
from file_client import FileClientManager
from file_server import FileServerManager
import os
from pathlib import Path

flag = True
CHUNK_SIZE = 1024 * 1024  
COUNTER = 1;

on_server = []

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
    
    # File operations methods
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
        success = self.file_server.add_file(file_path)
        
        if success:
            file_name = file_path.split('/')[-1]
            self.status_bar.showMessage(f"File uploaded: {file_name}")
            self.file_sharing = True;
            self.file_sharing_name = file_name
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            self.chat_display.append(f"[{timestamp}] You: Uploaded file '{file_name}'")
            
            # Refresh local file list
            self.refresh_file_list()
        else:
            self.status_bar.showMessage("Failed to upload file")
    
    def share_file(self):
        if not self.selected_file_edit.text():
            self.status_bar.showMessage("No file selected to share")
            return
            
        file_name = self.selected_file_edit.text().split('/')[-1]
        success = self.file_server.add_file(self.selected_file_edit.text())
        
        if success:
            self.status_bar.showMessage(f"File shared: {file_name}")
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            self.chat_display.append(f"[{timestamp}] You: Shared file '{file_name}' with the network")
            
            # Announce file share in chat
            share_msg = f"FILESHARE:{file_name}"
            self.send_to_server(share_msg)
            
            # Refresh local file list
            self.refresh_file_list()
        else:
            self.status_bar.showMessage("Failed to share file")
    
    def file_selected(self, item):
        self.status_bar.showMessage(f"Selected: {item.text()}")
    
    def refresh_file_list(self):
        self.files_list.clear()
        files = self.file_client.get_file_list()
        
        if files:
            if isinstance(files, list):
                for file in files:
                    self.files_list.addItem(file)
            else:
                self.log_file_message(files)  # It's an error message
    
    def download_file(self):
        selected_items = self.files_list.selectedItems()
        
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a file to download")
            return
            
        filename = selected_items[0].text()
        
        # Update status
        self.transfer_status.setText(f"Downloading: {filename}")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        
        # Start download
        self.file_client.download_file(filename)
    
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

    my_ip = socket.gethostbyname(socket.gethostbyname)
    def file_chunks(counter, file_path):
        folder = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        temp_dir = os.path.join(folder, "temp")

        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        with open(file_path, "rb") as f:
            chunk_num = 0
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                chunk_filename = f"{filename}_chunk_{chunk_num}"
                chunk_path = os.path.join(temp_dir, chunk_filename)
                with open(chunk_path, "wb") as chunk_file:
                    chunk_file.write(chunk)
                chunk_num += 1
        
    def check_file(self):
        global COUNTER
        shared_folders = ["shared_files/send", "shared_files/Received"]
        for folder in shared_folders:
            if os.path.exists(folder):
                files = os.listdir(folder)
                if files:
                    for file in files:
                        file_path = os.path.join(folder, file)
                        if os.path.isfile(file_path):
                            COUNTER += 1
                            self.file_chunks(COUNTER, file_path)
        
    def receive_messages(self):
        while True:
            try:
                msg = self.client.recv(2048).decode(self.FORMAT)
                if msg:
                    # Check if it's a file share announcement
                    if msg.startswith("FILESHARE:"):
                        filename = msg.split(":", 1)[1]
                        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
                        self.chat_display.append(f"[{timestamp}] A new file has been shared: {filename}")
                        # Refresh file list
                        self.refresh_file_list()
                        if self.file_sharing:
                            self.check_file()
                    else:
                        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
                        if(flag): 
                            self.chat_display.append(socket.gethostname(socket.gethostbyname)())
                            flag = False
                        self.chat_display.append(f"[{timestamp}] Peer: {msg}")
                        if(socket.inet_aton(msg)):
                                COUNTER+=1
            except:
                self.chat_display.append("[ERROR] Connection lost.")
                break
    
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    with open("style.qss", "r") as f:
        app.setStyleSheet(f.read())
    
    window = P2PFileShareApp()
    window.show()
    
    sys.exit(app.exec_())