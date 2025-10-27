#!/usr/bin/env python3
"""
Secure model encryption and decryption system.
Models are encrypted at build time and decrypted at runtime using license-derived keys.
"""

import os
import hashlib
import secrets
from pathlib import Path
from typing import Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import logging

logger = logging.getLogger(__name__)

# Master key for initial encryption (keep secret, used only during build)
MASTER_KEY_ENV = "SNF_MASTER_ENCRYPTION_KEY"

class ModelEncryption:
    """Handles model file encryption and decryption."""
    
    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,  # OWASP recommended
        )
        return kdf.derive(password.encode())
    
    @staticmethod
    def encrypt_model_file(input_path: Path, output_path: Path, master_key: str) -> dict:
        """
        Encrypt a model file with master key.
        Used during Docker image build process.
        
        Args:
            input_path: Path to unencrypted model file
            output_path: Path to save encrypted model
            master_key: Master encryption key
            
        Returns:
            dict: Metadata including salt and checksum
        """
        logger.info(f"Encrypting model: {input_path}")
        
        # Generate random salt
        salt = secrets.token_bytes(32)
        
        # Derive encryption key
        key = ModelEncryption.derive_key(master_key, salt)
        cipher = Fernet(key)
        
        # Read and encrypt model file in chunks (for large files)
        chunk_size = 64 * 1024 * 1024  # 64MB chunks
        
        with open(input_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                # Write salt first (needed for decryption)
                f_out.write(salt)
                
                # Encrypt file in chunks
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    encrypted_chunk = cipher.encrypt(chunk)
                    f_out.write(encrypted_chunk)
        
        # Calculate checksum of encrypted file
        checksum = ModelEncryption._calculate_checksum(output_path)
        
        logger.info(f"Model encrypted successfully: {output_path}")
        
        return {
            'original_size': input_path.stat().st_size,
            'encrypted_size': output_path.stat().st_size,
            'checksum': checksum,
            'algorithm': 'Fernet-PBKDF2-SHA256'
        }
    
    @staticmethod
    def decrypt_model_to_memory(encrypted_path: Path, license_key: str, device_id: str, seed: str) -> bytes:
        """
        Decrypt model file into memory using license-derived key.
        Used at runtime when user has valid license.
        
        Args:
            encrypted_path: Path to encrypted model file
            license_key: User's license key
            device_id: Hardware fingerprint
            seed: Server-provided decryption seed
            
        Returns:
            bytes: Decrypted model data in memory
        """
        logger.info(f"Decrypting model: {encrypted_path}")
        
        # Derive decryption password from license components
        password = f"{license_key}:{device_id}:{seed}"
        
        with open(encrypted_path, 'rb') as f:
            # Read salt from file header
            salt = f.read(32)
            
            # Derive decryption key
            key = ModelEncryption.derive_key(password, salt)
            cipher = Fernet(key)
            
            # Decrypt entire file
            encrypted_data = f.read()
            decrypted_data = cipher.decrypt(encrypted_data)
        
        logger.info(f"Model decrypted successfully: {len(decrypted_data)} bytes")
        return decrypted_data
    
    @staticmethod
    def decrypt_model_to_temp_file(encrypted_path: Path, license_key: str, device_id: str, seed: str) -> Path:
        """
        Decrypt model to temporary file that is deleted on exit.
        Use this for llama.cpp which needs file paths.
        
        Returns:
            Path: Temporary file path (auto-deleted on process exit)
        """
        import tempfile
        import atexit
        
        decrypted_data = ModelEncryption.decrypt_model_to_memory(
            encrypted_path, license_key, device_id, seed
        )
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.gguf')
        temp_path = Path(temp_file.name)
        
        # Write decrypted data
        temp_file.write(decrypted_data)
        temp_file.close()
        
        # Register cleanup on exit
        atexit.register(lambda: temp_path.unlink(missing_ok=True))
        
        logger.info(f"Model decrypted to temporary file: {temp_path}")
        return temp_path
    
    @staticmethod
    def _calculate_checksum(file_path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()


class SecureModelManager:
    """Manages encrypted model files for the application."""
    
    def __init__(self, models_dir: Path):
        self.models_dir = Path(models_dir)
        self.decrypted_models = {}
        
    def encrypt_all_models(self, master_key: str) -> dict:
        """
        Encrypt all .gguf files in models directory.
        This is run during Docker image build.
        
        Returns:
            dict: Encryption metadata for all models
        """
        metadata = {}
        
        # Find all unencrypted model files
        for model_file in self.models_dir.glob('*.gguf'):
            if model_file.suffix == '.encrypted':
                continue
            
            encrypted_path = model_file.with_suffix('.gguf.encrypted')
            
            # Encrypt model
            model_meta = ModelEncryption.encrypt_model_file(
                model_file,
                encrypted_path,
                master_key
            )
            
            metadata[model_file.name] = model_meta
            
            # Delete unencrypted original
            model_file.unlink()
            logger.info(f"Deleted unencrypted file: {model_file}")
        
        return metadata
    
    def decrypt_model(self, model_name: str, license_key: str, device_id: str, seed: str) -> Path:
        """
        Decrypt a specific model file.
        
        Args:
            model_name: Name of model (e.g., 'mistral-7b-instruct-q4.gguf')
            license_key: User's license key
            device_id: Hardware fingerprint
            seed: Server-provided seed
            
        Returns:
            Path: Path to decrypted model file (temporary)
        """
        encrypted_path = self.models_dir / f"{model_name}.encrypted"
        
        if not encrypted_path.exists():
            raise FileNotFoundError(f"Encrypted model not found: {encrypted_path}")
        
        # Check cache
        if model_name in self.decrypted_models:
            logger.info(f"Using cached decrypted model: {model_name}")
            return self.decrypted_models[model_name]
        
        # Decrypt to temporary file
        decrypted_path = ModelEncryption.decrypt_model_to_temp_file(
            encrypted_path,
            license_key,
            device_id,
            seed
        )
        
        # Cache the path
        self.decrypted_models[model_name] = decrypted_path
        
        return decrypted_path
    
    def decrypt_all_models(self, license_key: str, device_id: str, seed: str) -> dict:
        """
        Decrypt all encrypted models.
        
        Returns:
            dict: Mapping of model names to decrypted paths
        """
        decrypted = {}
        
        for encrypted_file in self.models_dir.glob('*.encrypted'):
            model_name = encrypted_file.name.replace('.encrypted', '')
            
            try:
                decrypted_path = self.decrypt_model(
                    model_name,
                    license_key,
                    device_id,
                    seed
                )
                decrypted[model_name] = decrypted_path
            except Exception as e:
                logger.error(f"Failed to decrypt {model_name}: {e}")
                raise
        
        return decrypted


# Build-time script to encrypt models
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python secure_model_manager.py <encrypt|decrypt>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'encrypt':
        # Get master key from environment
        master_key = os.environ.get(MASTER_KEY_ENV)
        if not master_key:
            print(f"Error: {MASTER_KEY_ENV} environment variable not set")
            sys.exit(1)
        
        models_dir = Path(__file__).parent.parent / 'models'
        manager = SecureModelManager(models_dir)
        
        print("Encrypting all models...")
        metadata = manager.encrypt_all_models(master_key)
        
        print("\nEncryption complete:")
        for model, meta in metadata.items():
            print(f"  {model}: {meta['encrypted_size'] / 1024 / 1024:.1f} MB")
        
        print("\nModels encrypted successfully!")
        print("Original files have been deleted.")
        
    elif command == 'decrypt':
        print("Error: Decryption requires license key, device ID, and seed")
        print("Decryption happens automatically at runtime with valid license")
        sys.exit(1)
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
