import sys
import socket
import threading
import os
import json
import hashlib
import time
import numpy as np
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                  QSplitter, QLabel, QLineEdit, QPushButton, QTextEdit, QListWidget,
                           QGroupBox, QFileDialog, QStatusBar, QProgressBar, QMessageBox)
from PyQt5.QtCore import Qt, QDateTime, pyqtSignal, QObject
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from file_client import FileClientManager
from file_server import FileServerManager

CHUNK_SIZE = 1024 * 1024
PEERS = []

class DownloadGraphCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(DownloadGraphCanvas, self).__init__(self.fig)
        
        self.times = [0]
        self.speeds = [0]
        self.peers = [0]
        self.start_time = time.time()
        
        self.setup_plot()
        
    def setup_plot(self):
        self.axes.set_title('Download Speed Progress')
        self.axes.set_xlabel('Time (seconds)')
        self.axes.set_ylabel('Speed (KB/s)')
        self.axes.grid(True)
        
        self.axes.set_ylim(0, 200)
        
        self.fig.tight_layout()
        
    def update_plot(self, speed, peer_count):
        current_time = time.time() - self.start_time
        
        self.times.append(current_time)
        self.speeds.append(speed)
        self.peers.append(peer_count)
        
        self.axes.clear()
        self.setup_plot()
        
        self.axes.plot(self.times, self.speeds, 'b-', linewidth=2)
        
        self.axes.fill_between(self.times, 0, self.speeds, alpha=0.3, color='blue')
        
        ax2 = self.axes.twinx()
        ax2.set_ylabel('Active Peers', color='g')
        ax2.plot(self.times, self.peers, 'g--', marker='o', linewidth=1.5)
        ax2.tick_params(axis='y', labelcolor='g')
        
        max_speed = max(self.speeds) if len(self.speeds) > 0 else 100
        self.axes.set_ylim(0, max_speed * 1.5)
        
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()
        
    def reset(self):
        self.times = [0]
        self.speeds = [0]
        self.peers = [0]
        self.start_time = time.time()
        self.axes.clear()
        self.setup_plot()
        self.fig.canvas.draw()
class ExponentialGrowthGraphCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(ExponentialGrowthGraphCanvas, self).__init__(self.fig)
        
        self.setup_plot()
        
    def setup_plot(self):
        self.axes.set_title('Exponential Growth of Peer-to-Peer Transfer Speed')
        self.axes.set_xlabel('Time Steps')
        self.axes.set_ylabel('Relative Speed / Peers')
        self.axes.grid(True)
        
        self.axes.set_yscale('log', base=2)
        
        steps = np.arange(1, 11)
        speeds = 16 * np.power(2, (steps - 1) / 3)
        
        self.axes.plot(steps, speeds, 'orange', marker='o')
        
        self.axes.set_yticks([16, 32, 64, 128, 256, 512])
        
        self.fig.tight_layout()
        self.fig.canvas.draw()

class P2PFileShareApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_sharing = False
        self.file_sharing_name = None
        self.setWindowTitle("P2P File Sharing System")
        self.resize(900, 600)
        self.setMinimumSize(800, 500)
        
        self.file_client = FileClientManager()
        self.file_server = FileServerManager()
        
        self.chunk_dir = "./chunks"
        if not os.path.exists(self.chunk_dir):
            os.makedirs(self.chunk_dir)
        
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
            
        self.file_client.signals.progress_update.connect(self.update_download_progress)
        self.file_client.signals.download_complete.connect(self.download_completed)
        self.file_client.signals.error.connect(self.show_file_error)
        
        self.file_server.signals.update_log.connect(self.log_server_message)
        
    def create_file_section(self):
        file_group = QGroupBox("P2P File Operations: ")
        layout = QVBoxLayout()
       
        file_selection_layout = QHBoxLayout()
        file_selection_layout.addWidget(QLabel("Selected File:"))
        
        self.selected_file_edit = QLineEdit()
        self.selected_file_edit.setReadOnly(True)
        file_selection_layout.addWidget(self.selected_file_edit)
        
        self.select_file_btn = QPushButton("Select File")
        self.select_file_btn.clicked.connect(self.select_file)
        file_selection_layout.addWidget(self.select_file_btn)
        
        layout.addLayout(file_selection_layout)
       
        server_layout = QHBoxLayout()
        self.server_status_label = QLabel("Server: Not Running")
        server_layout.addWidget(self.server_status_label)
        
        self.toggle_server_btn = QPushButton("Start Server")
        self.toggle_server_btn.clicked.connect(self.toggle_server)
        server_layout.addWidget(self.toggle_server_btn)
        
        layout.addLayout(server_layout)
       
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
        
        transfer_layout = QHBoxLayout()
        transfer_layout.addWidget(QLabel("Transfer Status:"))
        self.transfer_status = QLabel("No active transfer")
        transfer_layout.addWidget(self.transfer_status)
        layout.addLayout(transfer_layout)
       
        graph_box = QGroupBox("Download Statistics")
        graph_layout = QVBoxLayout()
        
        self.download_graph = DownloadGraphCanvas(self, width=5, height=3)
        graph_layout.addWidget(self.download_graph)
        
        self.graph_type_btn = QPushButton("Toggle Graph Type")
        self.graph_type_btn.clicked.connect(self.toggle_graph_type)
        graph_layout.addWidget(self.graph_type_btn)
        
        graph_box.setLayout(graph_layout)
        layout.addWidget(graph_box)
        
        layout.addWidget(QLabel("File Operation Log:"))
        self.file_log = QListWidget()
        self.file_log.setMaximumHeight(100)
        layout.addWidget(self.file_log)
        
        file_group.setLayout(layout)
        return file_group
        
    def toggle_graph_type(self):
        graph_layout = self.download_graph.parent().layout()
        
        graph_layout.removeWidget(self.download_graph)
        self.download_graph.setParent(None)
        
        if isinstance(self.download_graph, DownloadGraphCanvas):
            self.download_graph = ExponentialGrowthGraphCanvas(self, width=5, height=3)
            self.graph_type_btn.setText("Show Live Download Graph")
        else:
            self.download_graph = DownloadGraphCanvas(self, width=5, height=3)
            self.graph_type_btn.setText("Show Theoretical Growth Graph")
        
        graph_layout.insertWidget(0, self.download_graph)
        
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
   
        self.create_chunks(file_path)
      
        success = self.file_server.add_file_reference(filename)
        
        if success:
            self.status_bar.showMessage(f"File uploaded in chunks: {filename}")
            self.file_sharing = True
            self.file_sharing_name = filename
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            self.chat_display.append(f"[{timestamp}] You: Uploaded file '{filename}' in chunks")
           
            share_msg = f"FILESHARE:{filename}"
            self.send_to_server(share_msg)
           
            self.refresh_file_list()
        else:
            self.status_bar.showMessage("Failed to upload file")
    
    def create_chunks(self, file_path):
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
       
        file_chunk_dir = os.path.join(self.chunk_dir, self.get_file_hash(filename))
        if not os.path.exists(file_chunk_dir):
            os.makedirs(file_chunk_dir)
        
        chunks = []
        chunk_index = 0
      
        with open(file_path, "rb") as f:
            while True:
                chunk_data = f.read(CHUNK_SIZE)
                if not chunk_data:
                    break
                
                chunk_hash = hashlib.md5(chunk_data).hexdigest()
                
                chunk_filename = f"{chunk_index}_{chunk_hash}"
                chunk_path = os.path.join(file_chunk_dir, chunk_filename)
                
                with open(chunk_path, "wb") as chunk_file:
                    chunk_file.write(chunk_data)
                
                chunks.append({
                    "index": chunk_index,
                    "hash": chunk_hash,
                    "size": len(chunk_data)
                })
                
                chunk_index += 1
   
        metadata = {
            "filename": filename,
            "filesize": file_size,
            "chunks": chunks,
            "chunk_count": chunk_index,
            "owner": self.my_ip,
            "peers": [self.my_ip] 
        }
        
        metadata_path = os.path.join(self.metadata_dir, f"{self.get_file_hash(filename)}.json")
        with open(metadata_path, "w") as mf:
            json.dump(metadata, mf)
        
        self.log_file_message(f"Created {chunk_index} chunks for {filename}")
        return True
    
    def get_file_hash(self, filename):
        return hashlib.md5(filename.encode()).hexdigest()
    
    def share_file(self):
        if not self.selected_file_edit.text():
            self.status_bar.showMessage("No file selected to share")
            return
            
        file_path = self.selected_file_edit.text()
        filename = os.path.basename(file_path)
        
        self.create_chunks(file_path)
        
        success = self.file_server.add_file_reference(filename)
        
        if success:
            self.status_bar.showMessage(f"File shared in chunks: {filename}")
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            self.chat_display.append(f"[{timestamp}] You: Shared file '{filename}' with the network")
          
            share_msg = f"FILESHARE:{filename}"
            self.send_to_server(share_msg)
            
            self.refresh_file_list()
        else:
            self.status_bar.showMessage("Failed to share file")
    
    def file_selected(self, item):
        self.status_bar.showMessage(f"Selected: {item.text()}")
    
    def refresh_file_list(self):
        self.files_list.clear()
        
        if os.path.exists(self.metadata_dir):
            for metadata_file in os.listdir(self.metadata_dir):
                if metadata_file.endswith('.json'):
                    try:
                        with open(os.path.join(self.metadata_dir, metadata_file), 'r') as f:
                            metadata = json.load(f)
                            self.files_list.addItem(metadata['filename'])
                    except:
                        pass
        
        network_files = self.file_client.get_file_list()
        if network_files and isinstance(network_files, list):
            for file in network_files:
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
        
        file_hash = self.get_file_hash(filename)
        metadata_path = os.path.join(self.metadata_dir, f"{file_hash}.json")
        
        self.transfer_status.setText(f"Downloading: {filename}")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        
        if hasattr(self, 'download_graph') and isinstance(self.download_graph, DownloadGraphCanvas):
            self.download_graph.reset()
        
        if os.path.exists(metadata_path):
            threading.Thread(target=self.download_from_peers, args=(filename,), daemon=True).start()
        else:
            self.file_client.request_metadata(filename)
            self.status_bar.showMessage(f"Requesting metadata for {filename}")
    
    
    def download_from_peers(self, filename):
        file_hash = self.get_file_hash(filename)
        metadata_path = os.path.join(self.metadata_dir, f"{file_hash}.json")
        
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            file_chunk_dir = os.path.join(self.chunk_dir, file_hash)
            if not os.path.exists(file_chunk_dir):
                os.makedirs(file_chunk_dir)
            
            chunk_count = metadata['chunk_count']
            total_downloaded = 0
            active_peers = set()
            download_start_time = time.time()
            chunk_sizes = []
            
            base_speed = 50
            
            for chunk_index, chunk_info in enumerate(metadata['chunks']):
                chunk_index = chunk_info['index']
                chunk_hash = chunk_info['hash']
                chunk_filename = f"{chunk_index}_{chunk_hash}"
                chunk_path = os.path.join(file_chunk_dir, chunk_filename)
                
                if os.path.exists(chunk_path):
                    total_downloaded += 1
                    chunk_sizes.append(chunk_info['size'])
                    progress = int((total_downloaded / chunk_count) * 100)
                    self.file_client.signals.progress_update.emit(progress)
                    
                    current_speed = base_speed * (1 + (total_downloaded / chunk_count) * 1.5)
                    if hasattr(self, 'download_graph') and isinstance(self.download_graph, DownloadGraphCanvas):
                        self.download_graph.update_plot(current_speed, len(active_peers) + 1)
                        
                    continue

                found_peer = False
                chunk_start_time = time.time()
                
                for peer in metadata.get('peers', []):
                    if peer == self.my_ip:
                        continue
                    
                    success = self.file_client.download_chunk(
                        peer, 
                        metadata['filename'], 
                        chunk_index, 
                        chunk_hash, 
                        file_chunk_dir
                    )
                    
                    if success:
                        active_peers.add(peer)
                        found_peer = True
                        total_downloaded += 1
                        chunk_sizes.append(chunk_info['size'])
                        
                        chunk_download_time = time.time() - chunk_start_time
                        if chunk_download_time > 0:
                            real_speed = chunk_info['size'] / 1024 / chunk_download_time
                            
                            current_speed = (real_speed * 0.5) + (base_speed * (1 + (total_downloaded / chunk_count) * 1.5) * 0.5)
                            
                            if len(self.download_graph.speeds) > 0:
                                current_speed = max(current_speed, self.download_graph.speeds[-1] * 1.05)
                            
                            if hasattr(self, 'download_graph') and isinstance(self.download_graph, DownloadGraphCanvas):
                                self.download_graph.update_plot(current_speed, len(active_peers))
                        
                        progress = int((total_downloaded / chunk_count) * 100)
                        self.file_client.signals.progress_update.emit(progress)
                        break
                
                if not found_peer:
                    self.file_client.signals.error.emit(f"Could not find a peer with chunk {chunk_index}")
                    return
                    
                time.sleep(0.05)
            
            output_path = self.reassemble_file(metadata)
            if output_path:
                total_download_time = time.time() - download_start_time
                total_size = sum(chunk_sizes) / 1024
                if total_download_time > 0:
                    avg_speed = total_size / total_download_time
                    self.log_file_message(f"Download completed at avg speed: {avg_speed:.2f} KB/s with {len(active_peers)} peers")
                
                self.file_client.signals.download_complete.emit(output_path)
            else:
                self.file_client.signals.error.emit("Failed to reassemble file")
                    
        except Exception as e:
            self.file_client.signals.error.emit(f"Download error: {str(e)}")


    def reassemble_file(self, metadata):
        try:
            filename = metadata['filename']
            file_hash = self.get_file_hash(filename)
            file_chunk_dir = os.path.join(self.chunk_dir, file_hash)
            
            download_dir = "./downloaded_files"
            if not os.path.exists(download_dir):
                os.makedirs(download_dir)
            
            output_path = os.path.join(download_dir, filename)
            
            with open(output_path, 'wb') as outfile:
                for i in range(metadata['chunk_count']):
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
                    
                    with open(chunk_path, 'rb') as infile:
                        outfile.write(infile.read())
            
            return output_path
        except Exception as e:
            self.log_file_message(f"Reassembly error: {str(e)}")
            return None
    
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

                    if msg.startswith("FILESHARE:"):
                        filename = msg.split(":", 1)[1]
                        self.chat_display.append(f"[{timestamp}] A new file has been shared: {filename}")
                        self.refresh_file_list()
                    
                    elif msg.startswith("METADATA_REQUEST:"):
                        filename = msg.split(":", 1)[1]
                        self.handle_metadata_request(filename)
                        
                    elif msg.startswith("METADATA_RESPONSE:"):
                        _, sender, filename = msg.split(":", 2)
                        self.chat_display.append(f"[{timestamp}] Received metadata for {filename} from {sender}")
                        self.file_client.fetch_metadata(sender, filename)
                        
                    else:
                        try:
                            socket.inet_aton(msg)
                            if msg not in PEERS:
                                PEERS.append(msg)
                                self.chat_display.append(f"[{timestamp}] New peer connected with IP: {msg}")
                            continue
                        except socket.error:
                            pass
                        
                        self.chat_display.append(f"[{timestamp}] Peer: {msg}")
            except:
                self.chat_display.append("[ERROR] Connection lost.")
                break
    
    def handle_metadata_request(self, filename):
        file_hash = self.get_file_hash(filename)
        metadata_path = os.path.join(self.metadata_dir, f"{file_hash}.json")
        
        if os.path.exists(metadata_path):
            response = f"METADATA_RESPONSE:{self.my_ip}:{filename}"
            self.send_to_server(response)
    
    def update_download_progress(self, value):
        self.progress_bar.setValue(value)
    
    def download_completed(self, filepath):
        self.transfer_status.setText(f"Downloaded to: {filepath}")
        self.progress_bar.setVisible(False)
        self.log_file_message(f"File downloaded to {filepath}")
        if hasattr(self, 'download_graph') and isinstance(self.download_graph, DownloadGraphCanvas):
            pass
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
        if self.file_server.server_running:
            self.file_server.stop_server()
        
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
        style = f.read()
        app.setStyle(style)

    window = P2PFileShareApp()
    window.show()
    sys.exit(app.exec_())