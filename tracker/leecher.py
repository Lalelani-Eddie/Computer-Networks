import socket
import logging
import time
import traceback
import os

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("leecher_debug.log"),
                        logging.StreamHandler()
                    ])

# Configuration
TRACKER_ADDR = (socket.gethostbyname(socket.gethostname()), 6020)
FORMAT = 'utf-8'
CHUNK_SIZE = 512 * 1024  # 512 KB
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
CHUNKS_TO_RECEIVE = 7  # Must match CHUNKS_TO_BE_SENT in seeder

class FileLeecher:
    def __init__(self, filename):
        self.filename = filename
        self.leecher_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def get_seeders(self):
        try:
            logging.debug("Sending seeders request to tracker")
            self.leecher_udp.sendto(f"REQUEST_SEEDERS {self.filename}".encode(FORMAT), TRACKER_ADDR)

            self.leecher_udp.settimeout(30)
            data, _ = self.leecher_udp.recvfrom(1024)
            seeders_response = data.decode(FORMAT).split()

            logging.debug(f"Seeders response: {seeders_response}")

            if seeders_response[0] == "NO_SEEDERS":
                logging.error("No seeders available.")
                return []

            seeders = []
            for seeder_info in seeders_response[1:]:
                parts = seeder_info.split(":")
                if len(parts) >= 3:
                    ip, port, chunks = parts[0], parts[1], parts[2]
                    seeders.append({
                        'ip': ip,
                        'port': port,
                        'chunks': int(chunks),
                        'addr': f"{ip}:{port}"
                    })
                elif len(parts) == 2:
                    ip, port = parts[0], parts[1]
                    seeders.append({
                        'ip': ip,
                        'port': port,
                        'chunks': 0,
                        'addr': f"{ip}:{port}"
                    })

            return seeders

        except socket.timeout:
            logging.error("Timeout while requesting seeders")
            return []
        except Exception as e:
            logging.error(f"Error getting seeders: {e}")
            logging.error(traceback.format_exc())
            return []

    def download_chunks(self, seeder_info, num_chunks_to_request=CHUNKS_TO_RECEIVE):
        tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            ip, port = seeder_info['ip'], int(seeder_info['port'])
            seeder_socket_addr = (ip, port)

            logging.debug(f"Attempting to connect to seeder: {seeder_socket_addr}")
            tcp_client.settimeout(30)

            for attempt in range(MAX_RETRIES):
                try:
                    tcp_client.connect(seeder_socket_addr)
                    logging.info(f"Connected to seeder {seeder_socket_addr}")
                    break
                except Exception as connect_err:
                    logging.warning(f"Connection attempt {attempt + 1} failed: {connect_err}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                    else:
                        raise

            # Request total chunk count
            tcp_client.sendall(f"GET_CHUNK_COUNT {self.filename}".encode(FORMAT))
            total_chunks_data = tcp_client.recv(1024)
            total_chunks = int(total_chunks_data.decode(FORMAT))
            logging.info(f"Total chunks reported by seeder: {total_chunks}")

            # Determine number of chunks to receive
            chunks_to_get = min(num_chunks_to_request, total_chunks)

            with open(f"leeched_{self.filename}", "wb") as f:
                for chunk_id in range(chunks_to_get):
                    logging.info(f"Requesting chunk {chunk_id}")
                    tcp_client.sendall(f"GET_CHUNK {self.filename} {chunk_id}".encode(FORMAT))
                    chunk_data = b''
                    while True:
                        part = tcp_client.recv(8192)
                        if not part:
                            break
                        chunk_data += part
                        if len(chunk_data) >= CHUNK_SIZE:
                            break
                    f.write(chunk_data)
                    logging.info(f"Chunk {chunk_id} written: {len(chunk_data)} bytes")

            # Notify seeder we’re done
            tcp_client.sendall(f"DONE {self.filename}".encode(FORMAT))
            logging.info("File download completed")

        except Exception as e:
            logging.error(f"Error during download: {e}")
            logging.error(traceback.format_exc())
        finally:
            tcp_client.close()
            logging.debug("Closed TCP connection")

def main():
    filename = "large_text_file.txt"
    leecher = FileLeecher(filename)

    seeders = leecher.get_seeders()
    if not seeders:
        logging.error("No seeders found. Exiting.")
        return

    for seeder in seeders:
        leecher.download_chunks(seeder)
        break  # Just download from the first seeder for now

if __name__ == "__main__":
    main()
