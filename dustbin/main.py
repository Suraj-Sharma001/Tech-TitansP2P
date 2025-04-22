# main.py - Main application implementing the P2P file sharing system
import sys
import socket
import threading
import os
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QLabel, QLineEdit, QPushButton, QTextEdit, QListWidget,
                             QGroupBox, QFileDialog, QStatusBar, QProgressBar, QMessageBox)
from PyQt5.QtCore import Qt, QDateTime, pyqtSignal, QObject
from pathlib import Path

class WorkerSignals(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    update_status = pyqtSignal(str)
    file_received = pyqtSignal(str)

class P2PFileShareApp(QMainWindow):
    def __init__(self, is_server=False, server_ip=None, server_port=5051):
        super().__init__()
        self.is_server = is_server
        self.setWindowTitle("P2P File Sharing System")
        self.resize(900, 600)
        self.setMinimumSize(800, 500)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        file_widget = QWidget()
        splitter.addWidget(file_widget)
        file_layout = QVBoxLayout(file_widget)
        file_layout.addWidget(self.create_file_section())

        chat_widget = QWidget()
        splitter.addWidget(chat_widget)
        chat_layout = QVBoxLayout(chat_widget)
        chat_layout.addWidget(self.create_chat_section())

        splitter.setSizes([450, 450])

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setMaximumHeight(16)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        # Setup network parameters
        self.HEADER = 64
        self.PORT = server_port
        self.FORMAT = 'utf-8'
        self.DISCONNECT_MESSAGE = "DISCONNECT"
        
        # Create download directory
        self.download_dir = Path("downloads")
        self.download_dir.mkdir(exist_ok=True)
        
        # Setup signals
        self.signals = WorkerSignals()
        self.signals.progress.connect(self.update_progress)
        self.signals.finished.connect(self.transfer_finished)
        self.signals.error.connect(self.show_error)
        self.signals.update_status.connect(self.update_transfer_status)
        self.signals.file_received.connect(self.file_downloaded)

        # Setup server/client connection
        if self.is_server:
            self.SERVER = socket.gethostbyname(socket.gethostname())
            self.status_bar.showMessage("Running in server mode")
            # Start server in a separate thread
            threading.Thread(target=self.start_server, daemon=True).start()
        else:
            self.SERVER = server_ip if server_ip else '127.0.0.1'
            self.status_bar.showMessage("Running in client mode")

        # Connect to the server's chat system
        self.ADDR = (self.SERVER, self.PORT)
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client.connect(self.ADDR)
            self.status_bar.showMessage(f"Connected to server at {self.SERVER}")
            threading.Thread(target=self.receive_messages, daemon=True).start()
        except Exception as e:
            self.status_bar.showMessage(f"Connection failed: {e}")
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to server: {e}")

    def create_file_section(self):
        group = QGroupBox("P2P File Operations: ")
        layout = QVBoxLayout()

        sel_layout = QHBoxLayout()
        sel_layout.addWidget(QLabel("Selected File:"))
        self.selected_file_edit = QLineEdit()
        self.selected_file_edit.setReadOnly(True)
        sel_layout.addWidget(self.selected_file_edit)
        btn = QPushButton("Select File")
        btn.clicked.connect(self.select_file)
        sel_layout.addWidget(btn)
        layout.addLayout(sel_layout)

        ops = QHBoxLayout()
        up = QPushButton("Upload File")
        up.clicked.connect(self.upload_file)
        ops.addWidget(up)
        down = QPushButton("Download File")
        down.clicked.connect(self.download_file)
        ops.addWidget(down)
        layout.addLayout(ops)

        layout.addWidget(QLabel("Available Shared Files:"))
        self.files_list = QListWidget()
        self.files_list.itemDoubleClicked.connect(self.file_selected)
        layout.addWidget(self.files_list)

        ts = QHBoxLayout()
        ts.addWidget(QLabel("Transfer Status:"))
        self.transfer_status = QLabel("No active transfer")
        ts.addWidget(self.transfer_status)
        layout.addLayout(ts)

        # Refresh button
        refresh = QPushButton("Refresh File List")
        refresh.clicked.connect(self.request_file_list)
        layout.addWidget(refresh)

        group.setLayout(layout)
        return group

    def create_chat_section(self):
        group = QGroupBox("Chat")
        layout = QVBoxLayout()
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)

        msg_layout = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type your message here...")
        self.message_input.returnPressed.connect(self.send_message)
        msg_layout.addWidget(self.message_input)
        btn = QPushButton("Send")
        btn.clicked.connect(self.send_message)
        msg_layout.addWidget(btn)
        layout.addLayout(msg_layout)

        group.setLayout(layout)
        return group

    def start_server(self):
        import server
        server.start()

    def select_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select File to Share", "", "All Files (*)")
        if file_name:
            self.selected_file_edit.setText(file_name)
            self.status_bar.showMessage(f"File selected: {file_name}")

    def upload_file(self):
        filepath = self.selected_file_edit.text()
        if not filepath:
            self.status_bar.showMessage("No file selected")
            return

        if not os.path.exists(filepath):
            self.show_error("File does not exist")
            return

        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.transfer_status.setText(f"Uploading {filename}...")
        
        # Start upload in a separate thread
        thread = threading.Thread(
            target=self.upload_file_thread,
            args=(filepath, filename, filesize),
            daemon=True
        )
        thread.start()

    def upload_file_thread(self, filepath, filename, filesize):
        try:
            # Send upload request
            request = {
                "cmd": "UPLOAD_REQUEST",
                "filename": filename,
                "filesize": filesize
            }
            self.send_command(request)
            
            # Wait for approval
            response = self.receive_command()
            if response.get("cmd") != "UPLOAD_APPROVED":
                self.signals.error.emit("Upload request denied")
                return
            
            # Send file
            bytes_sent = 0
            with open(filepath, "rb") as f:
                while bytes_sent < filesize:
                    bytes_read = f.read(4096)
                    if not bytes_read:
                        break
                    self.client.sendall(bytes_read)
                    bytes_sent += len(bytes_read)
                    progress = int((bytes_sent / filesize) * 100)
                    self.signals.progress.emit(progress)
            
            # Wait for completion confirmation
            response = self.receive_command()
            if response.get("cmd") == "UPLOAD_COMPLETE":
                self.signals.update_status.emit(f"Upload of {filename} completed")
                timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
                message = f"[{timestamp}] You: Shared file '{filename}' with the network"
                self.add_chat_message(message)
                self.signals.finished.emit()
            else:
                self.signals.error.emit("Upload failed or incomplete")
        
        except Exception as e:
            self.signals.error.emit(f"Error during upload: {str(e)}")

    def download_file(self):
        selected_items = self.files_list.selectedItems()
        if not selected_items:
            self.status_bar.showMessage("No file selected to download")
            return
        
        filename = selected_items[0].text()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.transfer_status.setText(f"Downloading {filename}...")
        
        # Start download in a separate thread
        thread = threading.Thread(
            target=self.download_file_thread,
            args=(filename,),
            daemon=True
        )
        thread.start()

    def download_file_thread(self, filename):
        try:
            # Send download request
            request = {
                "cmd": "DOWNLOAD_REQUEST",
                "filename": filename
            }
            self.send_command(request)
            
            # Wait for approval
            response = self.receive_command()
            if response.get("cmd") != "DOWNLOAD_APPROVED":
                self.signals.error.emit("Download request denied or file not found")
                return
            
            filesize = response.get("filesize")
            filepath = self.download_dir / filename
            
            # Receive file
            bytes_received = 0
            with open(filepath, "wb") as f:
                while bytes_received < filesize:
                    bytes_to_receive = min(4096, filesize - bytes_received)
                    data = self.client.recv(bytes_to_receive)
                    if not data:
                        break
                    f.write(data)
                    bytes_received += len(data)
                    progress = int((bytes_received / filesize) * 100)
                    self.signals.progress.emit(progress)
            
            # Wait for completion message
            response = self.receive_command()
            if response.get("cmd") == "DOWNLOAD_COMPLETE":
                self.signals.update_status.emit(f"Download of {filename} completed")
                self.signals.file_received.emit(str(filepath))
                self.signals.finished.emit()
            else:
                self.signals.error.emit("Download failed or incomplete")
        
        except Exception as e:
            self.signals.error.emit(f"Error during download: {str(e)}")

    def file_selected(self, item):
        self.status_bar.showMessage(f"Selected: {item.text()}")

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

    def send_command(self, cmd_dict):
        cmd_str = f"CMD:{json.dumps(cmd_dict)}"
        self.send_to_server(cmd_str)

    def receive_command(self):
        while True:
            msg = self.client.recv(2048).decode(self.FORMAT)
            if msg:
                try:
                    return json.loads(msg)
                except:
                    # Not a JSON command, just a regular message
                    continue

    def receive_messages(self):
        while True:
            try:
                msg_length = self.client.recv(self.HEADER).decode(self.FORMAT)
                if msg_length:
                    msg_length = int(msg_length)
                    msg = self.client.recv(msg_length).decode(self.FORMAT)
                    
                    # Check if it's a command message
                    try:
                        cmd = json.loads(msg)
                        if isinstance(cmd, dict) and "cmd" in cmd:
                            self.handle_command(cmd)
                            continue
                    except:
                        pass
                    
                    # Regular chat message
                    timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
                    message = f"[{timestamp}] Peer: {msg}"
                    self.add_chat_message(message)
            except Exception as e:
                print(f"Reception error: {e}")
                self.add_chat_message("[ERROR] Connection lost.")
                break

    def handle_command(self, cmd):
        command = cmd.get("cmd")
        if command == "FILE_LIST":
            self.update_file_list(cmd.get("files", []))
        elif command == "ERROR":
            self.show_error(cmd.get("message", "Unknown error"))
        # Add more command handlers as needed

    def request_file_list(self):
        self.send_command({"cmd": "LIST_FILES"})
        self.status_bar.showMessage("Requesting file list...")

    def update_file_list(self, files):
        self.files_list.clear()
        for file in files:
            self.files_list.addItem(file)
        self.status_bar.showMessage(f"File list updated: {len(files)} files available")

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def transfer_finished(self):
        self.progress_bar.setVisible(False)

    def show_error(self, message):
        QMessageBox.critical(self, "Error", message)
        self.progress_bar.setVisible(False)
        self.transfer_status.setText("Transfer failed")

    def update_transfer_status(self, message):
        self.transfer_status.setText(message)

    def file_downloaded(self, filepath):
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        filename = os.path.basename(filepath)
        self.add_chat_message(f"[{timestamp}] System: Downloaded '{filename}' to {filepath}")

    def add_chat_message(self, message):
        self.chat_display.append(message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    is_server = len(sys.argv) > 1 and sys.argv[1].lower() == 'server'
    server_ip = sys.argv[2] if len(sys.argv) > 2 else None
    server_port = int(sys.argv[3]) if len(sys.argv) > 3 else 5051
    
    window = P2PFileShareApp(is_server=is_server, server_ip=server_ip, server_port=server_port)
    window.show()
    sys.exit(app.exec_())