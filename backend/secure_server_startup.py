#!/usr/bin/env python3
"""
Secure server startup with license validation and model decryption.
This wraps the main server and ensures security checks before starting.
"""

import os
import sys
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from secure_license_validator import SecureStartupValidator
from secure_model_manager import SecureModelManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def secure_startup():
    """
    Perform secure startup sequence:
    1. Validate license
    2. Decrypt models
    3. Start server
    """
    print("=" * 70)
    print("  🔒 SNF-AI Windsurf - Secure Startup")
    print("=" * 70)
    print("")
    
    # Step 1: Validate license
    print("🔑 Step 1: License Validation")
    print("-" * 70)
    
    validator = SecureStartupValidator()
    success, message, decryption_seed = validator.validate_and_start()
    
    if not success:
        print(f"\n❌ License validation failed: {message}")
        print("")
        print("Please ensure:")
        print("  1. SNF_LICENSE_KEY environment variable is set")
        print("  2. License key is valid and not expired")
        print("  3. License is activated for this device")
        print("")
        print("Get a license at: https://web-production-d31c0.up.railway.app/register")
        print("")
        sys.exit(1)
    
    print(f"✓ {message}")
    print("")
    
    # Step 2: Decrypt models
    print("🔓 Step 2: Model Decryption")
    print("-" * 70)
    
    models_dir = Path(__file__).parent.parent / 'models'
    model_manager = SecureModelManager(models_dir)
    
    # Check if models are encrypted
    encrypted_models = list(models_dir.glob('*.encrypted'))
    
    if encrypted_models:
        print(f"Found {len(encrypted_models)} encrypted model(s)")
        print("Decrypting models...")
        
        try:
            from secure_license_validator import HardwareFingerprint
            device_id = HardwareFingerprint.get_device_id()
            license_key = os.environ.get('SNF_LICENSE_KEY')
            
            decrypted = model_manager.decrypt_all_models(
                license_key,
                device_id,
                decryption_seed
            )
            
            print(f"✓ Decrypted {len(decrypted)} model(s):")
            for model_name, path in decrypted.items():
                print(f"  - {model_name}")
            
            # Store decrypted paths in environment for nodes to use
            os.environ['SNF_DECRYPTED_MODELS'] = str(model_manager.models_dir)
            
        except Exception as e:
            print(f"\n❌ Model decryption failed: {e}")
            print("")
            print("Possible causes:")
            print("  1. License key mismatch")
            print("  2. Device ID changed")
            print("  3. Corrupted encrypted files")
            print("")
            sys.exit(1)
    else:
        print("No encrypted models found - using unencrypted models")
        print("(Development mode)")
    
    print("")
    
    # Step 3: Start server
    print("🚀 Step 3: Starting Server")
    print("-" * 70)
    print("")
    
    # Import and run the actual server
    try:
        from server import create_app
        
        app = create_app()
        port = int(os.environ.get('PORT', 5002))
        
        print(f"✓ Server initialized")
        print("")
        print("=" * 70)
        print(f"  🎉 SNF-AI Windsurf Running on http://0.0.0.0:{port}")
        print("=" * 70)
        print("")
        print(f"  📊 Dashboard: http://localhost:{port}/dashboard/")
        print(f"  🔧 API: http://localhost:{port}/query")
        print(f"  📝 Status: http://localhost:{port}/status")
        print("")
        print(f"  License: ✓ Valid")
        print(f"  Heartbeat: ✓ Active (checking every 6 hours)")
        print("")
        print("=" * 70)
        print("")
        
        app.run(host='0.0.0.0', port=port, debug=False)
        
    except Exception as e:
        print(f"\n❌ Server startup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    try:
        secure_startup()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
