import socket
import threading
import time

# Constants
HEADER = 64  # Header size for messages (not currently used but kept for future expansion)
PORT = 6020  # Port number for the tracker service
SERVER = socket.gethostbyname(socket.gethostname())  # Gets the local machine's IP address
ADDR = (SERVER, PORT)  # Address tuple for binding socket
FORMAT = 'utf-8'  # Encoding format for messages

# Initialize the UDP socket for the tracker
tracker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
tracker.bind(ADDR)  # Bind the socket to the address

# Dictionary to store active seeders
# Structure: {filename: [(ip, port, chunk_count, last_heartbeat)]}
# - filename: name of the shared file
# - ip: seeder's IP address
# - port: seeder's port number
# - chunk_count: number of chunks the seeder has
# - last_heartbeat: timestamp of the last heartbeat
active_seeders = {}


def handle_client():
    """
    Main function to handle all incoming UDP messages from clients.
    Processes different message types:
    - REGISTER_SEEDER: Register a new file seeder
    - CHUNK_COUNT: Update the number of chunks a seeder has
    - REQUEST_SEEDERS: Respond with a list of seeders for a file
    - ALIVE: Process heartbeat messages to maintain seeder status
    """
    while True:
        # Wait for incoming UDP packets
        data, addr = tracker.recvfrom(1024)
        # Parse the received message
        message = data.decode(FORMAT).split()
        print(f"Received message: {message} from {addr}")

        if not message:
            continue  # Skip empty messages

        # Process REGISTER_SEEDER messages
        if message[0] == "REGISTER_SEEDER":
            if len(message) >= 3:
                filename = message[1]  # File being shared
                seeder_port = int(message[2])  # Seeder's listening port
                seeder_addr = (addr[0], seeder_port)  # Full seeder address
                
                # Create seeder information entry with initial timestamp
                seeder_info = (seeder_addr[0], seeder_addr[1], 0, time.time())

                if filename in active_seeders:
                    # Check if this seeder is already registered for this file
                    existing_seeder = None
                    for i, seeder in enumerate(active_seeders[filename]):
                        if (seeder[0], seeder[1]) == (seeder_addr[0], seeder_addr[1]):
                            existing_seeder = i
                            break
                            
                    if existing_seeder is not None:
                        # Update the existing seeder entry
                        active_seeders[filename][existing_seeder] = seeder_info
                    else:
                        # Add this as a new seeder for the file
                        active_seeders[filename].append(seeder_info)
                else:
                    # First seeder for this file
                    active_seeders[filename] = [seeder_info]

                print(f"Registered seeder {seeder_addr} with file {filename}")
            else:
                print(f"Invalid REGISTER_SEEDER message from {addr}")

        # Process CHUNK_COUNT messages
        elif message[0] == "CHUNK_COUNT":
            if len(message) >= 2:
                total_chunks = int(message[1])  # Number of chunks reported by seeder
                
                # Find the seeder that sent this message and update its chunk count
                for filename, seeders in active_seeders.items():
                    for i, seeder in enumerate(seeders):
                        # Match based on IP and port, or just IP as fallback
                        if (seeder[0], seeder[1]) == (addr[0], addr[1]) or seeder[0] == addr[0]:
                            # Update the chunk count while preserving other information
                            active_seeders[filename][i] = (seeder[0], seeder[1], total_chunks, seeder[3])
                            print(f"Updated seeder {addr} for {filename} with {total_chunks} chunks")
                            break
            else:
                print(f"Invalid CHUNK_COUNT message from {addr}")

        # Process REQUEST_SEEDERS messages (from leechers)
        elif message[0] == "REQUEST_SEEDERS":
            if len(message) >= 2:
                filename = message[1]  # Requested file
                seeders = active_seeders.get(filename, [])  # Get list of seeders for the file

                # Prepare response with seeders in format "ip:port:chunks"
                response = "SEEDERS " + " ".join([f"{ip}:{port}:{chunks}" for ip, port, chunks, _ in seeders]) if seeders else "NO_SEEDERS"
                tracker.sendto(response.encode(FORMAT), addr)  # Send the response
                print(f"Sent seeder list for {filename} to {addr}: {response}")
            else:
                print(f"Invalid REQUEST_SEEDERS message from {addr}")

        # Process ALIVE messages (heartbeats)
        elif message[0] == "ALIVE":
            if len(message) >= 2:
                filename = message[1]  # File the seeder is sharing

                if filename in active_seeders:
                    # Find and update the timestamp for the seeder
                    for i, (ip, port, chunks, last_heartbeat) in enumerate(active_seeders[filename]):
                        if (ip, port) == (addr[0], addr[1]) or ip == addr[0]:
                            # Update the heartbeat timestamp
                            active_seeders[filename][i] = (ip, port, chunks, time.time())
                            print(f"Received heartbeat from {ip}:{port} for {filename}")
                            break
            else:
                print(f"Invalid ALIVE message from {addr}")
                    

def remove_inactive_seeders():
    """
    Periodic cleanup function that runs in a separate thread.
    Removes seeders that haven't sent a heartbeat in the last 60 seconds.
    Also removes file entries if they no longer have any active seeders.
    """
    while True:
        time.sleep(100)  # Check for inactive seeders every 100 seconds
        current_time = time.time()

        for filename in list(active_seeders.keys()):
            # Filter out seeders that haven't sent a heartbeat in 60 seconds
            active_seeders[filename] = [
                (ip, port, chunks, last_heartbeat)
                for (ip, port, chunks, last_heartbeat) in active_seeders[filename]
                if current_time - last_heartbeat < 60  # 60-second timeout
            ]

            # Remove the file entry if there are no seeders left
            if not active_seeders[filename]:
                del active_seeders[filename]

        print(f"[CLEANUP] Removed inactive seeders. Active seeders: {active_seeders}")


def start():
    """
    Main function to start the tracker.
    Initializes threads for client handling and cleanup.
    """
    print(f"[STARTING] Tracker is starting at {SERVER}:{PORT}")
    
    # Start the client handler thread
    threading.Thread(target=handle_client, daemon=True).start()
    
    # Start the cleanup thread to remove inactive seeders
    threading.Thread(target=remove_inactive_seeders, daemon=True).start()
    
    print(f"[LISTENING] Tracker is listening on {SERVER}:{PORT}")

    try:
        # Keep the main thread alive without consuming too much CPU
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Handle clean shutdown on Ctrl+C
        print("\n[STOPPING] Tracker shutting down...")
        tracker.close()  # Close the UDP socket
        exit(0)  # Exit with success code

# Entry point
start()