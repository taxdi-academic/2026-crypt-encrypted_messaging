#!/usr/bin/env python3
"""
Point d'entrée du client sécurisé.
Usage: python client.py <client_id> <port>
Exemple: python client.py alice 5001
"""

import sys
from secure_client import SecureClient


def main():
    if len(sys.argv) < 3:
        print("Usage: python client.py <client_id> <port>")
        print("Exemple: python client.py alice 5001")
        sys.exit(1)

    client_id = sys.argv[1]
    port = int(sys.argv[2])

    client = SecureClient(client_id, port)
    client.run()


if __name__ == "__main__":
    main()
