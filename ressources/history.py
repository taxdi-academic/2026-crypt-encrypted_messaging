"""
Gestion de l'historique des conversations.
- Chargement et sauvegarde des messages
- Ajout de nouveaux messages
"""

import json
from pathlib import Path
from datetime import datetime


class HistoryManager:
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.history_dir = Path(f"history_{client_id}")
        self.history_dir.mkdir(exist_ok=True)
        self.messages = {}

    def get_timestamp(self) -> str:
        """Retourne un timestamp formaté."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def load(self):
        """Charge l'historique depuis les fichiers JSON."""
        for history_file in self.history_dir.glob("*.json"):
            peer_id = history_file.stem
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    self.messages[peer_id] = json.load(f)
                print(f"[SYSTEM] Historique chargé pour '{peer_id}' ({len(self.messages[peer_id])} messages)")
            except Exception as e:
                print(f"[WARNING] Impossible de charger l'historique pour '{peer_id}': {e}")

    def save(self, peer_id: str):
        """Sauvegarde l'historique d'une conversation."""
        if peer_id not in self.messages:
            return

        history_file = self.history_dir / f"{peer_id}.json"
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.messages[peer_id], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARNING] Impossible de sauvegarder l'historique pour '{peer_id}': {e}")

    def add_message(self, peer_id: str, from_id: str, message: str, verified: bool = True) -> dict:
        """Ajoute un message à l'historique et le sauvegarde."""
        if peer_id not in self.messages:
            self.messages[peer_id] = []

        msg_entry = {
            "from": from_id,
            "message": message,
            "timestamp": self.get_timestamp(),
            "verified": verified
        }
        self.messages[peer_id].append(msg_entry)
        self.save(peer_id)
        return msg_entry

    def get_messages(self, peer_id: str, limit: int = 50) -> list:
        """Retourne les derniers messages d'une conversation."""
        if peer_id in self.messages:
            return self.messages[peer_id][-limit:]
        return []

    def show(self, peer_id: str, client_id: str):
        """Affiche l'historique d'une conversation."""
        if peer_id not in self.messages:
            print(f"[{self.get_timestamp()}] [SYSTEM] Aucun historique disponible")
            return

        print(f"\n[SYSTEM] Historique avec '{peer_id}':")
        print("-" * 50)
        for msg in self.messages[peer_id][-20:]:
            verified = "[OK]" if msg.get("verified", True) else "[NOTOK]"
            sender = "Moi" if msg["from"] == client_id else msg["from"]
            print(f"[{msg['timestamp']}] {verified} {sender}: {msg['message']}")
        print("-" * 50)
