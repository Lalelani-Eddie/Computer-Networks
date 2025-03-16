# P2P File Sharing System

This is a simple peer-to-peer file sharing system that consists of three components: a tracker, seeders, and leechers. The system allows for efficient file distribution by chunking files and downloading from multiple sources simultaneously.

## Setup Instructions

### Prerequisites

- Python 3.6 or higher
- No external dependencies required (only standard library modules are used)

### Files

- `tracker.py`: Central coordinator that keeps track of available seeders
- `seeder.py`: Shares files with other peers in the network
- `leecher.py`: Downloads files from available seeders
- `large_text_file.txt`: An example file to share (you may use any file)

## Running the System

Follow these steps in order to set up and run the complete P2P system:

### Step 1: Start the Tracker

The tracker must be started first as it coordinates all peer activities:

```bash
python tracker.py
```

The tracker will start on the default port 6020 and display a message confirming it's running:
```
[STARTING] Tracker is starting at 192.168.1.X:6020
[LISTENING] Tracker is listening on 192.168.1.X:6020
```

### Step 2: Start the Seeders

You need to start at least one seeder (three are recommended for optimal performance) to share files:

```bash
# Start first seeder on default port 7000
python seeder.py -f large_text_file.txt -p 7000

# Start second seeder on port 7001
python seeder.py -f large_text_file.txt -p 7001

# Start third seeder on port 7002
python seeder.py -f large_text_file.txt -p 7002
```

Arguments:
- `-f, --file`: Specifies the file to share (default: large_text_file.txt)
- `-p, --port`: Specifies the port to listen on (default: 7000)

Each seeder will display a confirmation message:
```
Starting seeder for file 'large_text_file.txt' on port 7000
Seeder running on port 7000 for file large_text_file.txt
Press Ctrl+C to stop
```

### Step 3: Start the Leecher

Once the tracker and at least one seeder are running, you can start the leecher to download the file:

```bash
python leecher.py
```

The file name is currently hardcoded as "large_text_file.txt" in the leecher. If you want to download a different file, you'll need to modify the `filename` variable in the `main()` function of `leecher.py`.

The leecher will connect to the tracker, get a list of seeders, and download the file in chunks. A successful download will display:
```
Successfully downloaded large_text_file.txt
```

The downloaded file will be saved as "leeched_large_text_file.txt" in the same directory.

## System Architecture

1. **Tracker**: Maintains a registry of active seeders and their files
   - Uses UDP for communication
   - Handles seeder registration and heartbeats
   - Responds to leecher requests for seeder information

2. **Seeder**: Hosts files and serves them in chunks
   - Registers with the tracker
   - Serves file chunks over TCP connections
   - Calculates and sends SHA-256 hashes for data verification
   - Sends heartbeats to the tracker to indicate availability

3. **Leecher**: Downloads files from multiple seeders
   - Requests seeder information from the tracker
   - Downloads chunks in parallel from multiple seeders
   - Verifies chunk integrity using SHA-256 hashes
   - Assembles chunks into the complete file

## Troubleshooting

- If the leecher cannot find seeders, ensure the tracker is running first
- If a download fails, try restarting the leecher
- Check the log files (`seeder_debug.log` and `leecher_debug.log`) for detailed error information
- Ensure all components are running on the same network
- If using a personal firewall, ensure the ports (6020, 7000, etc.) are open

## Notes

- The system uses a chunk size of 512KB
- The leecher requires at least 3 seeders for optimal performance
- Seeders send heartbeats every 30 seconds
- The connection timeout is set to 90 seconds
- Log files are created in the same directory as the scripts