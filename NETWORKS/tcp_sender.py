import socket
import threading

# Seeder Configuration
SEEDER_IP = "127.0.0.1"  # Change to the actual IP if needed
SEEDER_PORT = 5000  # TCP port for file sharing
TRACKER_IP = "127.0.0.1"  # Tracker's IP
TRACKER_PORT = 12000  # Tracker's UDP port
FILENAME = "example.txt"  # File the seeder shares

def register_with_tracker():
    """Send a REGISTER message to the tracker over UDP."""
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    message = f"REGISTER {FILENAME}".encode()
    udp_socket.sendto(message, (TRACKER_IP, TRACKER_PORT))
    udp_socket.close()
    print(f"Registered '{FILENAME}' with the tracker.")

def handle_client(client_socket):
    """Handles a leecher's file request."""
    requested_file = client_socket.recv(1024).decode()
    
    if requested_file == FILENAME:
        try:
            with open(FILENAME, "rb") as file:
                while chunk := file.read(1024):  # Read file in chunks
                    client_socket.send(chunk)
            print(f"Sent '{FILENAME}' to a leecher.")
        except FileNotFoundError:
            client_socket.send(b"ERROR: File not found")
    else:
        client_socket.send(b"ERROR: Requested file not available")

    client_socket.close()

def start_seeder():
    """Starts the TCP server to listen for leechers."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((SEEDER_IP, SEEDER_PORT))
    server_socket.listen(5)
    print(f"Seeder listening on {SEEDER_IP}:{SEEDER_PORT}...")

    while True:
        client_socket, addr = server_socket.accept()
        print(f"Leecher connected from {addr}")
        thread = threading.Thread(target=handle_client, args=(client_socket,))
        thread.start()

if __name__ == "__main__":
    register_with_tracker()  # Register with the tracker
    start_seeder()  # Start listening for leechers
