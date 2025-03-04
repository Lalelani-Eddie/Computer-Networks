from socket import *
import time

# Define the server details
serverPort = 12000
serverSocket = socket(AF_INET, SOCK_DGRAM)
serverSocket.bind(('', serverPort))

print("The tracker server is ready to receive")

# Dictionary to store seeders {filename: [list of seeder IPs]}
seeders = {}

while True:
    # Receive message from any seeder or leecher
    message, clientAddress = serverSocket.recvfrom(2048)
    message = message.decode()
    
    parts = message.split()  # Expecting messages like "REGISTER filename" or "REQUEST filename"
    
    if len(parts) < 2:
        continue  # Ignore invalid messages
    
    command, filename = parts[0], parts[1]
    
    if command == "REGISTER":
        # Register seeder
        if filename not in seeders:
            seeders[filename] = []
        if clientAddress[0] not in seeders[filename]:
            seeders[filename].append(clientAddress[0])
        print(f"Seeder {clientAddress[0]} registered for {filename}")
    
    elif command == "REQUEST":
        # Return list of seeders for requested file
        if filename in seeders and seeders[filename]:
            response = " ".join(seeders[filename])
        else:
            response = "NO_SEEDERS"
        serverSocket.sendto(response.encode(), clientAddress)
        print(f"Sent seeders for {filename} to {clientAddress}")
