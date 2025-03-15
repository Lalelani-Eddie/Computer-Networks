import socket
import threading
import os
import time
import logging
import traceback
import argparse
import sys
import hashlib

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[ 
                        logging.FileHandler("seeder_debug.log"),
                        logging.StreamHandler()
                    ])

# Get local IP address
LOCAL_IP = socket.gethostbyname(socket.gethostname())
TRACKER_IP = LOCAL_IP
TRACKER_ADDR = (TRACKER_IP, 6020)
DEFAULT_SEEDER_PORT = 7000
FORMAT = 'utf-8'
CHUNK_SIZE = 512 * 1024  # 512 KB in bytes
CONNECTION_TIMEOUT = 90  # 1 minute 30 seconds

# Helper function to calculate the hash for a chunk
def calculate_chunk_hash(chunk):
    """Calculate SHA-256 hash of the given chunk"""
    sha256 = hashlib.sha256()
    sha256.update(chunk)
    return sha256.hexdigest()

class SeederServer:
    def __init__(self, filename, port):
        self.filename = filename
        self.port = port
        
        # UDP Socket for tracker communication
        self.seeder_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # TCP Socket for file sharing
        self.seeder_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.seeder_tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Disable timeout for TCP listen
        self.seeder_tcp.settimeout(None)
        
        logging.info(f"Binding TCP socket to {LOCAL_IP}:{self.port}")
        self.seeder_tcp.bind((LOCAL_IP, self.port))
        self.seeder_tcp.listen(5)
        
        # Calculate total chunks in the file
        if os.path.exists(self.filename):
            file_size = os.path.getsize(self.filename)
            self.total_chunks = max(1, (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE)
            self.last_chunk_size = file_size % CHUNK_SIZE or CHUNK_SIZE
            logging.info(f"File {filename} has {self.total_chunks} chunks (last chunk: {self.last_chunk_size} bytes)")
        else:
            logging.error(f"File {filename} does not exist!")
            sys.exit(1)

    def register_with_tracker(self):
        try:
            self.seeder_udp.sendto(f"REGISTER_SEEDER {self.filename} {self.port}".encode(FORMAT), TRACKER_ADDR)
            logging.info(f"Registered with tracker for file: {self.filename}")
            
            # Send the total number of chunks to the tracker
            self.seeder_udp.sendto(f"CHUNK_COUNT {self.total_chunks}".encode(FORMAT), TRACKER_ADDR)
            logging.info(f"Sent chunk count to tracker: {self.total_chunks}")
            
            # Start heartbeat thread
            threading.Thread(target=self.send_heartbeat, daemon=True).start()
            
        except Exception as e:
            logging.error(f"Failed to register with tracker: {e}")
            logging.error(traceback.format_exc())
    
    def send_heartbeat(self):
        while True:
            try:
                self.seeder_udp.sendto(f"ALIVE {self.filename}".encode(FORMAT), TRACKER_ADDR)
                logging.debug("Sent heartbeat to tracker")
            except Exception as e:
                logging.error(f"Failed to send heartbeat: {e}")
            time.sleep(30)  # Send heartbeat every 30 seconds

    def handle_client_connection(self, conn, addr):
        try:
            logging.debug(f"Starting connection handler for {addr}")
            
            # Set per-connection timeout
            conn.settimeout(CONNECTION_TIMEOUT)
            
            # Track chunk range for this connection
            start_chunk = 0
            end_chunk = self.total_chunks - 1
            
            while True:  # Keep accepting commands until client disconnects or error
                # Receive request
                request_data = conn.recv(1024)
                if not request_data:  # Client closed connection
                    logging.debug(f"Client {addr} closed connection")
                    break
                    
                request = request_data.decode(FORMAT).split()
                logging.debug(f"Received request: {request}")
                
                if len(request) < 2:
                    logging.warning(f"Invalid request from {addr}")
                    continue  # Wait for next request instead of closing

                cmd, fname = request[0], request[1]
                logging.info(f"Processing request from {addr}: {cmd} {fname}")

                if cmd == "GET_CHUNK_COUNT" and fname == self.filename:
                    conn.sendall(str(self.total_chunks).encode(FORMAT))
                    logging.info(f"Sent total chunks: {self.total_chunks}")
                
                elif cmd == "SET_CHUNK_RANGE" and len(request) == 4:
                    start_chunk = int(request[2])
                    end_chunk = int(request[3])
                    
                    # Validate range
                    if start_chunk < 0 or end_chunk >= self.total_chunks or start_chunk > end_chunk:
                        conn.sendall("RANGE_REJECTED".encode(FORMAT))
                        logging.warning(f"Rejected invalid chunk range {start_chunk}-{end_chunk}")
                    else:
                        conn.sendall("RANGE_ACCEPTED".encode(FORMAT))
                        logging.info(f"Accepted chunk range {start_chunk}-{end_chunk} for {addr}")
                
                elif cmd == "GET_CHUNK" and len(request) == 3:
                    chunk_id = int(request[2])
                    
                    # Validate chunk_id is within the agreed range
                    if chunk_id < start_chunk or chunk_id > end_chunk:
                        logging.warning(f"Chunk {chunk_id} outside of agreed range {start_chunk}-{end_chunk}")
                        conn.sendall("CHUNK_OUT_OF_RANGE".encode(FORMAT))
                        continue
                    
                    # Check if this is the last chunk
                    is_last_chunk = (chunk_id == self.total_chunks - 1)
                    
                    try:    
                        with open(self.filename, "rb") as f:
                            f.seek(chunk_id * CHUNK_SIZE)
                            chunk = f.read(CHUNK_SIZE)
                            
                            # Calculate chunk hash
                            chunk_hash = calculate_chunk_hash(chunk)
                            
                            # Send the chunk along with its hash
                            conn.sendall(chunk_hash.encode(FORMAT))  # Send hash first
                            logging.debug(f"Sent chunk hash for chunk {chunk_id}: {chunk_hash}")
                            
                            # Send the chunk data in smaller portions to avoid blocking for too long
                            bytes_sent = 0
                            while bytes_sent < len(chunk):
                                sent = conn.send(chunk[bytes_sent:bytes_sent + 8192])
                                if sent == 0:
                                    raise RuntimeError("Socket connection broken")
                                bytes_sent += sent
                                
                            # Send an empty packet to signal end of chunk if it's the last chunk
                            if is_last_chunk:
                                time.sleep(0.1)  # Small delay to ensure client processes data
                                conn.send(b'')  # Send an empty chunk to signal end of data
                                 
                        logging.info(f"Sent chunk {chunk_id} ({bytes_sent} bytes){' [LAST CHUNK]' if is_last_chunk else ''}")
                    except Exception as e:
                        logging.error(f"Error sending chunk {chunk_id}: {e}")
                        logging.error(traceback.format_exc())
                
                elif cmd == "DONE":
                    logging.info(f"Client {addr} indicated completion")
                    break

        except socket.timeout:
            logging.info(f"Connection to {addr} timed out after {CONNECTION_TIMEOUT} seconds")
        except ConnectionResetError:
            logging.info(f"Connection to {addr} was reset")
        except Exception as e:
            logging.error(f"Error handling client {addr}: {e}")
            logging.error(traceback.format_exc())
        finally:
            try:
                conn.close()
                logging.debug(f"Closed connection to {addr}")
            except:
                pass

    def listen_for_requests(self):
        logging.info(f"Seeder listening on {LOCAL_IP}:{self.port}")
        while True:
            try:
                # Block and wait for connections
                conn, addr = self.seeder_tcp.accept()
                logging.info(f"Accepted new connection from {addr}")
                
                # Handle each connection in a separate thread
                client_thread = threading.Thread(
                    target=self.handle_client_connection, 
                    args=(conn, addr)
                )
                client_thread.start()
                
            except Exception as e:
                logging.error(f"Error in listening loop: {e}")
                logging.error(traceback.format_exc())
                time.sleep(1)  # Prevent tight error loop

    def start(self):
        # Register with tracker
        self.register_with_tracker()

        # Start listening thread
        listening_thread = threading.Thread(
            target=self.listen_for_requests, 
            daemon=True
        )
        listening_thread.start()
        logging.info(f"Seeder started successfully on port {self.port}")
        print(f"Seeder running on port {self.port} for file {self.filename}")
        print("Press Ctrl+C to stop")

def parse_arguments():
    parser = argparse.ArgumentParser(description='File Seeder')
    parser.add_argument('-p', '--port', type=int, default=DEFAULT_SEEDER_PORT,
                        help=f'Port to listen on (default: {DEFAULT_SEEDER_PORT})')
    parser.add_argument('-f', '--file', type=str, default="large_text_file.txt",
                        help='File to seed (default: large_text_file.txt)')
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    # Check if file exists
    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' does not exist!")
        return
    
    print(f"Starting seeder for file '{args.file}' on port {args.port}")
    seeder = SeederServer(args.file, args.port)
    seeder.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Seeder stopped.")
        print("\nSeeder stopped.")

if __name__ == "__main__":
    main()
