"""
Serveur de confiance pour la distribution de clés de session AES.
- Reçoit les enregistrements des clients avec leurs clés publiques RSA
- Génère des clés de session AES pour les communications
- Chiffre la clé AES avec la clé publique RSA de chaque client
- Stocke les clés publiques pour vérification des signatures
- Support multi-sessions avec timestamps
"""

from flask import Flask, request, jsonify
import os
import json
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import base64
import secrets
from datetime import datetime

app = Flask(__name__)

# Stockage des clients enregistrés: {client_id: {"public_key": PEM, "address": (host, port), "registered_at": timestamp}}
registered_clients = {}

# Sessions actives: {session_id: {"clients": [client1_id, client2_id], "aes_key": bytes, "created_at": timestamp}}
active_sessions = {}

# Invitations en attente: {to_client: [{"from": client_id, "session_id": str, "timestamp": str, "encrypted_key": str}]}
pending_invitations = {}


def generate_aes_key():
    """Génère une clé AES-256 aléatoire."""
    return secrets.token_bytes(32)


def encrypt_with_rsa(public_key_pem: bytes, data: bytes) -> bytes:
    """Chiffre des données avec une clé publique RSA."""
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


def get_timestamp():
    """Retourne un timestamp ISO formaté."""
    return datetime.now().isoformat()


@app.route("/register", methods=["POST"])
def register_client():
    """
    Enregistre un client avec sa clé publique RSA.
    Body: {"client_id": str, "public_key": str (PEM base64), "port": int}
    """
    data = request.get_json()
    client_id = data.get("client_id")
    public_key_b64 = data.get("public_key")
    port = data.get("port")

    if not all([client_id, public_key_b64, port]):
        return jsonify({"error": "Missing required fields"}), 400

    public_key_pem = base64.b64decode(public_key_b64)
    timestamp = get_timestamp()

    registered_clients[client_id] = {
        "public_key": public_key_pem,
        "address": (request.remote_addr, port),
        "registered_at": timestamp
    }

    # Initialise la liste des invitations pour ce client
    if client_id not in pending_invitations:
        pending_invitations[client_id] = []

    print(f"[SERVER] [{timestamp}] Client '{client_id}' enregistré depuis {request.remote_addr}:{port}")
    return jsonify({
        "status": "registered",
        "client_id": client_id,
        "timestamp": timestamp
    })


@app.route("/clients", methods=["GET"])
def list_clients():
    """Liste tous les clients enregistrés."""
    clients = [
        {
            "client_id": cid,
            "address": f"{info['address'][0]}:{info['address'][1]}",
            "registered_at": info.get("registered_at", "N/A")
        }
        for cid, info in registered_clients.items()
    ]
    return jsonify({"clients": clients})


@app.route("/get_public_key/<client_id>", methods=["GET"])
def get_public_key(client_id):
    """Retourne la clé publique d'un client pour vérification des signatures."""
    if client_id not in registered_clients:
        return jsonify({"error": f"Client '{client_id}' not found"}), 404

    public_key_pem = registered_clients[client_id]["public_key"]
    return jsonify({
        "client_id": client_id,
        "public_key": base64.b64encode(public_key_pem).decode()
    })


@app.route("/request_session", methods=["POST"])
def request_session():
    """
    Demande une session sécurisée entre deux clients.
    Body: {"from_client": str, "to_client": str}
    Retourne la clé AES chiffrée pour le demandeur.
    """
    data = request.get_json()
    from_client = data.get("from_client")
    to_client = data.get("to_client")

    if not all([from_client, to_client]):
        return jsonify({"error": "Missing client IDs"}), 400

    if from_client not in registered_clients:
        return jsonify({"error": f"Client '{from_client}' not registered"}), 404

    if to_client not in registered_clients:
        return jsonify({"error": f"Client '{to_client}' not registered"}), 404

    # Génère une clé de session AES unique
    aes_key = generate_aes_key()
    timestamp = get_timestamp()

    # Crée un ID de session
    session_id = secrets.token_hex(16)

    # Stocke la session
    active_sessions[session_id] = {
        "clients": [from_client, to_client],
        "aes_key": aes_key,
        "created_at": timestamp
    }

    # Chiffre la clé AES pour chaque client
    from_client_key = registered_clients[from_client]["public_key"]
    to_client_key = registered_clients[to_client]["public_key"]

    encrypted_key_from = encrypt_with_rsa(from_client_key, aes_key)
    encrypted_key_to = encrypt_with_rsa(to_client_key, aes_key)

    # Récupère l'adresse du destinataire
    to_client_address = registered_clients[to_client]["address"]

    # Ajoute une invitation en attente pour le destinataire
    if to_client not in pending_invitations:
        pending_invitations[to_client] = []

    pending_invitations[to_client].append({
        "from": from_client,
        "session_id": session_id,
        "timestamp": timestamp,
        "encrypted_key": base64.b64encode(encrypted_key_to).decode()
    })

    print(f"[SERVER] [{timestamp}] Session '{session_id[:8]}...' créée entre '{from_client}' et '{to_client}'")

    return jsonify({
        "session_id": session_id,
        "encrypted_aes_key": base64.b64encode(encrypted_key_from).decode(),
        "peer_encrypted_key": base64.b64encode(encrypted_key_to).decode(),
        "peer_address": {
            "host": to_client_address[0] if to_client_address[0] != "127.0.0.1" else "127.0.0.1",
            "port": to_client_address[1]
        },
        "peer_id": to_client,
        "timestamp": timestamp
    })


@app.route("/pending_invitations/<client_id>", methods=["GET"])
def get_pending_invitations(client_id):
    """Récupère les invitations de session en attente pour un client."""
    if client_id not in registered_clients:
        return jsonify({"error": f"Client '{client_id}' not registered"}), 404

    invitations = pending_invitations.get(client_id, [])
    return jsonify({
        "client_id": client_id,
        "invitations": invitations
    })


@app.route("/clear_invitation", methods=["POST"])
def clear_invitation():
    """Supprime une invitation après qu'elle a été traitée."""
    data = request.get_json()
    client_id = data.get("client_id")
    session_id = data.get("session_id")

    if client_id in pending_invitations:
        pending_invitations[client_id] = [
            inv for inv in pending_invitations[client_id]
            if inv["session_id"] != session_id
        ]

    return jsonify({"status": "cleared"})


@app.route("/get_session_key", methods=["POST"])
def get_session_key():
    """
    Permet à un client de récupérer sa clé de session chiffrée.
    Body: {"client_id": str, "session_id": str}
    """
    data = request.get_json()
    client_id = data.get("client_id")
    session_id = data.get("session_id")

    if session_id not in active_sessions:
        return jsonify({"error": "Session not found"}), 404

    session = active_sessions[session_id]

    if client_id not in session["clients"]:
        return jsonify({"error": "Client not in session"}), 403

    # Chiffre la clé pour ce client
    client_key = registered_clients[client_id]["public_key"]
    encrypted_key = encrypt_with_rsa(client_key, session["aes_key"])

    # Trouve l'autre client
    peer_id = [c for c in session["clients"] if c != client_id][0]
    peer_address = registered_clients[peer_id]["address"]

    return jsonify({
        "encrypted_aes_key": base64.b64encode(encrypted_key).decode(),
        "peer_id": peer_id,
        "peer_address": {
            "host": peer_address[0] if peer_address[0] != "127.0.0.1" else "127.0.0.1",
            "port": peer_address[1]
        },
        "created_at": session.get("created_at")
    })


@app.route("/active_sessions/<client_id>", methods=["GET"])
def get_active_sessions(client_id):
    """Liste toutes les sessions actives d'un client."""
    if client_id not in registered_clients:
        return jsonify({"error": f"Client '{client_id}' not registered"}), 404

    sessions = []
    for sid, session in active_sessions.items():
        if client_id in session["clients"]:
            peer_id = [c for c in session["clients"] if c != client_id][0]
            sessions.append({
                "session_id": sid,
                "peer_id": peer_id,
                "created_at": session.get("created_at")
            })

    return jsonify({
        "client_id": client_id,
        "sessions": sessions
    })


if __name__ == "__main__":
    print(f"[SERVER] [{get_timestamp()}] Serveur de confiance démarré sur le port 5000")
    print("[SERVER] En attente d'enregistrements de clients...")
    app.run(host="0.0.0.0", port=5000, debug=False)
