import socket

TRACKER_ADDR = ("<tracker_ip>", 6020)
FORMAT = 'utf-8'
CHUNK_SIZE = 512

filename = "sample.txt"
leecher_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
leecher_udp.sendto(f"REQUEST_SEEDERS {filename}".encode(FORMAT), TRACKER_ADDR)

data, _ = leecher_udp.recvfrom(1024)
seeders = data.decode(FORMAT).split()[1:]

if not seeders or seeders[0] == "NO_SEEDERS":
    print("No seeders available.")
    exit()

chunks = []
for seeder in seeders:
    ip, port = seeder.split(":")
    seeder_addr = (ip, int(port))

    tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_client.connect(seeder_addr)

    # Request total number of chunks
    tcp_client.sendall(f"GET_CHUNK_COUNT {filename}".encode(FORMAT))
    total_chunks = int(tcp_client.recv(1024).decode(FORMAT))

    # Download each chunk
    for chunk_id in range(total_chunks):
        tcp_client.sendall(f"GET_CHUNK {filename} {chunk_id}".encode(FORMAT))
        chunk = tcp_client.recv(CHUNK_SIZE)
        chunks.append(chunk)

    tcp_client.close()

# Reassemble the file
with open("downloaded_" + filename, "wb") as f:
    for chunk in chunks:
        f.write(chunk)

print(f"File {filename} downloaded successfully.")
