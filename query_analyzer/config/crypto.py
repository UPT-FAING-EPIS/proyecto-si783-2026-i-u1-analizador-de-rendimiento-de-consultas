"""Gestión de cifrado y descifrado de credenciales."""

import base64
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .exceptions import EncryptionError


class CryptoManager:
    """
    Gestiona cifrado/descifrado de credenciales usando Fernet (AES-128).

    La llave se almacena en ~/.query-analyzer/.key con permisos restrictivos (0o600).
    Si la llave no existe, se genera automáticamente.
    """

    KEY_FILE = Path.home() / ".query-analyzer" / ".key"
    CONFIG_DIR = Path.home() / ".query-analyzer"

    @classmethod
    def _get_or_create_key(cls) -> bytes:
        """
        Obtiene la llave de cifrado o la crea si no existe.

        Returns:
            Llave de Fernet en bytes

        Raises:
            EncryptionError: Si hay problema al crear/leer la llave
        """
        # Crear directorio si no existe
        try:
            cls.CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        except OSError as e:
            raise EncryptionError(f"No se puede crear directorio de config: {e}")

        # Si la llave existe, leerla
        if cls.KEY_FILE.exists():
            try:
                return cls.KEY_FILE.read_bytes()
            except OSError as e:
                raise EncryptionError(f"No se puede leer llave de cifrado: {e}")

        # Generar nueva llave
        try:
            new_key = Fernet.generate_key()
            cls.KEY_FILE.write_bytes(new_key)
            cls.KEY_FILE.chmod(0o600)  # Solo lectura/escritura para propietario
            return new_key
        except OSError as e:
            raise EncryptionError(f"No se puede crear llave de cifrado: {e}")

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """
        Cifra un texto plano.

        Args:
            plaintext: Texto a cifrar

        Returns:
            Texto cifrado codificado en base64 (con prefijo 'enc:')

        Raises:
            EncryptionError: Si falla el cifrado
        """
        try:
            key = cls._get_or_create_key()
            cipher = Fernet(key)
            # Cifrar y codificar en base64
            ciphertext = cipher.encrypt(plaintext.encode("utf-8"))
            # Agregar prefijo para identificar datos cifrados
            return f"enc:{base64.b64encode(ciphertext).decode('utf-8')}"
        except Exception as e:
            raise EncryptionError(f"Error al cifrar datos: {e}")

    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        """
        Descifra un texto cifrado.

        Args:
            ciphertext: Texto cifrado (con prefijo 'enc:')

        Returns:
            Texto descifrado

        Raises:
            EncryptionError: Si falla el descifrado
        """
        try:
            # Verificar prefijo
            if not ciphertext.startswith("enc:"):
                # Si no tiene prefijo, devolver como está (para compatibilidad)
                return ciphertext

            # Eliminar prefijo y decodificar de base64
            encrypted_data = base64.b64decode(ciphertext[4:])

            # Descifrar
            key = cls._get_or_create_key()
            cipher = Fernet(key)
            plaintext = cipher.decrypt(encrypted_data)
            return plaintext.decode("utf-8")
        except InvalidToken:
            raise EncryptionError("Contraseña cifrada inválida (token corrupto)")
        except Exception as e:
            raise EncryptionError(f"Error al descifrar datos: {e}")

    @classmethod
    def is_encrypted(cls, text: str) -> bool:
        """Verifica si un texto está cifrado."""
        return text.startswith("enc:")
