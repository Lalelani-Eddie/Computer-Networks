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
CHUNK_SIZE = 512 * 1024  # 512 KB in bytes
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
            
            # Longer timeout for UDP
            self.leecher_udp.settimeout(30)
            
            data, _ = self.leecher_udp.recvfrom(1024)
            seeders_response = data.decode(FORMAT).split()
            
            logging.debug(f"Seeders response: {seeders_response}")
            
            if seeders_response[0] == "NO_SEEDERS":
                logging.error("No seeders available.")
                return []
            
            return seeders_response[1:]
        
        except socket.timeout:
            logging.error("Timeout while requesting seeders")
            return []
        except Exception as e:
            logging.error(f"Error getting seeders: {e}")
            logging.error(traceback.format_exc())
            return []

    def download_from_seeder(self, seeder_addr):
        tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        try:
            ip, port = seeder_addr.split(":")
            seeder_socket_addr = (ip, int(port))
            
            logging.debug(f"Attempting to connect to seeder: {seeder_socket_addr}")
            
            # Set a reasonable timeout for operations
            tcp_client.settimeout(30)
            
            # Connect with retries
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
            
            # Get total chunks - first request on this connection
            logging.debug("Requesting chunk count")
            tcp_client.sendall(f"GET_CHUNK_COUNT {self.filename}".encode(FORMAT))
            total_chunks_data = tcp_client.recv(1024)
            if not total_chunks_data:
                raise ValueError("Empty response when requesting chunk count")
                
            total_chunks = int(total_chunks_data.decode(FORMAT))
            logging.info(f"Total chunks: {total_chunks}")
            
            # Download chunks - subsequent requests on same connection
            chunks = []
            for chunk_id in range(total_chunks):
                logging.debug(f"Downloading chunk {chunk_id}")
                
                # Send chunk request
                tcp_client.sendall(f"GET_CHUNK {self.filename} {chunk_id}".encode(FORMAT))
                
                # Receive chunk data with retries
                for retry in range(MAX_RETRIES):
                    try:
                        # Initialize buffer for collecting chunk data
                        chunk_buffer = bytearray()
                        bytes_received = 0
                        
                        # Keep receiving until we get the full chunk
                        # 512 KB might need multiple recv calls
                        while bytes_received < CHUNK_SIZE:
                            part = tcp_client.recv(min(8192, CHUNK_SIZE - bytes_received))
                            if not part:  # Connection closed or end of file
                                if bytes_received == 0:
                                    raise ValueError("Empty chunk received")
                                break  # Got partial chunk (possibly end of file)
                                
                            chunk_buffer.extend(part)
                            bytes_received += len(part)
                            
                            # If we're reading a small file and the chunk is complete
                            file_size = os.path.getsize(self.filename) if os.path.exists(self.filename) else CHUNK_SIZE
                            if bytes_received < CHUNK_SIZE and file_size < CHUNK_SIZE:
                                break
                        
                        if bytes_received > 0:
                            chunks.append(bytes(chunk_buffer))
                            logging.debug(f"Successfully downloaded chunk {chunk_id} ({bytes_received} bytes)")
                            break
                        else:
                            raise ValueError("No data received")
                            
                    except Exception as chunk_err:
                        logging.warning(f"Chunk {chunk_id} download retry {retry + 1}: {chunk_err}")
                        if retry == MAX_RETRIES - 1:
                            logging.error(f"Failed to download chunk {chunk_id}: {chunk_err}")
                            logging.error(traceback.format_exc())
                            raise
                        time.sleep(RETRY_DELAY)
            
            # Tell seeder we're done
            try:
                tcp_client.sendall(f"DONE {self.filename}".encode(FORMAT))
            except:
                # Not critical if this fails
                pass
                
            return chunks
        
        except Exception as e:
            logging.error(f"Download error from {seeder_addr}: {e}")
            logging.error(traceback.format_exc())
            return None
        finally:
            try:
                tcp_client.close()
            except:
                pass

    def download_file(self):
        # Get list of seeders
        seeders = self.get_seeders()
        
        if not seeders:
            logging.error("No seeders found.")
            return False
        
        # Try downloading from each seeder
        for seeder in seeders:
            logging.info(f"Attempting to download from seeder: {seeder}")
            chunks = self.download_from_seeder(seeder)
            
            if chunks:
                # Save downloaded file
                try:
                    with open(f"downloaded_{self.filename}", "wb") as f:
                        for chunk in chunks:
                            f.write(chunk)
                    logging.info(f"File {self.filename} downloaded successfully.")
                    return True
                except Exception as e:
                    logging.error(f"Error saving file: {e}")
                    logging.error(traceback.format_exc())
        
        logging.error("Failed to download file from all seeders.")
        return False

def main():
    filename = "sample.txt"
    leecher = FileLeecher(filename)
    leecher.download_file()

if __name__ == "__main__":
    main()