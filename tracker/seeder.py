import socket
import threading
import os
import time
import logging
import traceback

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
SEEDER_PORT = 7000
FORMAT = 'utf-8'
CHUNK_SIZE = 512 * 1024  # 512 KB in bytes

# Constant for number of chunks to send to leechers
CHUNKS_TO_BE_SENT = 7  # Change this value to control how many chunks to send

class SeederServer:
    def __init__(self, filename):
        self.filename = filename
        
        # UDP Socket for tracker communication
        self.seeder_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # TCP Socket for file sharing
        self.seeder_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.seeder_tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Disable timeout for TCP listen
        self.seeder_tcp.settimeout(None)
        
        logging.info(f"Binding TCP socket to {LOCAL_IP}:{SEEDER_PORT}")
        self.seeder_tcp.bind((LOCAL_IP, SEEDER_PORT))
        self.seeder_tcp.listen(5)

    def register_with_tracker(self):
        try:
            self.seeder_udp.sendto(f"REGISTER_SEEDER {self.filename} {SEEDER_PORT}".encode(FORMAT), TRACKER_ADDR)
            logging.info(f"Registered with tracker for file: {self.filename}")
            
            # Send the total number of chunks to the tracker
            total_chunks = max(1, os.path.getsize(self.filename) // CHUNK_SIZE + 1)
            self.seeder_udp.sendto(f"CHUNK_COUNT {total_chunks}".encode(FORMAT), TRACKER_ADDR)
            logging.info(f"Sent chunk count to tracker: {total_chunks}")
            
        except Exception as e:
            logging.error(f"Failed to register with tracker: {e}")
            logging.error(traceback.format_exc())

    def handle_client_connection(self, conn, addr):
        try:
            logging.debug(f"Starting connection handler for {addr}")
            
            # Set per-connection timeout
            conn.settimeout(30)
            
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
                    total_chunks = max(1, os.path.getsize(self.filename) // CHUNK_SIZE + 1)
                    conn.sendall(str(total_chunks).encode(FORMAT))
                    logging.info(f"Sent total chunks: {total_chunks}")

                elif cmd == "GET_CHUNK" and len(request) == 3:
                    chunk_id = int(request[2])
                    
                    if chunk_id >= CHUNKS_TO_BE_SENT:  # Only send chunks up to CHUNKS_TO_BE_SENT
                        logging.info(f"Reached chunk limit of {CHUNKS_TO_BE_SENT}. Not sending more chunks.")
                        break
                    
                    with open(self.filename, "rb") as f:
                        f.seek(chunk_id * CHUNK_SIZE)
                        chunk = f.read(CHUNK_SIZE)
                        
                        # Send in smaller portions to avoid blocking for too long
                        bytes_sent = 0
                        while bytes_sent < len(chunk):
                            sent = conn.send(chunk[bytes_sent:bytes_sent + 8192])
                            if sent == 0:
                                raise RuntimeError("Socket connection broken")
                            bytes_sent += sent
                            
                    logging.info(f"Sent chunk {chunk_id} ({bytes_sent} bytes)")
                
                elif cmd == "DONE":
                    logging.info(f"Client {addr} indicated completion")
                    break

        except socket.timeout:
            logging.info(f"Connection to {addr} timed out")
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
        logging.info(f"Seeder listening on {LOCAL_IP}:{SEEDER_PORT}")
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

def main():
    filename = "large_text_file.txt"
    seeder = SeederServer(filename)
    seeder.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Seeder stopped.")

if __name__ == "__main__":
    main()
