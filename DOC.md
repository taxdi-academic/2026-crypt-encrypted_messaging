# Documentation Technique - Communication Sécurisée

Cette documentation explique en détail le fonctionnement de chaque fonction des programmes. Elle est destinée aux personnes souhaitant comprendre le code, même sans grande expérience en programmation.

---

## Table des matières

1. [Structure du projet](#structure-du-projet)
2. [server.py - Serveur de confiance](#serverpy---serveur-de-confiance)
3. [crypto_utils.py - Fonctions cryptographiques](#crypto_utilspy---fonctions-cryptographiques)
4. [history.py - Gestion de l'historique](#historypy---gestion-de-lhistorique)
5. [secure_client.py - Classe principale du client](#secure_clientpy---classe-principale-du-client)
6. [client.py - Point d'entrée](#clientpy---point-dentrée)
7. [Pages HTML](#pages-html)

---

## Structure du projet

```
TP2/
├── server.py          # Serveur de confiance (distribution de clés)
├── client.py          # Point d'entrée du client (27 lignes)
├── secure_client.py   # Logique principale du client (405 lignes)
├── crypto_utils.py    # Fonctions cryptographiques (93 lignes)
├── history.py         # Gestion de l'historique (80 lignes)
├── index.html         # Page de sélection des clients
├── chat.html          # Page de discussion
├── keys/              # Dossier des clés (créé automatiquement)
│   ├── alice_public.pem
│   ├── bob_public.pem
│   └── session_xxx_aes.key
└── history_<client>/  # Historique par client (créé automatiquement)
    └── <peer>.json
```

---

# server.py - Serveur de confiance

Le serveur est le "tiers de confiance" qui permet aux clients de s'enregistrer et de recevoir des clés de session pour communiquer entre eux.

## Variables globales

```python
registered_clients = {}
```
**Qu'est-ce que c'est ?** Un dictionnaire (comme un annuaire) qui stocke tous les clients enregistrés.

**Structure :**
```python
{
    "alice": {
        "public_key": b"-----BEGIN PUBLIC KEY-----...",  # Clé publique RSA
        "address": ("127.0.0.1", 5001),                   # Adresse IP et port
        "registered_at": "2026-01-20T14:30:00"            # Date d'enregistrement
    },
    "bob": { ... }
}
```

---

```python
active_sessions = {}
```
**Qu'est-ce que c'est ?** Un dictionnaire qui stocke toutes les sessions de communication actives.

**Structure :**
```python
{
    "abc123...": {                           # Identifiant unique de la session
        "clients": ["alice", "bob"],         # Les deux participants
        "aes_key": b"\x12\x34...",           # La clé AES partagée (32 bytes)
        "created_at": "2026-01-20T14:35:00"  # Date de création
    }
}
```

---

```python
pending_invitations = {}
```
**Qu'est-ce que c'est ?** Un dictionnaire qui stocke les invitations de session en attente.

**Pourquoi ?** Quand Alice demande une session avec Bob, le serveur garde l'invitation jusqu'à ce que Bob la récupère.

---

## Fonctions utilitaires

### `generate_aes_key()`

```python
def generate_aes_key():
    return secrets.token_bytes(32)
```

**Ce que fait cette fonction :** Génère une clé AES aléatoire de 256 bits (32 octets).

**Comment ça marche :**
1. `secrets.token_bytes(32)` génère 32 octets aléatoires de manière sécurisée
2. Ces 32 octets forment une clé AES-256

**Exemple de résultat :** `b'\x8f\x2a\x1b...'` (32 octets aléatoires)

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

**Ce que fait cette fonction :** Chiffre des données avec une clé publique RSA.

**Paramètres :**
- `public_key_pem` : La clé publique au format PEM (texte commençant par "-----BEGIN PUBLIC KEY-----")
- `data` : Les données à chiffrer (ici, la clé AES)

**Comment ça marche :**
1. `serialization.load_pem_public_key()` : Convertit le texte PEM en objet clé utilisable
2. `public_key.encrypt()` : Chiffre les données
3. `padding.OAEP` : Ajoute un "rembourrage" sécurisé pour éviter certaines attaques

**Pourquoi OAEP ?** C'est le mode de padding recommandé pour RSA. Il ajoute de l'aléatoire au chiffrement, ce qui le rend plus sûr.

---

### `get_timestamp()`

```python
def get_timestamp():
    return datetime.now().isoformat()
```

**Ce que fait cette fonction :** Retourne la date et l'heure actuelles au format ISO.

**Exemple de résultat :** `"2026-01-20T14:30:45.123456"`

---

## Routes HTTP (endpoints)

### `POST /register` - Enregistrer un client

```python
@app.route("/register", methods=["POST"])
def register_client():
```

**Ce que fait cette route :** Permet à un client de s'enregistrer auprès du serveur avec sa clé publique.

**Données attendues (JSON) :**
```json
{
    "client_id": "alice",
    "public_key": "LS0tLS1CRUdJTi...",
    "port": 5001
}
```

**Étapes détaillées :**
1. Récupère les données JSON envoyées par le client
2. Vérifie que tous les champs sont présents
3. Décode la clé publique (de Base64 vers bytes)
4. Stocke les informations dans `registered_clients`
5. Initialise une liste vide pour les invitations de ce client
6. Retourne une confirmation

**Réponse :**
```json
{
    "status": "registered",
    "client_id": "alice",
    "timestamp": "2026-01-20T14:30:00"
}
```

---

### `GET /clients` - Lister les clients

```python
@app.route("/clients", methods=["GET"])
def list_clients():
```

**Ce que fait cette route :** Retourne la liste de tous les clients enregistrés.

**Réponse :**
```json
{
    "clients": [
        {"client_id": "alice", "address": "127.0.0.1:5001", "registered_at": "..."},
        {"client_id": "bob", "address": "127.0.0.1:5002", "registered_at": "..."}
    ]
}
```

---

### `GET /get_public_key/<client_id>` - Récupérer une clé publique

```python
@app.route("/get_public_key/<client_id>", methods=["GET"])
def get_public_key(client_id):
```

**Ce que fait cette route :** Retourne la clé publique d'un client spécifique.

**Pourquoi c'est utile ?** Pour vérifier les signatures des messages. Si Alice envoie un message signé à Bob, Bob a besoin de la clé publique d'Alice pour vérifier que c'est bien elle qui l'a envoyé.

**Exemple d'appel :** `GET /get_public_key/alice`

**Réponse :**
```json
{
    "client_id": "alice",
    "public_key": "LS0tLS1CRUdJTi..."
}
```

---

### `POST /request_session` - Demander une session

```python
@app.route("/request_session", methods=["POST"])
def request_session():
```

**Ce que fait cette route :** Crée une nouvelle session sécurisée entre deux clients.

**Données attendues :**
```json
{
    "from_client": "alice",
    "to_client": "bob"
}
```

**Étapes détaillées :**
1. Vérifie que les deux clients existent
2. Génère une clé AES aléatoire (la clé de session) - **une seule fois**
3. Crée un identifiant unique pour cette session
4. Chiffre la clé AES avec la clé publique d'Alice
5. Chiffre la clé AES avec la clé publique de Bob
6. Stocke la session dans `active_sessions`
7. Ajoute une invitation pour Bob dans `pending_invitations`
8. Retourne les informations à Alice

**Pourquoi chiffrer deux fois la clé AES ?** Chaque client ne peut déchiffrer qu'avec sa propre clé privée. Donc Alice reçoit la clé chiffrée pour elle, et Bob reçoit la clé chiffrée pour lui.

**Réponse :**
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

### `GET /pending_invitations/<client_id>` - Récupérer les invitations

```python
@app.route("/pending_invitations/<client_id>", methods=["GET"])
def get_pending_invitations(client_id):
```

**Ce que fait cette route :** Retourne les invitations de session en attente pour un client.

---

### `POST /clear_invitation` - Supprimer une invitation

```python
@app.route("/clear_invitation", methods=["POST"])
def clear_invitation():
```

**Ce que fait cette route :** Supprime une invitation après qu'elle a été traitée.

---

### `POST /get_session_key` - Récupérer sa clé de session

```python
@app.route("/get_session_key", methods=["POST"])
def get_session_key():
```

**Ce que fait cette route :** Permet à un client de récupérer la clé AES d'une session existante.

**Sécurité :** Le serveur vérifie que le client fait bien partie de la session avant de lui donner la clé.

---

### `GET /active_sessions/<client_id>` - Lister ses sessions

```python
@app.route("/active_sessions/<client_id>", methods=["GET"])
def get_active_sessions(client_id):
```

**Ce que fait cette route :** Liste toutes les sessions actives d'un client.

---

# crypto_utils.py - Fonctions cryptographiques

Ce fichier contient toutes les fonctions de cryptographie utilisées par le client.

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

**Ce que fait cette fonction :** Génère une paire de clés RSA-2048.

**Paramètres de génération :**
- `public_exponent=65537` : Valeur standard pour l'exposant public
- `key_size=2048` : Taille de la clé en bits (sécurité recommandée)

**Retourne :** Un tuple (clé_privée, clé_publique)

---

## `public_key_to_pem(public_key)`

```python
def public_key_to_pem(public_key) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
```

**Ce que fait cette fonction :** Convertit une clé publique en format PEM (texte lisible).

**Résultat :**
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

**Ce que fait cette fonction :** Charge une clé publique depuis le format PEM.

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

**Ce que fait cette fonction :** Déchiffre des données avec une clé privée RSA (padding OAEP).

**Utilisation principale :** Déchiffrer la clé AES reçue du serveur.

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

**Ce que fait cette fonction :** Signe un message avec une clé privée RSA (padding PSS).

**Pourquoi signer ?** La signature prouve que le message vient bien de l'expéditeur. Seul le détenteur de la clé privée peut créer cette signature.

**Comment ça marche :**
1. Convertit le message en bytes
2. Calcule un "hash" (empreinte) du message avec SHA-256
3. Chiffre ce hash avec la clé privée → c'est la signature

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

**Ce que fait cette fonction :** Vérifie la signature d'un message.

**Retourne :**
- `True` : Signature valide (message authentique)
- `False` : Signature invalide (message potentiellement falsifié)

---

## `encrypt_aes(plaintext, aes_key)`

```python
def encrypt_aes(plaintext: bytes, aes_key: bytes) -> tuple:
    iv = secrets.token_bytes(16)

    # Padding PKCS7
    block_size = 16
    padding_len = block_size - (len(plaintext) % block_size)
    padded = plaintext + bytes([padding_len] * padding_len)

    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    return ciphertext, iv
```

**Ce que fait cette fonction :** Chiffre un message avec AES-256-CBC.

**Étapes détaillées :**

1. **Génération de l'IV (Initialization Vector) :**
   ```python
   iv = secrets.token_bytes(16)
   ```
   L'IV est un bloc de 16 bytes aléatoires. Il rend chaque chiffrement unique, même pour le même message.

2. **Padding PKCS7 :**
   ```python
   padding_len = block_size - (len(plaintext) % block_size)
   padded = plaintext + bytes([padding_len] * padding_len)
   ```
   AES travaille par blocs de 16 bytes. Si le message ne fait pas un multiple de 16, on ajoute des bytes pour compléter.

   **Exemple :** Message de 13 bytes → on ajoute 3 bytes de valeur `0x03`

3. **Chiffrement :**
   - `AES` : L'algorithme de chiffrement
   - `CBC` : Le mode de chaînage (chaque bloc dépend du précédent)
   - `iv` : Le vecteur d'initialisation

**Retourne :** Le message chiffré et l'IV (nécessaire pour déchiffrer)

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

**Ce que fait cette fonction :** Déchiffre un message chiffré avec AES-256-CBC.

**Étapes :**
1. Crée un déchiffreur avec la même clé et le même IV
2. Déchiffre les données
3. Retire le padding (le dernier byte indique combien de bytes retirer)

---

# history.py - Gestion de l'historique

Ce fichier gère la persistance des conversations.

## Classe `HistoryManager`

### `__init__(self, client_id)`

```python
def __init__(self, client_id: str):
    self.client_id = client_id
    self.history_dir = Path(f"history_{client_id}")
    self.history_dir.mkdir(exist_ok=True)
    self.messages = {}
```

**Ce que fait cette méthode :** Initialise le gestionnaire d'historique.

- Crée un dossier `history_<client_id>/` s'il n'existe pas
- Initialise un dictionnaire vide pour les messages

---

### `get_timestamp()`

```python
def get_timestamp(self) -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
```

**Ce que fait cette fonction :** Retourne la date/heure au format lisible.

**Exemple :** `"2026-01-20 14:30:45"`

---

### `load()`

```python
def load(self):
    for history_file in self.history_dir.glob("*.json"):
        peer_id = history_file.stem
        with open(history_file, 'r', encoding='utf-8') as f:
            self.messages[peer_id] = json.load(f)
```

**Ce que fait cette fonction :** Charge l'historique des conversations depuis les fichiers JSON.

**Comment ça marche :**
1. Parcourt tous les fichiers `.json` dans le dossier d'historique
2. Pour chaque fichier, extrait le nom du pair (ex: `bob.json` → `bob`)
3. Charge le contenu JSON dans le dictionnaire `messages`

---

### `save(peer_id)`

```python
def save(self, peer_id: str):
    history_file = self.history_dir / f"{peer_id}.json"
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(self.messages[peer_id], f, ensure_ascii=False, indent=2)
```

**Ce que fait cette fonction :** Sauvegarde l'historique d'une conversation dans un fichier JSON.

---

### `add_message(peer_id, from_id, message, verified)`

```python
def add_message(self, peer_id: str, from_id: str, message: str, verified: bool = True) -> dict:
```

**Ce que fait cette fonction :** Ajoute un message à l'historique et le sauvegarde immédiatement.

**Structure d'un message :**
```json
{
    "from": "alice",
    "message": "Bonjour!",
    "timestamp": "2026-01-20 14:30:00",
    "verified": true
}
```

---

### `get_messages(peer_id, limit)`

```python
def get_messages(self, peer_id: str, limit: int = 50) -> list:
```

**Ce que fait cette fonction :** Retourne les derniers messages d'une conversation (50 par défaut).

---

### `show(peer_id, client_id)`

```python
def show(self, peer_id: str, client_id: str):
```

**Ce que fait cette fonction :** Affiche l'historique dans le terminal avec formatage.

**Affichage :**
```
[SYSTEM] Historique avec 'bob':
--------------------------------------------------
[2026-01-20 14:30:00] [OK] Moi: Salut!
[2026-01-20 14:30:05] [OK] bob: Hello!
--------------------------------------------------
```

---

# secure_client.py - Classe principale du client

## Classe `SecureClient`

### `__init__(self, client_id, port, server_url)`

```python
def __init__(self, client_id: str, port: int, server_url: str = "http://127.0.0.1:5000"):
```

**Ce que fait cette méthode :** Initialise un nouveau client sécurisé.

**Étapes :**
1. Crée le dossier `keys/` pour stocker les clés
2. Génère une paire de clés RSA
3. Initialise les dictionnaires pour les sessions
4. Crée le gestionnaire d'historique
5. Configure les routes Flask

---

### `_save_key_to_file(filename, key_data, key_type)`

```python
def _save_key_to_file(self, filename: str, key_data: bytes, key_type: str = "AES"):
```

**Ce que fait cette fonction :** Sauvegarde une clé dans le dossier `keys/`.

**Format du fichier :**
```
Type: AES-256
Hex: 8f2a1b3c4d5e6f...
Base64: jyobPE1ebw...
```

---

## Routes Flask du client

### `GET /` - Page d'accueil

```python
@self.app.route("/")
def index():
    return send_file("index.html")
```

**Ce que fait cette route :** Sert la page de sélection des clients.

---

### `GET /chat` - Page de discussion

```python
@self.app.route("/chat")
def chat_page():
    return send_file("chat.html")
```

**Ce que fait cette route :** Sert la page de discussion.

---

### `POST /receive` - Recevoir un message

```python
@self.app.route("/receive", methods=["POST"])
def receive_message():
```

**Ce que fait cette route :** Reçoit et traite un message chiffré d'un autre client.

**Données attendues :**
```json
{
    "message": "...",
    "iv": "...",
    "from": "alice",
    "signature": "...",
    "timestamp": "..."
}
```

**Étapes :**
1. Vérifie qu'une session existe avec l'expéditeur
2. Affiche le contenu chiffré dans le terminal
3. Déchiffre le message avec AES
4. Affiche le contenu clair dans le terminal
5. Vérifie la signature
6. Ajoute le message à l'historique

**Affichage terminal :**
```
============================================================
[RECEPTION] Message de alice
[CHIFFRE] dGhpcyBpcyBhbiBlbmNyeXB0ZWQgbWVzc2FnZS4uLg==...
[IV] YWJjZGVmZ2hpamtsbW5vcA==
[CLAIR] Bonjour Bob!
[SIGNATURE] [OK]
============================================================
```

---

### `POST /session_invite` - Recevoir une invitation

```python
@self.app.route("/session_invite", methods=["POST"])
def session_invite():
```

**Ce que fait cette route :** Reçoit une invitation de session d'un autre client.

**Étapes :**
1. Déchiffre la clé AES avec la clé privée
2. Sauvegarde la clé AES dans `keys/`
3. Stocke la session
4. Récupère la clé publique du pair

---

### `POST /connect` - Établir une connexion

```python
@self.app.route("/connect", methods=["POST"])
def connect_route():
```

**Ce que fait cette route :** Établit une connexion avec un pair (appelée depuis l'interface web).

---

### `GET /clients` - Lister les clients

```python
@self.app.route("/clients")
def clients_route():
```

**Ce que fait cette route :** Proxy vers le serveur pour lister les clients disponibles.

---

### `GET /messages/<peer_id>` - Récupérer les messages

```python
@self.app.route("/messages/<peer_id>")
def get_peer_messages(peer_id):
```

**Ce que fait cette route :** Retourne les messages d'une conversation spécifique (pour l'interface web).

---

## Méthodes principales

### `register()`

```python
def register(self) -> bool:
```

**Ce que fait cette fonction :** Enregistre le client auprès du serveur de confiance.

**Étapes :**
1. Sauvegarde sa clé publique dans `keys/<client_id>_public.pem`
2. Envoie une requête POST au serveur avec l'ID, la clé publique et le port
3. Retourne `True` si l'enregistrement a réussi

---

### `request_session(target_client)`

```python
def request_session(self, target_client: str) -> bool:
```

**Ce que fait cette fonction :** Établit une session sécurisée avec un autre client.

**Étapes :**
1. Vérifie si une session existe déjà
2. Demande une nouvelle session au serveur
3. Déchiffre la clé AES reçue
4. Sauvegarde la clé AES dans `keys/`
5. Envoie l'invitation au pair

---

### `send_message(message, peer_id)`

```python
def send_message(self, message: str, peer_id: str = None) -> bool:
```

**Ce que fait cette fonction :** Envoie un message chiffré et signé à un pair.

**Étapes :**
1. Signe le message avec la clé privée RSA
2. Chiffre le message avec la clé AES
3. Affiche le contenu clair et chiffré dans le terminal
4. Envoie au pair
5. Ajoute à l'historique

**Affichage terminal :**
```
============================================================
[ENVOI] Message vers bob
[CLAIR] Bonjour Bob!
[CHIFFRE] dGhpcyBpcyBhbiBlbmNyeXB0ZWQgbWVzc2FnZS4uLg==...
[IV] YWJjZGVmZ2hpamtsbW5vcA==
[SIGNATURE] c2lnbmF0dXJlIGhlcmUuLi4=...
============================================================
```

---

### `run()`

```python
def run(self):
```

**Ce que fait cette fonction :** Démarre le client complet.

**Étapes :**
1. S'enregistre auprès du serveur
2. Désactive les logs Flask (pour éviter le spam)
3. Démarre le serveur Flask dans un thread séparé
4. Affiche les commandes disponibles
5. Entre dans une boucle qui lit les commandes utilisateur

**Commandes disponibles :**
- `/list` : Liste les clients disponibles
- `/connect <id>` : Se connecter à un client
- `/sessions` : Liste les sessions actives
- `/switch <id>` : Changer de session courante
- `/history [id]` : Afficher l'historique
- `/quit` : Quitter

---

# client.py - Point d'entrée

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

**Ce que fait ce fichier :** Point d'entrée simple du programme.

**Exemple d'utilisation :**
```bash
python client.py alice 5001
```

---

# Pages HTML

## index.html - Page de sélection des clients

**Fonctionnalités :**
- Affiche l'identifiant du client connecté
- Liste tous les clients disponibles
- Indique le statut (Disponible / Connecté)
- Clic sur un client → établit la connexion et redirige vers le chat
- Actualisation automatique toutes les 5 secondes

**Structure :**
```
+----------------------------------+
|    Communication Sécurisée       |
|           alice                  |
+----------------------------------+
|    CLIENTS DISPONIBLES           |
+----------------------------------+
| bob                  [Disponible]|
| charlie              [Connecté]  |
+----------------------------------+
|      [Actualiser la liste]       |
+----------------------------------+
```

---

## chat.html - Page de discussion

**Fonctionnalités :**
- Header avec nom du pair et bouton retour
- Zone de chat avec historique des messages
- Messages envoyés (bleu, à droite)
- Messages reçus (blanc, à gauche)
- Indicateur de signature `[OK]` / `[NOTOK]`
- Zone de saisie + bouton Envoyer
- Actualisation automatique toutes les 2 secondes

**Structure :**
```
+----------------------------------+
| <- |  bob                        |
|    |  Communication chiffrée     |
+----------------------------------+
|                                  |
|        [SYSTEM] Session établie  |
|                                  |
|                    Bonjour! [OK] |
|                         14:30:00 |
|                                  |
| Hello!                           |
| [OK] 14:30:05                    |
|                                  |
+----------------------------------+
| [Tapez votre message...]  [Envoyer]
+----------------------------------+
```