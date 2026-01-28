# Technical Documentation - Secure Communication

This documentation explains in detail how each function in the programs works. It is intended for people wishing to understand the code, even without extensive programming experience.

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [server.py - Trusted Server](#serverpy---trusted-server)
3. [crypto_utils.py - Cryptographic Functions](#crypto_utilspy---cryptographic-functions)
4. [history.py - History Management](#historypy---history-management)
5. [secure_client.py - Main Client Class](#secure_clientpy---main-client-class)
6. [client.py - Entry Point](#clientpy---entry-point)
7. [HTML Pages](#html-pages)

---

## Project Structure

```
TP2/
├── server.py          # Trusted server (key distribution)
├── client.py          # Client entry point (27 lines)
├── secure_client.py   # Main client logic (405 lines)
├── crypto_utils.py    # Cryptographic functions (93 lines)
├── history.py         # History management (80 lines)
├── index.html         # Client selection page
├── chat.html          # Chat page
├── keys/              # Key folder (automatically created)
│   ├── alice_public.pem
│   ├── bob_public.pem
│   └── session_xxx_aes.key
└── history_<client>/  # History per client (automatically created)
    └── <peer>.json
```

---

# server.py - Trusted Server

The server is the "trusted third party" that allows clients to register and receive session keys to communicate with each other.

## Global Variables

```python
registered_clients = {}
```
**What is it?** A dictionary (like a directory) that stores all registered clients.

**Structure:**
```python
{
    "alice": {
        "public_key": b"-----BEGIN PUBLIC KEY-----...",  # RSA public key
        "address": ("127.0.0.1", 5001),                   # IP address and port
        "registered_at": "2026-01-20T14:30:00"            # Registration date
    },
    "bob": { ... }
}
```

---

```python
active_sessions = {}
```
**What is it?** A dictionary that stores all active communication sessions.

**Structure:**
```python
{
    "abc123...": {                           # Unique session identifier
        "clients": ["alice", "bob"],         # The two participants
        "aes_key": b"\x12\x34...",           # Shared AES key (32 bytes)
        "created_at": "2026-01-20T14:35:00"  # Creation date
    }
}
```

---

```python
pending_invitations = {}
```
**What is it?** A dictionary that stores pending session invitations.

**Why?** When Alice requests a session with Bob, the server keeps the invitation until Bob retrieves it.

---

## Utility Functions

### `generate_aes_key()`

```python
def generate_aes_key():
    return secrets.token_bytes(32)
```

**What this function does:** Generates a random 256-bit (32-byte) AES key.

**How it works:**
1. `secrets.token_bytes(32)` generates 32 random bytes securely
2. These 32 bytes form an AES-256 key

**Example result:** `b'\x8f\x2a\x1b...'` (32 random bytes)

---

### `encrypt_with_rsa(public_key_pem, data)`

```python
def encrypt_with_rsa(public_key_pem: bytes, data: bytes) -> bytes:
    public_key = serialization.load_pem_public_key(public_key_pem, backend=default_backend())
    encrypted = public_key.encrypt(
        data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return encrypted
```

**What this function does:** Encrypts data with an RSA public key.

**Parameters:**
- `public_key_pem`: The public key in PEM format (text starting with "-----BEGIN PUBLIC KEY-----")
- `data`: The data to encrypt (here, the AES key)

**How it works:**
1. `serialization.load_pem_public_key()`: Converts PEM text to a usable key object
2. `public_key.encrypt()`: Encrypts the data
3. `padding.OAEP`: Adds secure "padding" to prevent certain attacks

**Why OAEP?** It's the recommended padding mode for RSA. It adds randomness to the encryption, making it more secure.

---

### `get_timestamp()`

```python
def get_timestamp():
    return datetime.now().isoformat()
```

**What this function does:** Returns the current date and time in ISO format.

**Example result:** `"2026-01-20T14:30:45.123456"`

---

## HTTP Routes (Endpoints)

### `POST /register` - Register a Client

```python
@app.route("/register", methods=["POST"])
def register_client():
```

**What this route does:** Allows a client to register with the server using its public key.

**Expected data (JSON):**
```json
{
    "client_id": "alice",
    "public_key": "LS0tLS1CRUdJTi...",
    "port": 5001
}
```

**Detailed steps:**
1. Retrieves JSON data sent by the client
2. Verifies that all fields are present
3. Decodes the public key (from Base64 to bytes)
4. Stores the information in `registered_clients`
5. Initializes an empty list for this client's invitations
6. Returns a confirmation

**Response:**
```json
{
    "status": "registered",
    "client_id": "alice",
    "timestamp": "2026-01-20T14:30:00"
}
```

---

### `GET /clients` - List Clients

```python
@app.route("/clients", methods=["GET"])
def list_clients():
```

**What this route does:** Returns the list of all registered clients.

**Response:**
```json
{
    "clients": [
        {"client_id": "alice", "address": "127.0.0.1:5001", "registered_at": "..."},
        {"client_id": "bob", "address": "127.0.0.1:5002", "registered_at": "..."}
    ]
}
```

---

### `GET /get_public_key/<client_id>` - Retrieve a Public Key

```python
@app.route("/get_public_key/<client_id>", methods=["GET"])
def get_public_key(client_id):
```

**What this route does:** Returns a specific client's public key.

**Why is it useful?** To verify message signatures. If Alice sends a signed message to Bob, Bob needs Alice's public key to verify that it really came from her.

**Example call:** `GET /get_public_key/alice`

**Response:**
```json
{
    "client_id": "alice",
    "public_key": "LS0tLS1CRUdJTi..."
}
```

---

### `POST /request_session` - Request a Session

```python
@app.route("/request_session", methods=["POST"])
def request_session():
```

**What this route does:** Creates a new secure session between two clients.

**Expected data:**
```json
{
    "from_client": "alice",
    "to_client": "bob"
}
```

**Detailed steps:**
1. Verifies that both clients exist
2. Generates a random AES key (the session key) - **only once**
3. Creates a unique identifier for this session
4. Encrypts the AES key with Alice's public key
5. Encrypts the AES key with Bob's public key
6. Stores the session in `active_sessions`
7. Adds an invitation for Bob to `pending_invitations`
8. Returns the information to Alice

**Why encrypt the AES key twice?** Each client can only decrypt with their own private key. So Alice receives the key encrypted for her, and Bob receives the key encrypted for him.

**Response:**
```json
{
    "session_id": "abc123...",
    "encrypted_aes_key": "...",
    "peer_encrypted_key": "...",
    "peer_address": {"host": "127.0.0.1", "port": 5002},
    "peer_id": "bob",
    "timestamp": "..."
}
```

---

### `GET /pending_invitations/<client_id>` - Retrieve Invitations

```python
@app.route("/pending_invitations/<client_id>", methods=["GET"])
def get_pending_invitations(client_id):
```

**What this route does:** Returns pending session invitations for a client.

---

### `POST /clear_invitation` - Delete an Invitation

```python
@app.route("/clear_invitation", methods=["POST"])
def clear_invitation():
```

**What this route does:** Deletes an invitation after it has been processed.

---

### `POST /get_session_key` - Retrieve Session Key

```python
@app.route("/get_session_key", methods=["POST"])
def get_session_key():
```

**What this route does:** Allows a client to retrieve the AES key of an existing session.

**Security:** The server verifies that the client is part of the session before giving them the key.

---

### `GET /active_sessions/<client_id>` - List Sessions

```python
@app.route("/active_sessions/<client_id>", methods=["GET"])
def get_active_sessions(client_id):
```

**What this route does:** Lists all active sessions for a client.

---

# crypto_utils.py - Cryptographic Functions

This file contains all cryptographic functions used by the client.

## `generate_rsa_keypair()`

```python
def generate_rsa_keypair():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    return private_key, private_key.public_key()
```

**What this function does:** Generates an RSA-2048 key pair.

**Generation parameters:**
- `public_exponent=65537`: Standard value for the public exponent
- `key_size=2048`: Key size in bits (recommended security)

**Returns:** A tuple (private_key, public_key)

---

## `public_key_to_pem(public_key)`

```python
def public_key_to_pem(public_key) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
```

**What this function does:** Converts a public key to PEM format (readable text).

**Result:**
```
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A...
-----END PUBLIC KEY-----
```

---

## `load_public_key_from_pem(pem_data)`

```python
def load_public_key_from_pem(pem_data: bytes):
    return serialization.load_pem_public_key(pem_data, backend=default_backend())
```

**What this function does:** Loads a public key from PEM format.

---

## `decrypt_rsa(private_key, encrypted_data)`

```python
def decrypt_rsa(private_key, encrypted_data: bytes) -> bytes:
    return private_key.decrypt(
        encrypted_data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
```

**What this function does:** Decrypts data with an RSA private key (OAEP padding).

**Main use:** Decrypt the AES key received from the server.

---

## `sign_message(private_key, message)`

```python
def sign_message(private_key, message: str) -> bytes:
    return private_key.sign(
        message.encode('utf-8'),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
```

**What this function does:** Signs a message with an RSA private key (PSS padding).

**Why sign?** The signature proves that the message really comes from the sender. Only the holder of the private key can create this signature.

**How it works:**
1. Converts the message to bytes
2. Calculates a "hash" (fingerprint) of the message with SHA-256
3. Encrypts this hash with the private key → this is the signature

---

## `verify_signature(public_key, message, signature)`

```python
def verify_signature(public_key, message: str, signature: bytes) -> bool:
    try:
        public_key.verify(
            signature,
            message.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False
```

**What this function does:** Verifies a message signature.

**Returns:**
- `True`: Valid signature (authentic message)
- `False`: Invalid signature (potentially forged message)

---

## `encrypt_aes(plaintext, aes_key)`

```python
def encrypt_aes(plaintext: bytes, aes_key: bytes) -> tuple:
    iv = secrets.token_bytes(16)

    # PKCS7 Padding
    block_size = 16
    padding_len = block_size - (len(plaintext) % block_size)
    padded = plaintext + bytes([padding_len] * padding_len)

    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    return ciphertext, iv
```

**What this function does:** Encrypts a message with AES-256-CBC.

**Detailed steps:**

1. **IV (Initialization Vector) generation:**
   ```python
   iv = secrets.token_bytes(16)
   ```
   The IV is a 16-byte random block. It makes each encryption unique, even for the same message.

2. **PKCS7 Padding:**
   ```python
   padding_len = block_size - (len(plaintext) % block_size)
   padded = plaintext + bytes([padding_len] * padding_len)
   ```
   AES works with 16-byte blocks. If the message is not a multiple of 16, we add bytes to complete it.

   **Example:** 13-byte message → add 3 bytes of value `0x03`

3. **Encryption:**
   - `AES`: The encryption algorithm
   - `CBC`: The chaining mode (each block depends on the previous one)
   - `iv`: The initialization vector

**Returns:** The encrypted message and the IV (needed to decrypt)

---

## `decrypt_aes(ciphertext, iv, aes_key)`

```python
def decrypt_aes(ciphertext: bytes, iv: bytes, aes_key: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    # Remove PKCS7 padding
    padding_len = padded[-1]
    return padded[:-padding_len]
```

**What this function does:** Decrypts a message encrypted with AES-256-CBC.

**Steps:**
1. Creates a decryptor with the same key and IV
2. Decrypts the data
3. Removes the padding (the last byte indicates how many bytes to remove)

---

# history.py - History Management

This file manages conversation persistence.

## `HistoryManager` Class

### `__init__(self, client_id)`

```python
def __init__(self, client_id: str):
    self.client_id = client_id
    self.history_dir = Path(f"history_{client_id}")
    self.history_dir.mkdir(exist_ok=True)
    self.messages = {}
```

**What this method does:** Initializes the history manager.

- Creates a `history_<client_id>/` folder if it doesn't exist
- Initializes an empty dictionary for messages

---

### `get_timestamp()`

```python
def get_timestamp(self) -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
```

**What this function does:** Returns the date/time in a readable format.

**Example:** `"2026-01-20 14:30:45"`

---

### `load()`

```python
def load(self):
    for history_file in self.history_dir.glob("*.json"):
        peer_id = history_file.stem
        with open(history_file, 'r', encoding='utf-8') as f:
            self.messages[peer_id] = json.load(f)
```

**What this function does:** Loads conversation history from JSON files.

**How it works:**
1. Iterates through all `.json` files in the history folder
2. For each file, extracts the peer name (e.g., `bob.json` → `bob`)
3. Loads the JSON content into the `messages` dictionary

---

### `save(peer_id)`

```python
def save(self, peer_id: str):
    history_file = self.history_dir / f"{peer_id}.json"
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(self.messages[peer_id], f, ensure_ascii=False, indent=2)
```

**What this function does:** Saves a conversation's history to a JSON file.

---

### `add_message(peer_id, from_id, message, verified)`

```python
def add_message(self, peer_id: str, from_id: str, message: str, verified: bool = True) -> dict:
```

**What this function does:** Adds a message to the history and saves it immediately.

**Message structure:**
```json
{
    "from": "alice",
    "message": "Hello!",
    "timestamp": "2026-01-20 14:30:00",
    "verified": true
}
```

---

### `get_messages(peer_id, limit)`

```python
def get_messages(self, peer_id: str, limit: int = 50) -> list:
```

**What this function does:** Returns the last messages of a conversation (50 by default).

---

### `show(peer_id, client_id)`

```python
def show(self, peer_id: str, client_id: str):
```

**What this function does:** Displays the history in the terminal with formatting.

**Display:**
```
[SYSTEM] History with 'bob':
--------------------------------------------------
[2026-01-20 14:30:00] [OK] Me: Hi!
[2026-01-20 14:30:05] [OK] bob: Hello!
--------------------------------------------------
```

---

# secure_client.py - Main Client Class

## `SecureClient` Class

### `__init__(self, client_id, port, server_url)`

```python
def __init__(self, client_id: str, port: int, server_url: str = "http://127.0.0.1:5000"):
```

**What this method does:** Initializes a new secure client.

**Steps:**
1. Creates the `keys/` folder to store keys
2. Generates an RSA key pair
3. Initializes dictionaries for sessions
4. Creates the history manager
5. Configures Flask routes

---

### `_save_key_to_file(filename, key_data, key_type)`

```python
def _save_key_to_file(self, filename: str, key_data: bytes, key_type: str = "AES"):
```

**What this function does:** Saves a key to the `keys/` folder.

**File format:**
```
Type: AES-256
Hex: 8f2a1b3c4d5e6f...
Base64: jyobPE1ebw...
```

---

## Client Flask Routes

### `GET /` - Home Page

```python
@self.app.route("/")
def index():
    return send_file("index.html")
```

**What this route does:** Serves the client selection page.

---

### `GET /chat` - Chat Page

```python
@self.app.route("/chat")
def chat_page():
    return send_file("chat.html")
```

**What this route does:** Serves the chat page.

---

### `POST /receive` - Receive a Message

```python
@self.app.route("/receive", methods=["POST"])
def receive_message():
```

**What this route does:** Receives and processes an encrypted message from another client.

**Expected data:**
```json
{
    "message": "...",
    "iv": "...",
    "from": "alice",
    "signature": "...",
    "timestamp": "..."
}
```

**Steps:**
1. Verifies that a session exists with the sender
2. Displays the encrypted content in the terminal
3. Decrypts the message with AES
4. Displays the plain content in the terminal
5. Verifies the signature
6. Adds the message to history

**Terminal display:**
```
============================================================
[RECEIVE] Message from alice
[ENCRYPTED] dGhpcyBpcyBhbiBlbmNyeXB0ZWQgbWVzc2FnZS4uLg==...
[IV] YWJjZGVmZ2hpamtsbW5vcA==
[PLAIN] Hello Bob!
[SIGNATURE] [OK]
============================================================
```

---

### `POST /session_invite` - Receive an Invitation

```python
@self.app.route("/session_invite", methods=["POST"])
def session_invite():
```

**What this route does:** Receives a session invitation from another client.

**Steps:**
1. Decrypts the AES key with the private key
2. Saves the AES key to `keys/`
3. Stores the session
4. Retrieves the peer's public key

---

### `POST /connect` - Establish a Connection

```python
@self.app.route("/connect", methods=["POST"])
def connect_route():
```

**What this route does:** Establishes a connection with a peer (called from the web interface).

---

### `GET /clients` - List Clients

```python
@self.app.route("/clients")
def clients_route():
```

**What this route does:** Proxy to the server to list available clients.

---

### `GET /messages/<peer_id>` - Retrieve Messages

```python
@self.app.route("/messages/<peer_id>")
def get_peer_messages(peer_id):
```

**What this route does:** Returns messages from a specific conversation (for the web interface).

---

## Main Methods

### `register()`

```python
def register(self) -> bool:
```

**What this function does:** Registers the client with the trusted server.

**Steps:**
1. Saves its public key to `keys/<client_id>_public.pem`
2. Sends a POST request to the server with the ID, public key, and port
3. Returns `True` if registration succeeded

---

### `request_session(target_client)`

```python
def request_session(self, target_client: str) -> bool:
```

**What this function does:** Establishes a secure session with another client.

**Steps:**
1. Checks if a session already exists
2. Requests a new session from the server
3. Decrypts the received AES key
4. Saves the AES key to `keys/`
5. Sends the invitation to the peer

---

### `send_message(message, peer_id)`

```python
def send_message(self, message: str, peer_id: str = None) -> bool:
```

**What this function does:** Sends an encrypted and signed message to a peer.

**Steps:**
1. Signs the message with the RSA private key
2. Encrypts the message with the AES key
3. Displays the plain and encrypted content in the terminal
4. Sends to the peer
5. Adds to history

**Terminal display:**
```
============================================================
[SEND] Message to bob
[PLAIN] Hello Bob!
[ENCRYPTED] dGhpcyBpcyBhbiBlbmNyeXB0ZWQgbWVzc2FnZS4uLg==...
[IV] YWJjZGVmZ2hpamtsbW5vcA==
[SIGNATURE] c2lnbmF0dXJlIGhlcmUuLi4=...
============================================================
```

---

### `run()`

```python
def run(self):
```

**What this function does:** Starts the complete client.

**Steps:**
1. Registers with the server
2. Disables Flask logs (to avoid spam)
3. Starts the Flask server in a separate thread
4. Displays available commands
5. Enters a loop that reads user commands

**Available commands:**
- `/list`: List available clients
- `/connect <id>`: Connect to a client
- `/sessions`: List active sessions
- `/switch <id>`: Switch current session
- `/history [id]`: Display history
- `/quit`: Quit

---

# client.py - Entry Point

```python
#!/usr/bin/env python3
import sys
from secure_client import SecureClient

def main():
    if len(sys.argv) < 3:
        print("Usage: python client.py <client_id> <port>")
        sys.exit(1)

    client_id = sys.argv[1]
    port = int(sys.argv[2])

    client = SecureClient(client_id, port)
    client.run()

if __name__ == "__main__":
    main()
```

**What this file does:** Simple program entry point.

**Usage example:**
```bash
python client.py alice 5001
```

---

# HTML Pages

## index.html - Client Selection Page

**Features:**
- Displays the connected client's identifier
- Lists all available clients
- Indicates status (Available / Connected)
- Click on a client → establishes connection and redirects to chat
- Automatic refresh every 5 seconds

**Structure:**
```
+----------------------------------+
|    Secure Communication          |
|           alice                  |
+----------------------------------+
|    AVAILABLE CLIENTS             |
+----------------------------------+
| bob                  [Available] |
| charlie              [Connected] |
+----------------------------------+
|      [Refresh list]              |
+----------------------------------+
```

---

## chat.html - Chat Page

**Features:**
- Header with peer name and back button
- Chat area with message history
- Sent messages (blue, right-aligned)
- Received messages (white, left-aligned)
- Signature indicator `[OK]` / `[NOTOK]`
- Input area + Send button
- Automatic refresh every 2 seconds

**Structure:**
```
+----------------------------------+
| <- |  bob                        |
|    |  Encrypted communication    |
+----------------------------------+
|                                  |
|        [SYSTEM] Session established|
|                                  |
|                    Hello! [OK]   |
|                         14:30:00 |
|                                  |
| Hi!                              |
| [OK] 14:30:05                    |
|                                  |
+----------------------------------+
| [Type your message...]  [Send]   |
+----------------------------------+
```
