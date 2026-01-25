"""
Classe principale du client sécurisé.
- Gestion des sessions
- Communication avec le serveur et les pairs
- Routes Flask
- Stockage des clés dans un dossier local
"""

from flask import Flask, request, jsonify, send_file
import threading
import requests
import base64
import json
import os
from pathlib import Path

from crypto_utils import (
    generate_rsa_keypair, public_key_to_pem, load_public_key_from_pem,
    decrypt_rsa, sign_message, verify_signature, encrypt_aes, decrypt_aes
)
from history import HistoryManager


class SecureClient:
    def __init__(self, client_id: str, port: int, server_url: str = "http://127.0.0.1:5000"):
        self.client_id = client_id
        self.port = port
        self.server_url = server_url

        # Dossier pour les clés (accessible à tous)
        self.keys_dir = Path("keys")
        self.keys_dir.mkdir(exist_ok=True)

        # Génère la paire de clés RSA
        self.private_key, self.public_key = generate_rsa_keypair()

        # Sessions: {peer_id: {"session_id": str, "aes_key": bytes, "address": tuple, "created_at": str}}
        self.sessions = {}
        self.current_peer = None

        # Cache des clés publiques des pairs
        self.peer_public_keys = {}

        # Historique
        self.history = HistoryManager(client_id)
        self.history.load()

        # Flask
        self.app = Flask(__name__)
        self._setup_routes()

        self.running = True

    def _save_key_to_file(self, filename: str, key_data: bytes, key_type: str = "AES"):
        """Sauvegarde une clé dans le dossier keys/."""
        key_file = self.keys_dir / filename
        with open(key_file, 'w') as f:
            f.write(f"Type: {key_type}\n")
            f.write(f"Hex: {key_data.hex()}\n")
            f.write(f"Base64: {base64.b64encode(key_data).decode()}\n")
        print(f"[KEYS] Clé sauvegardée: {key_file}")

    def _setup_routes(self):
        """Configure les routes Flask."""

        @self.app.route("/")
        def index():
            return send_file("index.html")

        @self.app.route("/chat")
        def chat_page():
            return send_file("chat.html")

        @self.app.route("/receive", methods=["POST"])
        def receive_message():
            data = request.get_json()
            from_client = data.get("from")
            timestamp = data.get("timestamp", self.history.get_timestamp())

            if from_client not in self.sessions:
                return jsonify({"error": "No active session"}), 400

            # Récupère les données chiffrées
            encrypted_msg_b64 = data.get("message")
            iv_b64 = data.get("iv")
            encrypted_msg = base64.b64decode(encrypted_msg_b64)
            iv = base64.b64decode(iv_b64)

            # Affiche le contenu chiffré
            print(f"\n{'='*60}")
            print(f"[RECEPTION] Message de {from_client}")
            print(f"[CHIFFRE] {encrypted_msg_b64[:80]}...")
            print(f"[IV] {iv_b64}")

            # Déchiffre le message
            message = decrypt_aes(encrypted_msg, iv, self.sessions[from_client]["aes_key"]).decode('utf-8')

            # Affiche le contenu clair
            print(f"[CLAIR] {message}")

            # Vérifie la signature
            verified = False
            signature_b64 = data.get("signature")
            if signature_b64 and from_client in self.peer_public_keys:
                signature = base64.b64decode(signature_b64)
                verified = verify_signature(self.peer_public_keys[from_client], message, signature)

            status_icon = "[OK]" if verified else "[NOTOK]"
            print(f"[SIGNATURE] {status_icon}")
            print(f"{'='*60}")

            self.history.add_message(from_client, from_client, message, verified)

            return jsonify({"status": "received", "verified": verified})

        @self.app.route("/session_invite", methods=["POST"])
        def session_invite():
            data = request.get_json()
            from_client = data.get("from")
            session_id = data.get("session_id")
            timestamp = data.get("timestamp", self.history.get_timestamp())

            # Déchiffre la clé AES
            encrypted_key = base64.b64decode(data.get("encrypted_key"))
            aes_key = decrypt_rsa(self.private_key, encrypted_key)

            # Sauvegarde la clé AES
            self._save_key_to_file(f"session_{session_id[:16]}_aes.key", aes_key, "AES-256")

            self.sessions[from_client] = {
                "session_id": session_id,
                "aes_key": aes_key,
                "address": (request.remote_addr, data.get("from_port")),
                "created_at": timestamp
            }

            self._fetch_peer_public_key(from_client)
            print(f"\n[{timestamp}] [NOTIFICATION] Nouvelle session avec '{from_client}'")
            self.history.add_message(from_client, "SYSTEM", f"Session établie (initiée par {from_client})", True)

            return jsonify({"status": "accepted"})

        @self.app.route("/send", methods=["POST"])
        def send_from_web():
            data = request.get_json()
            msg = data.get("message")
            peer = data.get("peer", self.current_peer)

            if not msg or not peer or peer not in self.sessions:
                return jsonify({"error": "Invalid request"}), 400

            success = self.send_message(msg, peer)
            return jsonify({"status": "sent" if success else "failed"})

        @self.app.route("/messages")
        def get_messages():
            peer = request.args.get("peer", self.current_peer)
            return jsonify(self.history.get_messages(peer) if peer else [])

        @self.app.route("/status")
        def status():
            return jsonify({
                "client_id": self.client_id,
                "sessions": list(self.sessions.keys()),
                "current_peer": self.current_peer
            })

        @self.app.route("/sessions")
        def list_sessions_route():
            return jsonify({"sessions": [
                {"peer_id": p, "created_at": s.get("created_at")}
                for p, s in self.sessions.items()
            ]})

        @self.app.route("/clients")
        def clients_route():
            """Proxy vers le serveur pour lister les clients."""
            try:
                response = requests.get(f"{self.server_url}/clients")
                return jsonify(response.json())
            except Exception:
                return jsonify({"clients": []})

        @self.app.route("/connect", methods=["POST"])
        def connect_route():
            """Établit une connexion avec un pair."""
            data = request.get_json()
            peer = data.get("peer")
            if not peer:
                return jsonify({"error": "No peer specified"}), 400

            success = self.request_session(peer)
            return jsonify({"status": "connected" if success else "failed"})

        @self.app.route("/messages/<peer_id>")
        def get_peer_messages(peer_id):
            """Retourne les messages d'un pair spécifique."""
            return jsonify(self.history.get_messages(peer_id))

    def _fetch_peer_public_key(self, peer_id: str):
        """Récupère la clé publique d'un pair."""
        try:
            response = requests.get(f"{self.server_url}/get_public_key/{peer_id}")
            if response.status_code == 200:
                pem = base64.b64decode(response.json()["public_key"])
                self.peer_public_keys[peer_id] = load_public_key_from_pem(pem)
                # Sauvegarde la clé publique
                key_file = self.keys_dir / f"{peer_id}_public.pem"
                with open(key_file, 'wb') as f:
                    f.write(pem)
        except Exception as e:
            print(f"[WARNING] Clé publique de '{peer_id}' non récupérée: {e}")

    def register(self) -> bool:
        """S'enregistre auprès du serveur."""
        public_key_b64 = base64.b64encode(public_key_to_pem(self.public_key)).decode()

        # Sauvegarde sa propre clé publique
        key_file = self.keys_dir / f"{self.client_id}_public.pem"
        with open(key_file, 'wb') as f:
            f.write(public_key_to_pem(self.public_key))
        print(f"[KEYS] Clé publique sauvegardée: {key_file}")

        response = requests.post(f"{self.server_url}/register", json={
            "client_id": self.client_id,
            "public_key": public_key_b64,
            "port": self.port
        })

        if response.status_code == 200:
            ts = response.json().get("timestamp", self.history.get_timestamp())
            print(f"[{ts}] [SYSTEM] Enregistré comme '{self.client_id}'")
            return True
        print(f"[ERROR] Enregistrement échoué: {response.json()}")
        return False

    def list_clients(self):
        """Liste les clients disponibles."""
        response = requests.get(f"{self.server_url}/clients")
        if response.status_code == 200:
            print(f"\n[{self.history.get_timestamp()}] [SYSTEM] Clients disponibles:")
            for c in response.json()["clients"]:
                if c["client_id"] != self.client_id:
                    status = "[session]" if c["client_id"] in self.sessions else ""
                    print(f"  - {c['client_id']} ({c['address']}) {status}")

    def list_sessions(self):
        """Affiche les sessions actives."""
        if not self.sessions:
            print(f"\n[{self.history.get_timestamp()}] [SYSTEM] Aucune session active")
            return
        print(f"\n[{self.history.get_timestamp()}] [SYSTEM] Sessions actives:")
        for peer_id, session in self.sessions.items():
            current = ">" if peer_id == self.current_peer else " "
            print(f"  {current} {peer_id} (depuis {session.get('created_at', 'N/A')})")

    def request_session(self, target_client: str) -> bool:
        """Demande une session avec un client."""
        if target_client in self.sessions:
            print(f"[{self.history.get_timestamp()}] [SYSTEM] Session déjà active avec '{target_client}'")
            self.current_peer = target_client
            return True

        response = requests.post(f"{self.server_url}/request_session", json={
            "from_client": self.client_id,
            "to_client": target_client
        })

        if response.status_code != 200:
            print(f"[ERROR] Échec: {response.json()}")
            return False

        data = response.json()
        session_id = data["session_id"]
        encrypted_key = base64.b64decode(data["encrypted_aes_key"])
        aes_key = decrypt_rsa(self.private_key, encrypted_key)
        peer_address = (data["peer_address"]["host"], data["peer_address"]["port"])

        # Sauvegarde la clé AES
        self._save_key_to_file(f"session_{session_id[:16]}_aes.key", aes_key, "AES-256")

        self.sessions[target_client] = {
            "session_id": session_id,
            "aes_key": aes_key,
            "address": peer_address,
            "created_at": data.get("timestamp", self.history.get_timestamp())
        }
        self.current_peer = target_client
        self._fetch_peer_public_key(target_client)

        # Envoie l'invitation au pair
        try:
            requests.post(f"http://{peer_address[0]}:{peer_address[1]}/session_invite", json={
                "session_id": session_id,
                "from": self.client_id,
                "from_port": self.port,
                "encrypted_key": data["peer_encrypted_key"],
                "timestamp": data.get("timestamp")
            })
            print(f"[{data.get('timestamp')}] [SYSTEM] Session établie avec '{target_client}'")
            self.history.add_message(target_client, "SYSTEM", f"Session établie avec {target_client}", True)
            return True
        except Exception as e:
            print(f"[ERROR] Impossible de contacter {target_client}: {e}")
            return False

    def send_message(self, message: str, peer_id: str = None) -> bool:
        """Envoie un message chiffré et signé."""
        peer_id = peer_id or self.current_peer
        if not peer_id or peer_id not in self.sessions:
            print("[ERROR] Pas de session active")
            return False

        session = self.sessions[peer_id]
        signature = sign_message(self.private_key, message)
        ciphertext, iv = encrypt_aes(message.encode('utf-8'), session["aes_key"])
        timestamp = self.history.get_timestamp()

        # Affiche le contenu clair et chiffré
        print(f"\n{'='*60}")
        print(f"[ENVOI] Message vers {peer_id}")
        print(f"[CLAIR] {message}")
        print(f"[CHIFFRE] {base64.b64encode(ciphertext).decode()[:80]}...")
        print(f"[IV] {base64.b64encode(iv).decode()}")
        print(f"[SIGNATURE] {base64.b64encode(signature).decode()[:60]}...")
        print(f"{'='*60}")

        try:
            response = requests.post(f"http://{session['address'][0]}:{session['address'][1]}/receive", json={
                "message": base64.b64encode(ciphertext).decode(),
                "iv": base64.b64encode(iv).decode(),
                "from": self.client_id,
                "signature": base64.b64encode(signature).decode(),
                "timestamp": timestamp
            })

            if response.status_code == 200:
                self.history.add_message(peer_id, self.client_id, message, True)
                return True
        except Exception as e:
            print(f"[ERROR] Échec d'envoi: {e}")
        return False

    def switch_session(self, peer_id: str) -> bool:
        """Change la session courante."""
        if peer_id in self.sessions:
            self.current_peer = peer_id
            print(f"[{self.history.get_timestamp()}] [SYSTEM] Session courante: {peer_id}")
            return True
        print(f"[ERROR] Pas de session avec '{peer_id}'")
        return False

    def run(self):
        """Démarre le client."""
        if not self.register():
            return

        # Démarre Flask (sans logs)
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        def run_flask():
            from werkzeug.serving import make_server
            server = make_server("0.0.0.0", self.port, self.app, threaded=True)
            server.serve_forever()

        threading.Thread(target=run_flask, daemon=True).start()

        print(f"[{self.history.get_timestamp()}] [SYSTEM] Client sur le port {self.port}")
        print(f"[SYSTEM] Interface web: http://127.0.0.1:{self.port}")
        print(f"[SYSTEM] Historique: {self.history.history_dir}")
        print(f"[SYSTEM] Clés stockées dans: {self.keys_dir}")
        print("\nCommandes: /list, /connect <id>, /sessions, /switch <id>, /history [id], /quit")
        print()

        while True:
            try:
                cmd = input()

                if cmd == "/list":
                    self.list_clients()
                elif cmd.startswith("/connect "):
                    self.request_session(cmd.split(" ", 1)[1].strip())
                elif cmd == "/sessions":
                    self.list_sessions()
                elif cmd.startswith("/switch "):
                    self.switch_session(cmd.split(" ", 1)[1].strip())
                elif cmd.startswith("/history"):
                    parts = cmd.split(" ", 1)
                    peer = parts[1].strip() if len(parts) > 1 else self.current_peer
                    self.history.show(peer, self.client_id)
                elif cmd == "/quit":
                    print(f"[{self.history.get_timestamp()}] [SYSTEM] Fermeture...")
                    self.running = False
                    break
                elif cmd and not cmd.startswith("/"):
                    if self.current_peer:
                        self.send_message(cmd)
                    else:
                        print("[ERROR] Utilisez /connect <client_id> d'abord")

            except (KeyboardInterrupt, EOFError):
                self.running = False
                break
