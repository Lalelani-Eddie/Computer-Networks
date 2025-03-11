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

            # Parse the seeder information (now includes chunk count)
            seeders = []
            for seeder_info in seeders_response[1:]:
                parts = seeder_info.split(":")
                if len(parts) >= 3:  # New format with chunk count: ip:port:chunks
                    ip, port, chunks = parts[0], parts[1], parts[2]
                    seeders.append({
                        'ip': ip,
                        'port': port,
                        'chunks': int(chunks),
                        'addr': f"{ip}:{port}"
                    })
                elif len(parts) == 2:  # Old format without chunk count: ip:port
                    ip, port = parts[0], parts[1]
                    seeders.append({
                        'ip': ip,
                        'port': port,
                        'chunks': 0,  # Unknown number of chunks
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

    def download_chunks(self, seeder_info, num_chunks_to_request=2):
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

            # Get total chunks
            tcp_client.sendall(f"GET_CHUNK_COUNT {self.filename}".encode(FORMAT))
            total_chunks_data = tcp_client.recv(1024)
            total_chunks = int(total_chunks_data.decode(FORMAT))
            logging.info(f"Total chunks: {total_chunks}")

            # Adjust num_chunks_to_request based on total available
            num_chunks_to_request = min(num_chunks_to_request, total_chunks)
            
            # Request chunks
            chunks = []
            print(f"{num_chunks_to_request} chunks from seeder at {seeder_info['addr']} being requested")

            for chunk_id in range(num_chunks_to_request):
                try:
                    tcp_client.sendall(f"GET_CHUNK {self.filename} {chunk_id}".encode(FORMAT))
                    chunk_buffer = bytearray()
                    bytes_received = 0

                    while bytes_received < CHUNK_SIZE:
                        try:
                            part = tcp_client.recv(min(8192, CHUNK_SIZE - bytes_received))
                            if not part:
                                # Connection closed by seeder
                                logging.warning(f"Connection closed by seeder while downloading chunk {chunk_id}")
                                break
                            
                            chunk_buffer.extend(part)
                            bytes_received += len(part)

                            file_size = os.path.getsize(self.filename) if os.path.exists(self.filename) else CHUNK_SIZE
                            if bytes_received < CHUNK_SIZE and file_size < CHUNK_SIZE:
                                # We've probably received the entire file if it's smaller than CHUNK_SIZE
                                break
                        except socket.timeout:
                            logging.warning(f"Timeout while receiving data for chunk {chunk_id}")
                            break
                        except ConnectionResetError:
                            logging.warning(f"Connection reset by seeder while downloading chunk {chunk_id}")
                            break

                    if bytes_received > 0:
                        chunks.append(bytes(chunk_buffer))
                        logging.debug(f"Successfully downloaded chunk {chunk_id} ({bytes_received} bytes)")
                    else:
                        logging.warning(f"No data received for chunk {chunk_id}, seeder may have limited chunk sharing")
                        # Don't raise an error, just stop trying to get more chunks
                        break
                    
                except Exception as chunk_err:
                    logging.warning(f"Error downloading chunk {chunk_id}: {chunk_err}")
                    # Continue to next chunk rather than failing completely
                    break

            print(f"{len(chunks)} chunks have been successfully received from seeder at {seeder_info['addr']}")
            return chunks

        except Exception as e:
            logging.error(f"Download error from {seeder_info['addr']}: {e}")
            logging.error(traceback.format_exc())
            return []
        finally:
            try:
                tcp_client.close()
            except:
                pass

    def download_file(self):
        seeders = self.get_seeders()
        if not seeders:
            logging.error("No seeders found.")
            return False

        seeder = seeders[0]  # Use only the first seeder
        logging.info(f"Attempting to download chunks from seeder: {seeder['addr']} (has {seeder['chunks']} chunks)")
        chunks = self.download_chunks(seeder)

        if chunks:
            try:
                with open(f"partial_{self.filename}", "wb") as f:
                    for chunk in chunks:
                        f.write(chunk)
                logging.info(f"Downloaded {len(chunks)} chunks of {self.filename} successfully.")
                return True
            except Exception as e:
                logging.error(f"Error saving file: {e}")
                logging.error(traceback.format_exc())
                return False
        else:
            logging.error("Failed to download any chunks from seeder.")
            return False

def main():
    filename = "large_text_file.txt"
    leecher = FileLeecher(filename)
    leecher.download_file()

if __name__ == "__main__":
    main()