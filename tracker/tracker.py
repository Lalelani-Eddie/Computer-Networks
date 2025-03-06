import socket
import threading

HEADER = 64
PORT = 6020
SERVER = socket.gethostbyname(socket.gethostname())  # Get local IP
ADDR = (SERVER, PORT)
FORMAT = 'utf-8'

# Set up the UDP socket
tracker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
tracker.bind(ADDR)

active_seeders = {}  # {filename: [(ip, port), ...]}

def handle_client():
    while True:
        data, addr = tracker.recvfrom(1024)
        message = data.decode(FORMAT).split()

        if message[0] == "REGISTER_SEEDER":
            filename = message[1]
            seeder_addr = (addr[0], int(message[2]))
            active_seeders.setdefault(filename, []).append(seeder_addr)
            print(f"Seeder {seeder_addr} registered for {filename}")

        elif message[0] == "REQUEST_SEEDERS":
            filename = message[1]
            seeders = active_seeders.get(filename, [])
            response = "SEEDERS " + " ".join([f"{ip}:{port}" for ip, port in seeders]) if seeders else "NO_SEEDERS"
            tracker.sendto(response.encode(FORMAT), addr)

        elif message[0] == "ALIVE":
            # Keep seeder alive (Optional: Implement a heartbeat mechanism)
            pass

def start():
    print(f"[STARTING] Tracker is starting at {SERVER}:{PORT}")
    threading.Thread(target=handle_client, daemon=True).start()
    print(f"[LISTENING] Tracker is listening on {SERVER}:{PORT}")

    # The server runs indefinitely, handling client messages
    while True:
        pass

start()
