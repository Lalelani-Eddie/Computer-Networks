# transitioner.py
import socket
import logging
import threading
import traceback



FORMAT = "utf-8"    
CONNECTION_TIMEOUT = 120
TRACKER_ADDR = ("localhost", 6020)



class Transitioner:
    def __init__(self, filename, total_chunks, leecher_udp):
        self.filename = filename
        self.total_chunks = total_chunks
        self.leecher_udp = leecher_udp

    def start_seeder_mode(self):
        """
        Transition from leecher to seeder mode after successful file download.
        This method:
        1. Registers with the tracker as a seeder
        2. Starts a TCP server to handle chunk requests from other peers
        3. Creates a separate thread to handle seeder operations
        """
        logging.info("Transitioning to seeder mode")
        
        # Create a TCP socket for serving chunks
        seeder_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        seeder_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind to available port
        host = socket.gethostbyname(socket.gethostname())
        port = 0  # Let OS assign an available port
        seeder_socket.bind((host, port))
        _, actual_port = seeder_socket.getsockname()  # Get the assigned port
        
        # Register with the tracker as a seeder
        self._register_as_seeder(host, actual_port)
        
        # Start listening for incoming connections
        seeder_thread = threading.Thread(target=self._run_seeder_server, 
                                        args=(seeder_socket,))
        seeder_thread.daemon = True  # Allow program to exit even if thread is running
        seeder_thread.start()
        
        logging.info(f"Seeder mode active on {host}:{actual_port}")
        return True

    def _register_as_seeder(self, host, port):

        try:
            # Send registration message to tracker
            register_msg = f"REGISTER_SEEDER {self.filename} {host} {port} {self.total_chunks}"
            logging.info(f"Registering as seeder: {register_msg}")
        
            self.leecher_udp.sendto(register_msg.encode(FORMAT), TRACKER_ADDR)
        
            # Wait for confirmation from tracker
            self.leecher_udp.settimeout(CONNECTION_TIMEOUT)
            try:
                data, _ = self.leecher_udp.recvfrom(1024)
                response = data.decode(FORMAT)
            
                if response == "REGISTRATION_SUCCESSFUL":
                    logging.info("Successfully registered as seeder with tracker")
                    return True
                else:
                    logging.error(f"Failed to register as seeder: {response}")
                    return False
            except ConnectionResetError:
                logging.error("Connection to tracker was forcibly closed by the remote host.")
                return False
            except socket.timeout:
                logging.error("Timeout while waiting for tracker response.")
                return False
            except Exception as e:
                logging.error(f"Error registering as seeder: {e}")
                logging.error(traceback.format_exc())
                return False
        except Exception as e:
            logging.error(f"Unexpected error in _register_as_seeder: {e}")
            return False

    def _register_as_seeder(self, host, port):
        """
        Register with the tracker as a seeder for the file.
        
        Args:
            host (str): IP address to register
            port (int): Port number to register
        """
        try:
            # Send registration message to tracker
            register_msg = f"REGISTER_SEEDER {self.filename} {host} {port} {self.total_chunks}"
            logging.info(f"Registering as seeder: {register_msg}")
            
            self.leecher_udp.sendto(register_msg.encode(FORMAT), TRACKER_ADDR)
            
            # Wait for confirmation from tracker
            self.leecher_udp.settimeout(CONNECTION_TIMEOUT)
            data, _ = self.leecher_udp.recvfrom(1024)
            response = data.decode(FORMAT)
            
            if response == "REGISTRATION_SUCCESSFUL":
                logging.info("Successfully registered as seeder with tracker")
                return True
            else:
                logging.error(f"Failed to register as seeder: {response}")
                return False
                
        except socket.timeout:
            logging.error("Timeout while registering as seeder")
            return False
        except Exception as e:
            logging.error(f"Error registering as seeder: {e}")
            logging.error(traceback.format_exc())
            return False

    def _run_seeder_server(self, seeder_socket):
        """
        Run the seeder server to handle chunk requests from peers.
        
        Args:
            seeder_socket (socket): Socket to accept connections on
        """
        try:
            seeder_socket.listen(5)  # Allow up to 5 pending connections
            logging.info("Seeder server started, listening for connections")
            
            while True:
                try:
                    # Accept incoming connection
                    client_socket, client_addr = seeder_socket.accept()
                    logging.info(f"Connection accepted from {client_addr}")
                    
                    # Handle client request in a separate thread
                    client_thread = threading.Thread(target=self._handle_client_request,
                                                   args=(client_socket, client_addr))
                    client_thread.daemon = True
                    client_thread.start()
                    
                except Exception as e:
                    logging.error(f"Error accepting connection: {e}")
                    continue
                    
        except Exception as e:
            logging.error(f"Seeder server error: {e}")
            logging.error(traceback.format_exc())
        finally:
            try:
                seeder_socket.close()
                logging.info("Seeder socket closed")
            except:
                pass

    def _handle_client_request(self, client_socket, client_addr):
        """
        Handle requests from a connected client.
        
        Args:
            client_socket (socket): Socket connected to the client
            client_addr (tuple): Client's address information
        """
        try:
            client_socket.settimeout(CONNECTION_TIMEOUT)
            
            while True:
                # Receive request from client
                data = client_socket.recv(1024)
                if not data:
                    break  # Client disconnected
                    
                request = data.decode(FORMAT)
                logging.debug(f"Received request: {request} from {client_addr}")
                
                parts = request.split()
                cmd = parts[0] if parts else ""
                
                # Handle different request types
                if cmd == "GET_CHUNK_COUNT":
                    self._handle_chunk_count_request(client_socket, parts)
                elif cmd == "SET_CHUNK_RANGE":
                    self._handle_set_chunk_range(client_socket, parts)
                elif cmd == "GET_CHUNK":
                    self._handle_get_chunk_request(client_socket, parts)
                elif cmd == "DONE":
                    logging.info(f"Client {client_addr} completed download")
                    break
                else:
                    logging.warning(f"Unknown command from {client_addr}: {cmd}")
                    client_socket.sendall("UNKNOWN_COMMAND".encode(FORMAT))
                    
        except socket.timeout:
            logging.warning(f"Connection to {client_addr} timed out")
        except Exception as e:
            logging.error(f"Error handling client {client_addr}: {e}")
            logging.error(traceback.format_exc())
        finally:
            try:
                client_socket.close()
                logging.debug(f"Closed connection to {client_addr}")
            except:
                pass