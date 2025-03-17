# P2P File Sharing System

This is a peer-to-peer file sharing system that implements a distributed approach to file distribution through a tracker-based architecture. The system divides files into chunks and allows downloading from multiple sources simultaneously, improving download speeds and distribution efficiency.

## System Architecture

The system consists of three main components that work together:

### 1. Tracker (`tracker.py`)
- Central coordinator that maintains a registry of active seeders
- Uses UDP for lightweight, connectionless communication
- Functions:
  - Handles seeder registration and maintains their status
  - Processes heartbeat messages to track seeder availability
  - Responds to leecher requests with lists of available seeders
  - Performs automatic cleanup of inactive seeders
  - Maintains metadata about available files and chunk counts

### 2. Seeder (`seeder.py`)
- Hosts complete files and serves them in chunks to peers
- Uses TCP for reliable file transfer
- Features:
  - Registers with the tracker and sends periodic heartbeats
  - Calculates and sends SHA-256 hashes for data integrity verification
  - Handles multiple concurrent client connections
  - Supports specific chunk range requests for efficient downloading
  - Implements timeout mechanisms to prevent resource exhaustion

### 3. Leecher (`leecher.py`)
- Downloads files from multiple seeders simultaneously
- Implements a hybrid approach:
  - Uses UDP to communicate with the tracker
  - Uses TCP to download file chunks from seeders
- Features:
  - Requests seeder information from the tracker
  - Downloads chunks in parallel from multiple seeders
  - Distributes download load across available seeders
  - Verifies chunk integrity using SHA-256 hashes
  - Assembles chunks into the complete file
  - Retries failed chunk downloads
  - Transitions to seeder mode after successful download

## Advanced Features

- **Chunk Verification**: SHA-256 hash verification ensures data integrity
- **Parallel Downloads**: Simultaneous downloads from multiple seeders
- **Automatic Seeding**: Leechers automatically become seeders after completing downloads
- **Heartbeat System**: Maintains up-to-date seeder availability information
- **Fault Tolerance**: Retries failed downloads and handles network errors
- **Thread Safety**: Proper synchronization for concurrent operations
- **Comprehensive Logging**: Detailed logs for debugging and monitoring

## Setup Instructions

### Prerequisites

- Python 3.6 or higher
- No external dependencies required (only standard library modules are used)
- Network connectivity between all peers

### Files

- `tracker.py`: Central coordinator for the P2P network
- `seeder.py`: Shares files with other peers
- `leecher.py`: Downloads files from available seeders
- `transitioner.py`: (Used internally) Handles transition from leecher to seeder

## Running the System

### Step 1: Start the Tracker

```bash
python tracker.py
```

The tracker will start on port 6020 by default. You should see:
```
[STARTING] Tracker is starting at 192.168.X.X:6020
[LISTENING] Tracker is listening on 192.168.X.X:6020
```

### Step 2: Start One or More Seeders

For optimal performance, start multiple seeders on different ports:

```bash
# Start first seeder
python seeder.py -f large_text_file.txt -p 7000

# Start additional seeders (optional but recommended)
python seeder.py -f large_text_file.txt -p 7001
python seeder.py -f large_text_file.txt -p 7002
```

Arguments:
- `-f, --file`: Specifies the file to share (default: large_text_file.txt)
- `-p, --port`: Specifies the port to listen on (default: 7000)

Each seeder will display:
```
Starting seeder for file 'large_text_file.txt' on port 7000
Seeder running on port 7000 for file large_text_file.txt
Press Ctrl+C to stop
```

### Step 3: Start the Leecher

Once the tracker and at least one seeder are running:

```bash
python leecher.py
```

The leecher will:
1. Connect to the tracker and get a list of active seeders
2. Download the file in chunks from multiple seeders simultaneously
3. Verify the integrity of each downloaded chunk
4. Assemble the complete file as "leeched_large_text_file.txt"
5. Automatically transition to seeder mode after successful download

You can monitor the download progress in the console and log files.

## Configuration

The system can be customized by modifying the constants in each file:

### Common Settings
- `CHUNK_SIZE`: Size of each file chunk (default: 512KB)
- `FORMAT`: Encoding format for messages (default: 'utf-8')

### Tracker Settings
- `PORT`: Port number for tracker service (default: 6020)

### Seeder Settings
- `DEFAULT_SEEDER_PORT`: Default port for seeder service (default: 7000)
- `CONNECTION_TIMEOUT`: Client connection timeout (default: 90 seconds)

### Leecher Settings
- `MAX_RETRIES`: Maximum number of retries for failed operations (default: 3)
- `RETRY_DELAY`: Delay between retries (default: 2 seconds)
- `CONNECTION_TIMEOUT`: Network connection timeout (default: 300 seconds)

## Troubleshooting

### Common Issues
- **Leecher can't find seeders**: Ensure the tracker is running first and seeders are registered
- **Download fails**: Check for network issues, firewall settings, or try restarting the leecher
- **Timeout errors**: Increase the `CONNECTION_TIMEOUT` value if on a slow network
- **Chunk mismatch errors**: Verify the file hasn't been modified after the seeder started

### Log Files
- Detailed logs are saved in:
  - `seeder_debug.log`: For seeder operations
  - `leecher_debug.log`: For leecher operations
- Check these logs for detailed error information and debugging

### Firewall Configuration
- Ensure the following ports are open:
  - UDP port 6020 for tracker communication
  - TCP ports used by seeders (default: 7000, 7001, etc.)
  - Any dynamically assigned ports for leecher-to-seeder connections

## Performance Optimization

- Start multiple seeders for the same file to improve download speeds
- Run the system on a local network for faster transfers
- Adjust `CHUNK_SIZE` based on your network conditions and file sizes
- For very large files, increase the connection timeout values

## Implementation Details

- The system uses a chunk size of 512KB by default
- Seeders send heartbeats every 30 seconds
- The tracker removes inactive seeders after 60 seconds of no heartbeat
- Leechers retry failed downloads up to 3 times
- SHA-256 hashing is used for chunk verification
- Thread safety is ensured using locks for file operations

## Extending the System

The modular design allows for easy extension:

- Add a GUI for better user experience
- Implement bandwidth throttling
- Add support for file discovery and search
- Implement encrypted transfers for security
- Add support for resuming interrupted downloads