# UDP Tracker for P2P File Sharing

## Overview
This UDP Tracker is a central server that helps coordinate peer-to-peer (P2P) file sharing. It maintains a list of available **seeders** (file providers) and responds to **leechers** (file downloaders) requesting file sources.

## Features
- **Registers Seeders:** Seeders announce files they can provide.
- **Responds to Leechers:** Provides a list of seeders hosting a requested file.
- **Tracks Active Seeders:** Stores and updates seeder IP addresses.

## How It Works
1. **Start the Tracker:** The tracker runs as a UDP server, waiting for messages.
2. **Seeder Registers a File:** A seeder sends a `REGISTER filename` message.
3. **Leecher Requests a File:** A leecher sends a `REQUEST filename` message.
4. **Tracker Responds:** Sends back a list of seeders hosting the file.

## Installation & Setup
### Prerequisites
- Python 3

### Running the Tracker
1. Save the tracker script as `udp_tracker.py`.
2. Run the tracker using:
   ```sh
   python udp_tracker.py
   ```
3. The tracker will now listen for UDP messages on port **12000**.

## Seeder Usage (File Providers)
A **seeder** (file provider) should send the following UDP message to register a file:
```
REGISTER myfile.txt
```
The tracker will store the seeder’s IP and the file it provides.

## Leecher Usage (File Downloaders)
A **leecher** (file downloader) should send a request to find available seeders:
```
REQUEST myfile.txt
```
The tracker will reply with a list of IP addresses of seeders hosting `myfile.txt`.

## Expected Responses
- **If seeders exist:** The tracker returns a space-separated list of seeder IPs.
- **If no seeders are available:** The tracker replies with `NO_SEEDERS`.

## Notes
- The tracker must be running before seeders register or leechers request files.
- Seeders should periodically re-register to ensure they remain discoverable.

## Next Steps
- Implement the **TCP Seeder** to serve files.
- Implement the **TCP Leecher** to download chunks from multiple seeders.

---
Developed for CSC3002 – Networks Assignment 2025

