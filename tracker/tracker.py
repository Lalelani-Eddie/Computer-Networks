import socket
import threading
import os

HEADER = 64
PORT = 6020
SERVER = socket.gethostbyname(socket.gethostname())  # Get local IP
ADDR = (SERVER, PORT)
FORMAT = 'utf-8'
CHUNK_SIZE = 512 * 1024  # 512 KB (you can adjust this value)

# Set up the UDP socket
tracker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
tracker.bind(ADDR)

active_seeders = {}  # {filename: [(ip, port, chunk_count), ...]}

def handle_client():
    while True:
        data, addr = tracker.recvfrom(1024)
        message = data.decode(FORMAT).split()
        print(f"Received message: {message} from {addr}")

        if message[0] == "REGISTER_SEEDER":
            filename = message[1]
            seeder_addr = (addr[0], int(message[2]))
            
            # Initialize with 0 chunks, will be updated when CHUNK_COUNT message is received
            seeder_info = (seeder_addr[0], seeder_addr[1], 0)
            
            # Add or update seeder info
            if filename in active_seeders:
                # Check if this seeder already exists
                existing_seeders = [s for s in active_seeders[filename] if (s[0], s[1]) == seeder_addr]
                if existing_seeders:
                    # Update existing entry (preserving chunk count)
                    pass
                else:
                    # Add new seeder
                    active_seeders[filename].append(seeder_info)
            else:
                active_seeders[filename] = [seeder_info]
                
            print(f"Registered seeder {seeder_addr} with file {filename}")

        elif message[0] == "CHUNK_COUNT":
            # Update the chunk count for the most recently registered seeder
            total_chunks = int(message[1])
            
            # Find the seeder that sent this message
            for filename, seeders in active_seeders.items():
                for i, seeder in enumerate(seeders):
                    if (seeder[0], seeder[1]) == (addr[0], SEEDER_PORT):
                        # Update the chunk count
                        active_seeders[filename][i] = (seeder[0], seeder[1], total_chunks)
                        print(f"Updated seeder {(seeder[0], seeder[1])} WITH FILE {filename} has: {total_chunks} chunks")
                        break

        elif message[0] == "REQUEST_SEEDERS":
            filename = message[1]
            seeders = active_seeders.get(filename, [])
            
            # Include chunk count in response
            response = "SEEDERS " + " ".join([f"{ip}:{port}:{chunks}" for ip, port, chunks in seeders]) if seeders else "NO_SEEDERS"
            tracker.sendto(response.encode(FORMAT), addr)
            print(f"Sent seeder list for {filename} to {addr}")

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

# Global variable for the seeder port (needed for CHUNK_COUNT message handling)
SEEDER_PORT = 7000

start()