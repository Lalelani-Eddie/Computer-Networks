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
# Sets up logging to both file and console with timestamp and severity level
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[ 
                        logging.FileHandler("seeder_debug.log"),  # Log to file
                        logging.StreamHandler()                   # Log to console
                    ])

# Network configuration constants
LOCAL_IP = socket.gethostbyname(socket.gethostname())  # Get local machine's IP address
TRACKER_IP = LOCAL_IP                                  # Use local IP for tracker (assumes tracker runs on same machine)
TRACKER_ADDR = (TRACKER_IP, 6020)                      # Tracker address tuple (IP, port)
DEFAULT_SEEDER_PORT = 7000                             # Default port for the seeder service
FORMAT = 'utf-8'                                       # Encoding format for text messages
CHUNK_SIZE = 512 * 1024                                # Size of each file chunk (512 KB)
CONNECTION_TIMEOUT = 90                                # Client connection timeout in seconds

# Helper function to calculate the hash for a chunk
def calculate_chunk_hash(chunk):
    """
    Calculate SHA-256 hash of the given chunk.
    
    Args:
        chunk (bytes): The file chunk data
        
    Returns:
        str: Hexadecimal representation of the SHA-256 hash
    """
    sha256 = hashlib.sha256()
    sha256.update(chunk)
    return sha256.hexdigest()

class SeederServer:
    """
    Seeder server that shares files in a P2P network.
    Communicates with a tracker to register available files and
    serves file chunks to peers upon request.
    """
    
    def __init__(self, filename, port):
        """
        Initialize the seeder server.
        
        Args:
            filename (str): Path to the file to be shared
            port (int): TCP port to listen on for peer connections
        """
        self.filename = filename
        self.port = port
        
        # UDP Socket for tracker communication (registration and heartbeats)
        self.seeder_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # TCP Socket for file sharing with peers
        self.seeder_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.seeder_tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow reuse of address
        
        # Disable timeout for TCP listen socket (blocking accept())
        self.seeder_tcp.settimeout(None)
        
        logging.info(f"Binding TCP socket to {LOCAL_IP}:{self.port}")
        self.seeder_tcp.bind((LOCAL_IP, self.port))  # Bind to the specified port
        self.seeder_tcp.listen(5)  # Allow up to 5 queued connections
        
        # Calculate total chunks in the file and the size of the last chunk
        if os.path.exists(self.filename):
            file_size = os.path.getsize(self.filename)
            # Calculate total chunks, ensuring at least 1 chunk even for empty files
            self.total_chunks = max(1, (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE)
            # Calculate last chunk size (remainder or full chunk size if evenly divisible)
            self.last_chunk_size = file_size % CHUNK_SIZE or CHUNK_SIZE
            logging.info(f"File {filename} has {self.total_chunks} chunks (last chunk: {self.last_chunk_size} bytes)")
        else:
            logging.error(f"File {filename} does not exist!")
            sys.exit(1)  # Exit if file doesn't exist

    def register_with_tracker(self):
        """
        Register this seeder with the tracker.
        Sends the filename, port, and chunk count to the tracker.
        Also starts a heartbeat thread to maintain registration.
        """
        try:
            # Send registration message with filename and listening port
            self.seeder_udp.sendto(f"REGISTER_SEEDER {self.filename} {self.port}".encode(FORMAT), TRACKER_ADDR)
            logging.info(f"Registered with tracker for file: {self.filename}")
            
            # Send the total number of chunks to the tracker
            self.seeder_udp.sendto(f"CHUNK_COUNT {self.total_chunks}".encode(FORMAT), TRACKER_ADDR)
            logging.info(f"Sent chunk count to tracker: {self.total_chunks}")
            
            # Start heartbeat thread to periodically notify tracker that we're still alive
            threading.Thread(target=self.send_heartbeat, daemon=True).start()
            
        except Exception as e:
            logging.error(f"Failed to register with tracker: {e}")
            logging.error(traceback.format_exc())
    
    def send_heartbeat(self):
        """
        Send periodic heartbeat messages to the tracker.
        Runs in a separate thread to maintain registration with the tracker.
        """
        while True:
            try:
                # Send ALIVE message to prevent being removed from tracker's active seeder list
                self.seeder_udp.sendto(f"ALIVE {self.filename}".encode(FORMAT), TRACKER_ADDR)
                logging.debug("Sent heartbeat to tracker")
            except Exception as e:
                logging.error(f"Failed to send heartbeat: {e}")
            time.sleep(30)  # Send heartbeat every 30 seconds

    def handle_client_connection(self, conn, addr):
        """
        Handle a single client connection.
        Processes client requests and sends requested file chunks.
        
        Args:
            conn (socket.socket): Connected socket object for communication with client
            addr (tuple): Client address tuple (IP, port)
        """
        try:
            logging.debug(f"Starting connection handler for {addr}")
            
            # Set per-connection timeout to prevent hanging connections
            conn.settimeout(CONNECTION_TIMEOUT)
            
            # Track chunk range for this connection (default: all chunks)
            start_chunk = 0
            end_chunk = self.total_chunks - 1
            
            while True:  # Keep accepting commands until client disconnects or error
                # Receive request from client
                request_data = conn.recv(1024)
                if not request_data:  # Client closed connection
                    logging.debug(f"Client {addr} closed connection")
                    break
                    
                # Parse the request
                request = request_data.decode(FORMAT).split()
                logging.debug(f"Received request: {request}")
                
                # Validate request format
                if len(request) < 2:
                    logging.warning(f"Invalid request from {addr}")
                    continue  # Wait for next request instead of closing
                
                # Extract command and filename
                cmd, fname = request[0], request[1]
                logging.info(f"Processing request from {addr}: {cmd} {fname}")

                # Handle GET_CHUNK_COUNT command - tell client how many chunks are in the file
                if cmd == "GET_CHUNK_COUNT" and fname == self.filename:
                    conn.sendall(str(self.total_chunks).encode(FORMAT))
                    logging.info(f"Sent total chunks: {self.total_chunks}")
                
                # Handle SET_CHUNK_RANGE command - client wants to download a specific range of chunks
                elif cmd == "SET_CHUNK_RANGE" and len(request) == 4:
                    start_chunk = int(request[2])
                    end_chunk = int(request[3])
                    
                    # Validate the requested range is within file bounds
                    if start_chunk < 0 or end_chunk >= self.total_chunks or start_chunk > end_chunk:
                        conn.sendall("RANGE_REJECTED".encode(FORMAT))
                        logging.warning(f"Rejected invalid chunk range {start_chunk}-{end_chunk}")
                    else:
                        conn.sendall("RANGE_ACCEPTED".encode(FORMAT))
                        logging.info(f"Accepted chunk range {start_chunk}-{end_chunk} for {addr}")
                
                # Handle GET_CHUNK command - send the requested chunk to the client
                elif cmd == "GET_CHUNK" and len(request) == 3:
                    chunk_id = int(request[2])
                    
                    # Validate chunk_id is within the agreed range
                    if chunk_id < start_chunk or chunk_id > end_chunk:
                        logging.warning(f"Chunk {chunk_id} outside of agreed range {start_chunk}-{end_chunk}")
                        conn.sendall("CHUNK_OUT_OF_RANGE".encode(FORMAT))
                        continue
                    
                    # Check if this is the last chunk (special handling for EOF)
                    is_last_chunk = (chunk_id == self.total_chunks - 1)
                    
                    try:    
                        with open(self.filename, "rb") as f:
                            # Jump to the correct position in the file
                            f.seek(chunk_id * CHUNK_SIZE)
                            # Read the chunk data
                            chunk = f.read(CHUNK_SIZE)
                            
                            # Calculate chunk hash for integrity verification
                            chunk_hash = calculate_chunk_hash(chunk)
                            
                            # Send the chunk hash first (for client verification)
                            conn.sendall(chunk_hash.encode(FORMAT))
                            logging.debug(f"Sent chunk hash for chunk {chunk_id}: {chunk_hash}")
                            
                            # Send the chunk data in smaller portions to avoid blocking
                            # and to handle very large chunks more efficiently
                            bytes_sent = 0
                            while bytes_sent < len(chunk):
                                sent = conn.send(chunk[bytes_sent:bytes_sent + 8192])  # Send up to 8KB at a time
                                if sent == 0:
                                    raise RuntimeError("Socket connection broken")
                                bytes_sent += sent
                                
                            # Send an empty packet to signal end of chunk if it's the last chunk
                            # This helps the client recognize EOF
                            if is_last_chunk:
                                time.sleep(0.1)  # Small delay to ensure client processes data
                                conn.send(b'')  # Send an empty chunk to signal end of data
                                 
                        logging.info(f"Sent chunk {chunk_id} ({bytes_sent} bytes){' [LAST CHUNK]' if is_last_chunk else ''}")
                    except Exception as e:
                        logging.error(f"Error sending chunk {chunk_id}: {e}")
                        logging.error(traceback.format_exc())
                
                # Handle DONE command - client is finished downloading
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
                conn.close()  # Ensure socket is closed
                logging.debug(f"Closed connection to {addr}")
            except:
                pass  # Ignore errors during close

    def listen_for_requests(self):
        """
        Main listening loop for the seeder.
        Accepts incoming connections and spawns handler threads.
        """
        logging.info(f"Seeder listening on {LOCAL_IP}:{self.port}")
        while True:
            try:
                # Block and wait for connections
                conn, addr = self.seeder_tcp.accept()
                logging.info(f"Accepted new connection from {addr}")
                
                # Handle each connection in a separate thread to support multiple clients
                client_thread = threading.Thread(
                    target=self.handle_client_connection, 
                    args=(conn, addr)
                )
                client_thread.start()
                
            except Exception as e:
                logging.error(f"Error in listening loop: {e}")
                logging.error(traceback.format_exc())
                time.sleep(1)  # Prevent tight error loop consuming CPU

    def start(self):
        """
        Start the seeder server.
        Registers with tracker and begins listening for client requests.
        """
        # Register with tracker
        self.register_with_tracker()

        # Start listening thread for client connections
        listening_thread = threading.Thread(
            target=self.listen_for_requests, 
            daemon=True  # Thread will exit when main thread exits
        )
        listening_thread.start()
        logging.info(f"Seeder started successfully on port {self.port}")
        print(f"Seeder running on port {self.port} for file {self.filename}")
        print("Press Ctrl+C to stop")

def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(description='File Seeder')
    parser.add_argument('-p', '--port', type=int, default=DEFAULT_SEEDER_PORT,
                        help=f'Port to listen on (default: {DEFAULT_SEEDER_PORT})')
    parser.add_argument('-f', '--file', type=str, default="large_text_file.txt",
                        help='File to seed (default: large_text_file.txt)')
    return parser.parse_args()

def main():
    """
    Main entry point for the seeder application.
    Parses arguments, creates and starts the seeder server.
    """
    args = parse_arguments()
    
    # Check if file exists before creating the seeder
    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' does not exist!")
        return
    
    print(f"Starting seeder for file '{args.file}' on port {args.port}")
    seeder = SeederServer(args.file, args.port)
    seeder.start()

    # Keep main thread alive until Ctrl+C
    try:
        while True:
            time.sleep(1)  # Sleep to prevent high CPU usage
    except KeyboardInterrupt:
        logging.info("Seeder stopped.")
        print("\nSeeder stopped.")

# Entry point when script is executed directly
if __name__ == "__main__":
    main()