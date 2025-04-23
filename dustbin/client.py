# client.py - Module for client-side functions
import socket
import threading
import json
import time

def discover_servers(port=5051, timeout=3):
   
    discovered_servers = []
    
    # Create a UDP socket for broadcasting
    broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    broadcast_socket.settimeout(timeout)
    
    # Send discovery message
    discovery_message = json.dumps({
        "cmd": "DISCOVER",
        "port": port
    }).encode('utf-8')
    
    try:
        broadcast_socket.sendto(discovery_message, ('<broadcast>', port))
        
        # Wait for responses
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                data, addr = broadcast_socket.recvfrom(1024)
                response = json.loads(data.decode('utf-8'))
                if response.get("cmd") == "SERVER_ANNOUNCE":
                    server_ip = addr[0]
                    server_port = response.get("port", port)
                    discovered_servers.append((server_ip, server_port))
            except socket.timeout:
                break
            except json.JSONDecodeError:
                continue
    finally:
        broadcast_socket.close()
    
    return discovered_servers

def connect_to_server(server_ip, server_port=5051):
    """
    Establishes a connection to a P2P server.
    Returns a connected socket object if successful, None otherwise.
    """
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((server_ip, server_port))
        return client_socket
    except Exception as e:
        print(f"Failed to connect to server at {server_ip}:{server_port}: {e}")
        return None

def receive_file(client_socket, save_path, filesize, progress_callback=None):
    """
    Receives a file from the server and saves it to the specified path.
    Returns True if successful, False otherwise.
    """
    try:
        bytes_received = 0
        with open(save_path, 'wb') as f:
            while bytes_received < filesize:
                bytes_to_receive = min(4096, filesize - bytes_received)
                data = client_socket.recv(bytes_to_receive)
                if not data:
                    return False
                f.write(data)
                bytes_received += len(data)
                if progress_callback:
                    progress_callback(int((bytes_received / filesize) * 100))
        return True
    except Exception as e:
        print(f"Error receiving file: {e}")
        return False

def send_file(client_socket, file_path, progress_callback=None):
    """
    Sends a file to the server.
    Returns True if successful, False otherwise.
    """
    try:
        filesize = os.path.getsize(file_path)
        bytes_sent = 0
        with open(file_path, 'rb') as f:
            while bytes_sent < filesize:
                bytes_read = f.read(4096)
                if not bytes_read:
                    break
                client_socket.sendall(bytes_read)
                bytes_sent += len(bytes_read)
                if progress_callback:
                    progress_callback(int((bytes_sent / filesize) * 100))
        return True
    except Exception as e:
        print(f"Error sending file: {e}")
        return False    