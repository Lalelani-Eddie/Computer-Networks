import socket
import logging
import time
import traceback
import os
import threading
import hashlib  # Added missing import

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
CONNECTION_TIMEOUT = 90  # Increased to 90 seconds

class FileLeecher:
    def __init__(self, filename):
        self.filename = filename
        self.leecher_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.output_file_lock = threading.Lock()  # Lock for file access
        self.total_chunks = 0  # Will be updated after getting seeder info
        self.missing_chunks = []  # Track any chunks that fail to download
        self.download_status = {}  # Track download status per chunk
        
    def get_seeders(self):
        try:
            logging.debug("Sending seeders request to tracker")
            self.leecher_udp.sendto(f"REQUEST_SEEDERS {self.filename}".encode(FORMAT), TRACKER_ADDR)

            self.leecher_udp.settimeout(CONNECTION_TIMEOUT)
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
                        'port': int(port),
                        'chunks': int(chunks),
                        'addr': f"{ip}:{port}"
                    })
                elif len(parts) == 2:
                    ip, port = parts[0], parts[1]
                    seeders.append({
                        'ip': ip,
                        'port': int(port),
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

    def download_chunk(self, tcp_client, chunk_id, is_last_chunk=False):
        """Download a single chunk with hash verification and return the chunk data"""
        try:
            logging.info(f"Requesting chunk {chunk_id}")
            tcp_client.sendall(f"GET_CHUNK {self.filename} {chunk_id}".encode(FORMAT))
            
            # First receive the chunk's hash (SHA-256 is 64 characters in hex)
            hash_data = b''
            while len(hash_data) < 64:  # SHA-256 hash is 64 characters in hex
                part = tcp_client.recv(64 - len(hash_data))
                if not part:
                    raise Exception("Connection closed while receiving hash")
                hash_data += part
            
            expected_hash = hash_data.decode(FORMAT)
            logging.debug(f"Received hash for chunk {chunk_id}: {expected_hash}")
            
            # Now receive chunk data
            chunk_data = b''
            start_time = time.time()
            
            while True:
                try:
                    part = tcp_client.recv(8192)
                    if not part:  # End of transmission
                        if len(chunk_data) > 0 or is_last_chunk:
                            # If we have data or it's the last chunk, we're done
                            break
                        else:
                            # Empty response for non-last chunk is unexpected
                            raise Exception("Received empty response for chunk")
                    
                    chunk_data += part
                    
                    # For non-last chunks, break when we have enough data
                    if not is_last_chunk and len(chunk_data) >= CHUNK_SIZE:
                        break
                        
                    # For last chunk, we keep receiving until connection is closed
                    elapsed = time.time() - start_time
                    if elapsed > 30:  # Prevent infinite loop
                        logging.warning(f"Chunk {chunk_id} download taking too long ({elapsed:.1f}s)")
                        break
                        
                except socket.timeout:
                    # Handle timeout during chunk download
                    if len(chunk_data) > 0:
                        logging.warning(f"Timeout while downloading chunk {chunk_id}, but received {len(chunk_data)} bytes")
                        break
                    else:
                        raise  # Re-raise timeout if no data received
            
            # Verify hash
            if len(chunk_data) > 0:
                calculated_hash = hashlib.sha256(chunk_data).hexdigest()
                if calculated_hash != expected_hash:
                    logging.error(f"Hash verification failed for chunk {chunk_id}")
                    logging.error(f"Expected: {expected_hash}")
                    logging.error(f"Calculated: {calculated_hash}")
                    return None  # Return None to indicate hash verification failure
                else:
                    logging.info(f"Hash verified for chunk {chunk_id}")
            
            return chunk_data
            
        except Exception as e:
            logging.error(f"Error downloading chunk {chunk_id}: {e}")
            return None
          
    def receive_chunk(self, conn, chunk_id):
        """Receive chunk and verify its hash"""
        try:
            # Receive the chunk's hash
            chunk_hash = conn.recv(64).decode(FORMAT)  # SHA-256 hash length is 64 hex characters
            
            # Receive the chunk data
            chunk_data = b''
            while len(chunk_data) < CHUNK_SIZE:
                part = conn.recv(8192)
                if not part:  # End of transmission
                    break
                chunk_data += part
            
            # Verify the chunk's hash
            calculated_hash = hashlib.sha256(chunk_data).hexdigest()
            if calculated_hash != chunk_hash:
                logging.error(f"Hash mismatch for chunk {chunk_id}. Expected {chunk_hash}, but got {calculated_hash}")
                return None  # Hash mismatch, indicate failure
            
            logging.info(f"Chunk {chunk_id} verified successfully")
            return chunk_data
        
        except Exception as e:
            logging.error(f"Error receiving chunk {chunk_id}: {e}")
            return None

    def download_chunks_from_seeder(self, seeder_info, start_chunk, end_chunk):
        tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            ip, port = seeder_info['ip'], int(seeder_info['port'])
            seeder_socket_addr = (ip, port)

            logging.debug(f"Attempting to connect to seeder: {seeder_socket_addr}")
            tcp_client.settimeout(CONNECTION_TIMEOUT)

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
            
            # Update total chunks for the file
            self.total_chunks = max(self.total_chunks, total_chunks)
            
            # Tell seeder which chunk range we want
            tcp_client.sendall(f"SET_CHUNK_RANGE {self.filename} {start_chunk} {end_chunk}".encode(FORMAT))
            response = tcp_client.recv(1024).decode(FORMAT)
            if response != "RANGE_ACCEPTED":
                logging.error(f"Seeder rejected chunk range: {response}")
                return
            
            logging.info(f"Seeder accepted chunk range from {start_chunk} to {end_chunk}")

            # Download each chunk
            for chunk_id in range(start_chunk, end_chunk + 1):
                # Check if this is the last chunk in the file
                is_last_chunk = (chunk_id == total_chunks - 1)
                
                # Try to download the chunk with retries
                for retry in range(MAX_RETRIES):
                    try:
                        chunk_data = self.download_chunk(tcp_client, chunk_id, is_last_chunk)
                        
                        if chunk_data and len(chunk_data) > 0:
                            # Write the chunk to file
                            if self.write_chunk_to_file(chunk_id, chunk_data):
                                break  # Success, move to next chunk
                        
                        # If we get here, the chunk download failed
                        if retry < MAX_RETRIES - 1:
                            logging.warning(f"Retry {retry+1} for chunk {chunk_id}")
                            time.sleep(RETRY_DELAY)
                        else:
                            logging.error(f"Failed to download chunk {chunk_id} after {MAX_RETRIES} retries")
                            self.missing_chunks.append(chunk_id)
                            
                    except socket.timeout:
                        logging.warning(f"Timeout on retry {retry+1} for chunk {chunk_id}")
                        if retry < MAX_RETRIES - 1:
                            time.sleep(RETRY_DELAY)
                        else:
                            logging.error(f"Failed due to timeout after {MAX_RETRIES} retries")
                            self.missing_chunks.append(chunk_id)

            # Notify seeder we're done
            try:
                tcp_client.sendall(f"DONE {self.filename}".encode(FORMAT))
                logging.info(f"Chunks {start_chunk}-{end_chunk} download completed")
            except Exception as e:
                logging.warning(f"Error sending DONE message: {e}")

        except Exception as e:
            logging.error(f"Error during download from seeder {seeder_info['addr']}: {e}")
            logging.error(traceback.format_exc())
            
            # Add failed chunks to missing chunks list
            for chunk_id in range(start_chunk, end_chunk + 1):
                if chunk_id not in self.download_status:
                    self.missing_chunks.append(chunk_id)
                    
        finally:
            try:
                tcp_client.close()
                logging.debug("Closed TCP connection")
            except:
                pass

    def write_chunk_to_file(self, chunk_id, chunk_data):
        """Write a chunk to the output file"""
        if not chunk_data:
            logging.error(f"Cannot write empty chunk {chunk_id}")
            return False
            
        try:
            with self.output_file_lock:
                with open(f"leeched_{self.filename}", "r+b" if os.path.exists(f"leeched_{self.filename}") else "wb") as f:
                    f.seek(chunk_id * CHUNK_SIZE)
                    f.write(chunk_data)
                
                self.download_status[chunk_id] = len(chunk_data)
                logging.info(f"Chunk {chunk_id} written: {len(chunk_data)} bytes")
                return True
                
        except Exception as e:
            logging.error(f"Error writing chunk {chunk_id}: {e}")
            return False

    def retry_missing_chunks(self, seeders):
        """Retry downloading any missing chunks"""
        if not self.missing_chunks:
            return True
            
        logging.info(f"Attempting to retry {len(self.missing_chunks)} missing chunks")
        
        # Try each seeder for the missing chunks
        for seeder in seeders:
            if not self.missing_chunks:
                break  # All chunks downloaded
                
            # Connect to seeder
            tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_client.settimeout(CONNECTION_TIMEOUT)
            
            try:
                ip, port = seeder['ip'], int(seeder['port'])
                tcp_client.connect((ip, port))
                
                # Request total chunk count
                tcp_client.sendall(f"GET_CHUNK_COUNT {self.filename}".encode(FORMAT))
                total_chunks_data = tcp_client.recv(1024)
                total_chunks = int(total_chunks_data.decode(FORMAT))
                
                # Set chunk range for the missing chunks
                chunk_range = sorted(self.missing_chunks)
                start_chunk, end_chunk = min(chunk_range), max(chunk_range)
                
                tcp_client.sendall(f"SET_CHUNK_RANGE {self.filename} {start_chunk} {end_chunk}".encode(FORMAT))
                response = tcp_client.recv(1024).decode(FORMAT)
                
                if response != "RANGE_ACCEPTED":
                    continue  # Try next seeder
                
                # Download each missing chunk
                for chunk_id in list(self.missing_chunks):  # Create a copy of the list
                    is_last_chunk = (chunk_id == total_chunks - 1)
                    
                    chunk_data = self.download_chunk(tcp_client, chunk_id, is_last_chunk)
                    if chunk_data and len(chunk_data) > 0:
                        if self.write_chunk_to_file(chunk_id, chunk_data):
                            self.missing_chunks.remove(chunk_id)
                
            except Exception as e:
                logging.error(f"Error during retry with seeder {seeder['addr']}: {e}")
            finally:
                tcp_client.close()
                
        return len(self.missing_chunks) == 0

    def verify_download(self):
        """Verify if the download is complete"""
        if self.missing_chunks:
            logging.warning(f"Download incomplete. Missing chunks: {self.missing_chunks}")
            return False
            
        try:
            file_size = os.path.getsize(f"leeched_{self.filename}")
            logging.info(f"Download complete. File size: {file_size} bytes")
            
            # For the last chunk, we don't know the exact size, so we can't verify precisely
            return True
            
        except Exception as e:
            logging.error(f"Error verifying download: {e}")
            return False

    def get_chunk_distribution(self, seeders, total_chunks):
        """Calculate how many chunks each seeder should provide"""
        num_seeders = len(seeders)
        
        # Base chunks per seeder (integer division)
        base_chunks_per_seeder = total_chunks // num_seeders
        
        # Calculate remainder
        remainder = total_chunks % num_seeders
        
        # Distribute chunks to seeders
        chunk_distribution = []
        chunk_index = 0
        
        for i in range(num_seeders):
            # Give one extra chunk to the first 'remainder' seeders
            if i < remainder:
                num_chunks = base_chunks_per_seeder + 1
            else:
                num_chunks = base_chunks_per_seeder
                
            # Calculate start and end chunks
            start_chunk = chunk_index
            end_chunk = chunk_index + num_chunks - 1
            chunk_index += num_chunks
            
            chunk_distribution.append({
                'seeder': seeders[i],
                'start_chunk': start_chunk,
                'end_chunk': end_chunk,
                'num_chunks': num_chunks
            })
            
        return chunk_distribution

    def download_file(self):
        # Get seeders from tracker
        seeders = self.get_seeders()
        
        # Verify we have at least 3 seeders (keeping current setup requirement)
        if not seeders or len(seeders) < 3:
            logging.error(f"Need at least 3 seeders, but only found {len(seeders)}. Exiting.")
            return False
        
        # Connect to first seeder to get total chunk count
        try:
            tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_client.settimeout(CONNECTION_TIMEOUT)
            
            ip, port = seeders[0]['ip'], int(seeders[0]['port'])
            tcp_client.connect((ip, port))
            
            # Request total chunk count
            tcp_client.sendall(f"GET_CHUNK_COUNT {self.filename}".encode(FORMAT))
            total_chunks_data = tcp_client.recv(1024)
            total_chunks = int(total_chunks_data.decode(FORMAT))
            self.total_chunks = total_chunks
            
            logging.info(f"Total chunks for file: {total_chunks}")
            tcp_client.close()
            
        except Exception as e:
            logging.error(f"Failed to get total chunk count: {e}")
            return False
        
        # Create and initialize output file
        with open(f"leeched_{self.filename}", "wb") as f:
            # We don't know the final size yet, so we'll create an empty file
            pass
        
        # Calculate chunk distribution
        chunk_distribution = self.get_chunk_distribution(seeders, total_chunks)
        
        logging.info(f"Chunk distribution: {[(d['seeder']['addr'], d['start_chunk'], d['end_chunk']) for d in chunk_distribution]}")
        
        # Create threads for each seeder
        threads = []
        for distribution in chunk_distribution:
            seeder = distribution['seeder']
            start_chunk = distribution['start_chunk']
            end_chunk = distribution['end_chunk']
            
            thread = threading.Thread(
                target=self.download_chunks_from_seeder,
                args=(seeder, start_chunk, end_chunk)
            )
            threads.append(thread)
            logging.info(f"Created thread for seeder {seeder['addr']} for chunks {start_chunk}-{end_chunk}")
            
        # Start all threads
        for thread in threads:
            thread.start()
            
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
            
        logging.info("All download threads completed")
        
        # Retry missing chunks if any
        if self.missing_chunks:
            logging.warning(f"Some chunks are missing. Retrying...")
            self.retry_missing_chunks(seeders)
        
        # Verify the download
        return self.verify_download()

def main():
    filename = "large_text_file.txt"
    leecher = FileLeecher(filename)
    success = leecher.download_file()
    
    if success:
        print(f"Successfully downloaded {filename}")
    else:
        print(f"Download of {filename} was incomplete")

if __name__ == "__main__":
    main()