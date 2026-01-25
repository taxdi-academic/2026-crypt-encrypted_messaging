"""
Fonctions utilitaires pour la cryptographie.
- Chiffrement/déchiffrement RSA
- Chiffrement/déchiffrement AES
- Signature et vérification RSA
"""

import base64
import secrets
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


def generate_rsa_keypair():
    """Génère une paire de clés RSA-2048."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    return private_key, private_key.public_key()


def public_key_to_pem(public_key) -> bytes:
    """Convertit une clé publique en format PEM."""
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )


def load_public_key_from_pem(pem_data: bytes):
    """Charge une clé publique depuis le format PEM."""
    return serialization.load_pem_public_key(pem_data, backend=default_backend())


def decrypt_rsa(private_key, encrypted_data: bytes) -> bytes:
    """Déchiffre des données avec une clé privée RSA (OAEP)."""
    return private_key.decrypt(
        encrypted_data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )


def sign_message(private_key, message: str) -> bytes:
    """Signe un message avec une clé privée RSA (PSS)."""
    return private_key.sign(
        message.encode('utf-8'),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )


def verify_signature(public_key, message: str, signature: bytes) -> bool:
    """Vérifie la signature d'un message. Retourne True si valide."""
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


def encrypt_aes(plaintext: bytes, aes_key: bytes) -> tuple:
    """Chiffre des données avec AES-256-CBC. Retourne (ciphertext, iv)."""
    iv = secrets.token_bytes(16)

    # Padding PKCS7
    block_size = 16
    padding_len = block_size - (len(plaintext) % block_size)
    padded = plaintext + bytes([padding_len] * padding_len)

    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    return ciphertext, iv


def decrypt_aes(ciphertext: bytes, iv: bytes, aes_key: bytes) -> bytes:
    """Déchiffre des données avec AES-256-CBC."""
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    # Remove PKCS7 padding
    padding_len = padded[-1]
    return padded[:-padding_len]
