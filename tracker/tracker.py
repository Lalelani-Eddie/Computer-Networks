import socket
import threading
import time

# Constants
HEADER = 64
PORT = 6020
SERVER = socket.gethostbyname(socket.gethostname())
ADDR = (SERVER, PORT)
FORMAT = 'utf-8'

tracker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
tracker.bind(ADDR)

active_seeders = {}  # {filename: [(ip, port, chunk_count, last_heartbeat)]}


def handle_client():
    while True:
        data, addr = tracker.recvfrom(1024)
        message = data.decode(FORMAT).split()
        print(f"Received message: {message} from {addr}")

        if not message:
            continue

        if message[0] == "REGISTER_SEEDER":
            if len(message) >= 3:
                filename = message[1]
                seeder_port = int(message[2])
                seeder_addr = (addr[0], seeder_port)

                seeder_info = (seeder_addr[0], seeder_addr[1], 0, time.time())

                if filename in active_seeders:
                    # Check if seeder already exists
                    existing_seeder = None
                    for i, seeder in enumerate(active_seeders[filename]):
                        if (seeder[0], seeder[1]) == (seeder_addr[0], seeder_addr[1]):
                            existing_seeder = i
                            break
                            
                    if existing_seeder is not None:
                        # Update existing seeder
                        active_seeders[filename][existing_seeder] = seeder_info
                    else:
                        # Add new seeder
                        active_seeders[filename].append(seeder_info)
                else:
                    active_seeders[filename] = [seeder_info]

                print(f"Registered seeder {seeder_addr} with file {filename}")
            else:
                print(f"Invalid REGISTER_SEEDER message from {addr}")

        elif message[0] == "CHUNK_COUNT":
            if len(message) >= 2:
                total_chunks = int(message[1])
                
                # Find the seeder that sent this message
                for filename, seeders in active_seeders.items():
                    for i, seeder in enumerate(seeders):
                        if (seeder[0], seeder[1]) == (addr[0], addr[1]) or seeder[0] == addr[0]:
                            active_seeders[filename][i] = (seeder[0], seeder[1], total_chunks, seeder[3])
                            print(f"Updated seeder {addr} for {filename} with {total_chunks} chunks")
                            break
            else:
                print(f"Invalid CHUNK_COUNT message from {addr}")

        elif message[0] == "REQUEST_SEEDERS":
            if len(message) >= 2:
                filename = message[1]
                seeders = active_seeders.get(filename, [])

                response = "SEEDERS " + " ".join([f"{ip}:{port}:{chunks}" for ip, port, chunks, _ in seeders]) if seeders else "NO_SEEDERS"
                tracker.sendto(response.encode(FORMAT), addr)
                print(f"Sent seeder list for {filename} to {addr}: {response}")
            else:
                print(f"Invalid REQUEST_SEEDERS message from {addr}")

        elif message[0] == "ALIVE":
            if len(message) >= 2:
                filename = message[1]

                if filename in active_seeders:
                    for i, (ip, port, chunks, last_heartbeat) in enumerate(active_seeders[filename]):
                        if (ip, port) == (addr[0], addr[1]) or ip == addr[0]:
                            active_seeders[filename][i] = (ip, port, chunks, time.time())
                            print(f"Received heartbeat from {ip}:{port} for {filename}")
                            break
            else:
                print(f"Invalid ALIVE message from {addr}")
                    
def remove_inactive_seeders():
    while True:
        time.sleep(100)
        current_time = time.time()

        for filename in list(active_seeders.keys()):
            active_seeders[filename] = [
                (ip, port, chunks, last_heartbeat)
                for (ip, port, chunks, last_heartbeat) in active_seeders[filename]
                if current_time - last_heartbeat < 60
            ]

            if not active_seeders[filename]:
                del active_seeders[filename]

        print(f"[CLEANUP] Removed inactive seeders. Active seeders: {active_seeders}")

def start():
    print(f"[STARTING] Tracker is starting at {SERVER}:{PORT}")
    
    threading.Thread(target=handle_client, daemon=True).start()  # Only one instance
    threading.Thread(target=remove_inactive_seeders, daemon=True).start()
    
    print(f"[LISTENING] Tracker is listening on {SERVER}:{PORT}")

    try:
        while True:
            time.sleep(1)  # Prevents 100% CPU usage
    except KeyboardInterrupt:
        print("\n[STOPPING] Tracker shutting down...")
        tracker.close()  # Close the UDP socket
        exit(0)  # Graceful exit

start()