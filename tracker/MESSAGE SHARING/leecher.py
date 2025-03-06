import socket
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
TRACKER_ADDR = (socket.gethostbyname(socket.gethostname()), 6020)
FORMAT = 'utf-8'
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

class MessageLeecher:
    def __init__(self):
        self.leecher_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
    def get_seeders(self):
        try:
            # Request seeders for messages
            self.leecher_udp.sendto("REQUEST_SEEDERS messages".encode(FORMAT), TRACKER_ADDR)
            
            self.leecher_udp.settimeout(30)
            
            data, _ = self.leecher_udp.recvfrom(1024)
            seeders_response = data.decode(FORMAT).split()
            
            if seeders_response[0] == "NO_SEEDERS":
                logging.error("No seeders available.")
                return []
            
            return seeders_response[1:]
        
        except socket.timeout:
            logging.error("Timeout while requesting seeders")
            return []
        except Exception as e:
            logging.error(f"Error getting seeders: {e}")
            return []

    def send_message(self, seeder_addr, message):
        tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        try:
            ip, port = seeder_addr.split(":")
            seeder_socket_addr = (ip, int(port))
            
            # Connect to seeder
            tcp_client.connect(seeder_socket_addr)
            logging.info(f"Connected to seeder {seeder_socket_addr}")
            
            # Send message
            tcp_client.send(message.encode(FORMAT))
            
            # Receive response
            response = tcp_client.recv(1024).decode(FORMAT)
            logging.info(f"Seeder response: {response}")
            
            return True
        
        except Exception as e:
            logging.error(f"Error sending message to {seeder_addr}: {e}")
            return False
        finally:
            tcp_client.close()

    def communicate(self):
        # Get list of seeders
        seeders = self.get_seeders()
        
        if not seeders:
            logging.error("No seeders found.")
            return False
        
        # Try sending message to first seeder
        message = input("Enter message to send: ")
        
        for seeder in seeders:
            logging.info(f"Attempting to send message to seeder: {seeder}")
            if self.send_message(seeder, message):
                return True
        
        logging.error("Failed to send message to any seeder.")
        return False

def main():
    leecher = MessageLeecher()
    
    # Continuous messaging
    while True:
        leecher.communicate()
        
        # Optional: Ask if user wants to continue
        cont = input("Send another message? (y/n): ").lower()
        if cont != 'y':
            break

if __name__ == "__main__":
    main()