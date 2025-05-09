# 📡 Peer-to-Peer Serverless Messaging & File Sharing

> A fully decentralized, serverless file and message sharing system for lab sessions at Graphic Era Hill University (GEHU). Designed for seamless local network use without the internet, central servers, or static configurations.

## 🎯 Objective

Enable faculty to distribute code files, datasets, and messages to students in real-time during lab sessions — **without relying on cloud services or central servers**. Inspired by **BitTorrent**, this app ensures every participant acts as both a receiver and a sharer.

---

## 🧩 Features

- ✅ **Fully Decentralized** – No central server needed.
- 📡 **Peer Discovery via Broadcast** – Auto-discovers nearby devices on the local network.
- 🔁 **Multi-Hop Sharing** – Files/messages are re-broadcast by every recipient (P2P swarming).
- 🖥️ **Cross-Platform** – Works on Windows, macOS, and Linux.
- 🔒 **Access Control** – Only authorized devices (teacher) can initiate broadcasts.
- 📶 **Offline First** – Designed to work over campus Wi-Fi or LAN without the internet.
- 📁 **File & Message Support** – Share any file type and text messages instantly.
- 🧪 **Scalable** – Tested with 50+ devices in a lab setting.
- 🧼 **Simple GUI** – Easy interface for both teachers and students.

---

## 🧠 How It Works

1. **Session Start (Teacher)**:
   - Launches the app.
   - Broadcasts session announcement on the local network using UDP.

2. **Peer Discovery (Students)**:
   - Student systems auto-listen for sessions.
   - On receiving broadcast, connect via TCP and prepare to receive files/messages.

3. **P2P File Distribution**:
   - Files are split into chunks.
   - Chunks are sent to random peers.
   - Recipients further share the chunks they have to other connected peers — similar to torrent swarming.

4. **Message Relay**:
   - Messages are relayed and re-broadcast across all devices in a mesh fashion.

---

## 📦 Technologies Used

- Python 3
- Sockets (UDP for discovery, TCP for transfer)
- Threading for concurrent send/receive
- Tkinter for GUI
- JSON-based lightweight message protocol
- Custom chunk management algorithm

