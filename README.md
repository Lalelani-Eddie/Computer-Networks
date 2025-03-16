# P2P File Sharing System

A simple peer-to-peer file sharing system consisting of three main components: tracker, seeder, and leecher. This system allows users to distribute and download files across multiple connections for efficient data transfer.

## Overview

This P2P system uses a hybrid architecture:
- A centralized tracker to coordinate peers
- Multiple seeders to serve file chunks
- Leechers that download chunks from multiple seeders simultaneously

The system supports chunked file transfers with hash verification to ensure data integrity.

## Components

### Tracker (`tracker.py`)

The tracker is the central coordination point that:
- Maintains a registry of active seeders
- Provides seeder information to leechers
- Tracks which files are available on the network
- Monitors seeder heartbeats to maintain an up-to-date list

```bash
python tracker.py
```

### Seeder (`seeder.py`)

Seeders host files and serve chunks to leechers. Each seeder:
- Registers with the tracker
- Calculates file chunks and hashes
- Serves specific chunk ranges to leechers
- Sends regular heartbeats to the tracker

```bash
python seeder.py -f <filename> -p <port>
```

Arguments:
- `-f, --file`: Filename to seed (default: large_text_file.txt)
- `-p, --port`: Port to listen on (default: 7000)

### Leecher (`leecher.py`)

Leechers download files by:
- Requesting seeder information from the tracker
- Downloading chunks from multiple seeders in parallel
- Verifying chunk integrity using SHA-256 hashes
- Assembling chunks into a complete file

```bash
python leecher.py
```

## Features

- **Parallel Downloads**: Distributes download tasks across multiple seeders
- **Integrity Verification**: Uses SHA-256 hashes to verify chunk integrity
- **Fault Tolerance**: Retries failed chunk downloads
- **Chunked Transfer**: Splits files into 512KB chunks for efficient transfer
- **Connection Timeout Handling**: Gracefully handles network issues
- **Logging**: Comprehensive debug and info logging

## System Flow

1. The tracker starts and listens for UDP messages
2. Seeders register with the tracker and provide file chunk information
3. Leechers request seeder information from the tracker
4. Leechers establish TCP connections with multiple seeders
5. Each seeder serves a specific chunk range
6. The leecher verifies each chunk with its hash
7. The leecher assembles all chunks into the final file

## Technical Details

- **Chunk Size**: 512KB (configurable)
- **Hash Algorithm**: SHA-256
- **Protocols**: UDP for tracker communication, TCP for file transfers
- **Connection Timeout**: 90 seconds
- **Heartbeat Interval**: 30 seconds

## Requirements

- Python 3.6+
- Standard library modules only (no external dependencies)

## Example Output

A successful download will show log entries similar to:
```
2025-03-16 21:50:25,873 - INFO - All download threads completed
2025-03-16 21:50:25,873 - INFO - Download complete. File size: 10577202 bytes
Successfully downloaded large_text_file.txt
```

## Error Handling

The system handles various error conditions:
- Network timeouts
- Seeder unavailability
- Hash verification failures
- Connection resets
- File access issues

## Limitations

- Currently optimized for text files
- Requires at least 3 active seeders
- No encryption or authentication mechanisms
- No bandwidth throttling