# Messagerie Chiffrée avec Serveur de Confiance

Système de messagerie sécurisée implémentant un protocole de distribution de clés inspiré de Needham-Schroeder, développé dans le cadre du TP2 de Protocoles Cryptographiques à l'ENSIBS.

## Architecture

```
┌─────────────┐                    ┌─────────────┐
│   Client A  │◄──── AES-256 ────►│   Client B  │
│  (RSA-2048) │                    │  (RSA-2048) │
└──────┬──────┘                    └──────┬──────┘
       │                                  │
       │    ┌───────────────────┐        │
       └───►│  Serveur (KDC)    │◄───────┘
            │  Distribution des │
            │  clés de session  │
            └───────────────────┘
```

## Protocole Cryptographique

### Algorithmes utilisés

| Composant | Algorithme | Taille de clé |
|-----------|------------|---------------|
| Chiffrement asymétrique | RSA-OAEP | 2048 bits |
| Chiffrement symétrique | AES-CBC | 256 bits |
| Signature | RSA-PSS | 2048 bits |
| Hachage | SHA-256 | 256 bits |
| Padding (AES) | PKCS7 | - |

### Flux d'établissement de session

1. **Enregistrement** : Chaque client génère une paire RSA-2048 et enregistre sa clé publique auprès du serveur
2. **Demande de session** : Le client A demande une session avec le client B
3. **Génération de clé** : Le serveur génère une clé AES-256 aléatoire
4. **Distribution** : Le serveur chiffre la clé AES avec la clé publique RSA de chaque client (OAEP)
5. **Établissement** : Les clients déchiffrent la clé AES et peuvent communiquer de manière sécurisée

### Sécurité des messages

- **Confidentialité** : Messages chiffrés en AES-256-CBC avec IV aléatoire
- **Authenticité** : Chaque message est signé avec RSA-PSS (SHA-256)
- **Intégrité** : La signature garantit que le message n'a pas été altéré

## Installation

### Prérequis

- Python 3.8+
- pip

### Dépendances

```bash
pip install flask cryptography requests
```

## Utilisation

### 1. Démarrer le serveur de confiance

```bash
python server.py
```

Le serveur écoute sur le port 5000.

### 2. Démarrer les clients

Dans des terminaux séparés :

```bash
# Terminal 1 - Alice
python client.py alice 5001

# Terminal 2 - Bob
python client.py bob 5002
```

### 3. Établir une communication

Depuis le terminal d'Alice :

```
/list                  # Affiche les clients disponibles
/connect bob           # Établit une session sécurisée avec Bob
Bonjour Bob !          # Envoie un message chiffré
```

### Commandes disponibles

| Commande | Description |
|----------|-------------|
| `/list` | Liste les clients enregistrés |
| `/connect <id>` | Établit une session avec un client |
| `/sessions` | Affiche les sessions actives |
| `/switch <id>` | Change la session courante |
| `/history [id]` | Affiche l'historique des messages |
| `/quit` | Ferme le client |

### Interface Web

Chaque client expose une interface web accessible à l'adresse :

```
http://127.0.0.1:<port>
```

## Structure du Projet

```
TP2/
├── server.py           # Serveur de distribution de clés (KDC)
├── client.py           # Point d'entrée du client
├── secure_client.py    # Logique principale du client
├── crypto_utils.py     # Fonctions cryptographiques
├── history.py          # Gestion de l'historique
├── index.html          # Interface web (accueil)
├── chat.html           # Interface web (chat)
├── keys/               # Stockage des clés (généré)
└── history_<id>/       # Historique des conversations (généré)
```

## API du Serveur

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/register` | POST | Enregistre un client avec sa clé publique |
| `/clients` | GET | Liste les clients enregistrés |
| `/get_public_key/<id>` | GET | Récupère la clé publique d'un client |
| `/request_session` | POST | Demande une session entre deux clients |
| `/pending_invitations/<id>` | GET | Récupère les invitations en attente |
| `/get_session_key` | POST | Récupère la clé de session chiffrée |
| `/active_sessions/<id>` | GET | Liste les sessions actives d'un client |

## Exemple de communication

```
[ENVOI] Message vers bob
[CLAIR] Bonjour Bob !
[CHIFFRE] a3Kj8mN2pQ5rS7vX9zA1bC3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW3xY5zA7bC9dE...
[IV] f1G2h3I4j5K6l7M8n9O0
[SIGNATURE] p1Q2r3S4t5U6v7W8x9Y0a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0...

[RECEPTION] Message de alice
[CHIFFRE] a3Kj8mN2pQ5rS7vX9zA1bC3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW3xY5zA7bC9dE...
[IV] f1G2h3I4j5K6l7M8n9O0
[CLAIR] Bonjour Bob !
[SIGNATURE] [OK]
```

## Sécurité

### Points forts

- Clés de session uniques pour chaque paire de clients
- IV aléatoire pour chaque message (pas de réutilisation)
- Signature de tous les messages pour l'authentification
- Clés RSA générées à chaque démarrage du client

### Limitations (contexte pédagogique)

- Le serveur de confiance est un point de confiance unique (single point of trust)
- Pas de perfect forward secrecy (PFS)
- Les clés privées sont en mémoire uniquement
- Pas de gestion de révocation des clés

## Auteur

Eliot MAHÉ - ENSIBS - Protocoles Cryptographiques TP2
