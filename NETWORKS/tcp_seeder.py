import socket

# Tracker Configuration
TRACKER_IP = "127.0.0.1"  # Trackers' IP
TRACKER_PORT = 12000  # Tracker's UDP port
FILENAME = input("Enter the name of the file you wan to share?")

def get_seeders():
    """Requests the list of seeders from the tracker via UDP."""
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    message = f"REQUEST {FILENAME}".encode()
    
    udp_socket.sendto(message, (TRACKER_IP, TRACKER_PORT))
    seeders_data, _ = udp_socket.recvfrom(1024)  # Receive list of seeders
    udp_socket.close()
    
    seeders = seeders_data.decode().split(",") if seeders_data else []
    return seeders

def download_file_from_seeder(seeder_ip):
    """Connects to a seeder over TCP and downloads the file in chunks."""
    seeder_port = 5000  # Default port for seeders
    try:
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.connect((seeder_ip, seeder_port))
        tcp_socket.send(FILENAME.encode())  # Request file
        
        with open(f"downloaded_{FILENAME}", "wb") as file:
            while chunk := tcp_socket.recv(1024):  # Receive file in chunks
                file.write(chunk)

        tcp_socket.close()
        print(f"Downloaded '{FILENAME}' from {seeder_ip}")
        return True  # Success
    except Exception as e:
        print(f"Failed to connect to seeder {seeder_ip}: {e}")
        return False

def start_leecher():
    """Gets the list of seeders and downloads the file from one of them."""
    seeders = get_seeders()
    if not seeders:
        print("No seeders found for the requested file.")
        return

    print(f"Available seeders: {seeders}")

    for seeder_ip in seeders:
        if download_file_from_seeder(seeder_ip.strip()):
            break  # Stop after successfully downloading

if __name__ == "__main__":
    start_leecher()
