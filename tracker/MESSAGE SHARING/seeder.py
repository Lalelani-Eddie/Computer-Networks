import socket
import threading
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Get local IP address
LOCAL_IP = socket.gethostbyname(socket.gethostname())
TRACKER_IP = LOCAL_IP
TRACKER_ADDR = (TRACKER_IP, 6020)
SEEDER_PORT = 7000
FORMAT = 'utf-8'
CHUNK_SIZE = 512  # keeping for compatibility

class SeederServer:
    def __init__(self):
        # UDP Socket for tracker communication
        self.seeder_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # TCP Socket for message sharing
        self.seeder_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.seeder_tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        self.seeder_tcp.bind((LOCAL_IP, SEEDER_PORT))
        self.seeder_tcp.listen(5)

    def register_with_tracker(self):
        try:
            # Register as a "seeder" but for messages
            self.seeder_udp.sendto(f"REGISTER_SEEDER messages {SEEDER_PORT}".encode(FORMAT), TRACKER_ADDR)
            logging.info("Registered with tracker for messaging")
        except Exception as e:
            logging.error(f"Failed to register with tracker: {e}")

    def handle_client_connection(self, conn, addr):
        try:
            # Receive message
            message = conn.recv(1024).decode(FORMAT)
            logging.info(f"Received message from {addr}: {message}")
            
            # Optional: Echo back or process message
            response = f"Seeder received: {message}"
            conn.send(response.encode(FORMAT))
        
        except Exception as e:
            logging.error(f"Error handling connection from {addr}: {e}")
        finally:
            conn.close()

    def listen_for_messages(self):
        logging.info(f"Seeder listening on {LOCAL_IP}:{SEEDER_PORT}")
        while True:
            try:
                conn, addr = self.seeder_tcp.accept()
                logging.info(f"New connection from {addr}")
                
                # Handle in a separate thread
                client_thread = threading.Thread(
                    target=self.handle_client_connection, 
                    args=(conn, addr)
                )
                client_thread.start()
                
            except Exception as e:
                logging.error(f"Error accepting connection: {e}")

    def start(self):
        # Register with tracker
        self.register_with_tracker()

        # Start listening thread
        listening_thread = threading.Thread(
            target=self.listen_for_messages, 
            daemon=True
        )
        listening_thread.start()

def main():
    seeder = SeederServer()
    seeder.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Seeder stopped.")

if __name__ == "__main__":
    main()