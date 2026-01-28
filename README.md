# Encrypted Messaging with Trusted Server

Secure messaging system implementing a key distribution protocol inspired by Needham-Schroeder, developed as part of the Cryptographic Protocols TP2 course at ENSIBS.

## Architecture

```
┌─────────────┐                    ┌─────────────┐
│   Client A  │◄──── AES-256 ────►│   Client B  │
│  (RSA-2048) │                    │  (RSA-2048) │
└──────┬──────┘                    └──────┬──────┘
       │                                  │
       │    ┌───────────────────┐        │
       └───►│  Server (KDC)     │◄───────┘
            │  Session key      │
            │  distribution     │
            └───────────────────┘
```

## Cryptographic Protocol

### Algorithms Used

| Component | Algorithm | Key Size |
|-----------|-----------|----------|
| Asymmetric encryption | RSA-OAEP | 2048 bits |
| Symmetric encryption | AES-CBC | 256 bits |
| Signature | RSA-PSS | 2048 bits |
| Hashing | SHA-256 | 256 bits |
| Padding (AES) | PKCS7 | - |

### Session Establishment Flow

1. **Registration**: Each client generates an RSA-2048 key pair and registers its public key with the server
2. **Session Request**: Client A requests a session with Client B
3. **Key Generation**: The server generates a random AES-256 key
4. **Distribution**: The server encrypts the AES key with each client's RSA public key (OAEP)
5. **Establishment**: Clients decrypt the AES key and can communicate securely

### Message Security

- **Confidentiality**: Messages encrypted with AES-256-CBC with random IV
- **Authenticity**: Each message is signed with RSA-PSS (SHA-256)
- **Integrity**: The signature ensures the message has not been altered

## Installation

### Prerequisites

- Python 3.8+
- pip

### Dependencies

```bash
pip install flask cryptography requests
```

## Usage

### 1. Start the Trusted Server

```bash
python server.py
```

The server listens on port 5000.

### 2. Start the Clients

In separate terminals:

```bash
# Terminal 1 - Alice
python client.py alice 5001

# Terminal 2 - Bob
python client.py bob 5002
```

### 3. Establish Communication

From Alice's terminal:

```
/list                  # Display available clients
/connect bob           # Establish a secure session with Bob
Hello Bob!             # Send an encrypted message
```

### Available Commands

| Command | Description |
|---------|-------------|
| `/list` | List registered clients |
| `/connect <id>` | Establish a session with a client |
| `/sessions` | Display active sessions |
| `/switch <id>` | Switch current session |
| `/history [id]` | Display message history |
| `/quit` | Close the client |

### Web Interface

Each client exposes a web interface accessible at:

```
http://127.0.0.1:<port>
```

## Project Structure

```
TP2/
├── server.py           # Key Distribution Center (KDC)
├── client.py           # Client entry point
├── secure_client.py    # Main client logic
├── crypto_utils.py     # Cryptographic functions
├── history.py          # History management
├── index.html          # Web interface (home)
├── chat.html           # Web interface (chat)
├── keys/               # Key storage (generated)
└── history_<id>/       # Conversation history (generated)
```

## Server API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/register` | POST | Register a client with its public key |
| `/clients` | GET | List registered clients |
| `/get_public_key/<id>` | GET | Retrieve a client's public key |
| `/request_session` | POST | Request a session between two clients |
| `/pending_invitations/<id>` | GET | Retrieve pending invitations |
| `/get_session_key` | POST | Retrieve encrypted session key |
| `/active_sessions/<id>` | GET | List a client's active sessions |

## Communication Example

```
[SEND] Message to bob
[PLAIN] Hello Bob!
[ENCRYPTED] a3Kj8mN2pQ5rS7vX9zA1bC3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW3xY5zA7bC9dE...
[IV] f1G2h3I4j5K6l7M8n9O0
[SIGNATURE] p1Q2r3S4t5U6v7W8x9Y0a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0...

[RECEIVE] Message from alice
[ENCRYPTED] a3Kj8mN2pQ5rS7vX9zA1bC3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW3xY5zA7bC9dE...
[IV] f1G2h3I4j5K6l7M8n9O0
[PLAIN] Hello Bob!
[SIGNATURE] [OK]
```

## Security

### Strengths

- Unique session keys for each client pair
- Random IV for each message (no reuse)
- Signature of all messages for authentication
- RSA keys generated at each client startup

### Limitations (Educational Context)

- The trusted server is a single point of trust
- No perfect forward secrecy (PFS)
- Private keys are stored in memory only
- No key revocation management

## Author

Eliot MAHÉ - ENSIBS - Cryptographic Protocols TP2
