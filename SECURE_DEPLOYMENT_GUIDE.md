# SNF-AI Windsurf Secure Deployment Guide

This guide explains how to build and deploy the license-protected, encrypted version of SNF-AI Windsurf.

## 🔒 Security Architecture

### Multi-Layer Protection

1. **Private Docker Registry** - Only licensed users can pull images
2. **Encrypted Model Files** - Models encrypted with master key
3. **License Validation** - Online validation with server
4. **Hardware Binding** - License tied to specific device
5. **Periodic Heartbeat** - Re-validation every 6 hours
6. **Code Integrity** - Tampering detection
7. **Decryption Seeds** - Unique per-license decryption keys

### How It Works

```
Build Time (Your Side):
1. Download models from Hugging Face
2. Encrypt with MASTER KEY
3. Build Docker image with encrypted models
4. Push to PRIVATE Docker Hub

Runtime (Customer Side):
1. Customer provides LICENSE KEY
2. License validated with server
3. Server returns DECRYPTION SEED
4. Models decrypted using: license + device_id + seed
5. Decrypted models loaded into memory
6. Heartbeat monitoring starts
```

## 🛠️ Build Process

### Prerequisites

- Python 3.11+
- Docker and Docker Hub account
- Hugging Face account (for model downloads)
- Railway deployment (for license API)

### Step 1: Download Models

First, download the required models from Hugging Face:

```bash
# Run model downloader
python3 backend/model_downloader.py

# This downloads:
# - mistral-7b-instruct-q4.gguf (~4GB)
# - codellama-7b-q4.gguf (~4GB)
# - llava-v1.5-7b-Q4_K.gguf (~4GB)
# - mmproj-model-f16.gguf (~600MB)
```

### Step 2: Encrypt Models

Generate a secure master encryption key and encrypt models:

```bash
# Generate strong master key (save this securely!)
export SNF_MASTER_ENCRYPTION_KEY=$(openssl rand -base64 32)

# Save the key somewhere safe
echo $SNF_MASTER_ENCRYPTION_KEY > master_key.secret
chmod 600 master_key.secret

# Encrypt all models
./scripts/encrypt_models.sh
```

**CRITICAL**: 
- Keep `SNF_MASTER_ENCRYPTION_KEY` secret and secure
- Never commit it to Git
- You'll need it for future builds
- Losing it means you can't build new images

After encryption:
- Original `.gguf` files are deleted
- Encrypted `.gguf.encrypted` files remain
- Ready for Docker build

### Step 3: Build Secure Docker Image

```bash
# Build the secure image
docker build -f Dockerfile.secure -t snf-ai-windsurf:secure .

# Tag for your private Docker Hub
docker tag snf-ai-windsurf:secure YOUR_USERNAME/snf-ai-windsurf:latest

# Push to private registry
docker login
docker push YOUR_USERNAME/snf-ai-windsurf:latest
```

### Step 4: Make Repository Private

1. Go to Docker Hub: https://hub.docker.com
2. Navigate to your repository
3. Settings → Make Private
4. (Optional) Set up access tokens per customer

### Step 5: Update License API

Update your Railway deployment to support decryption seeds:

```python
# In your test_server.py or license server

@app.route('/api/registration/validate', methods=['POST'])
def validate_license():
    data = request.get_json()
    license_key = data.get('license_key')
    device_id = data.get('device_id')
    request_seed = data.get('request_seed', False)
    
    # Validate license in your database
    # ...
    
    response = {
        'valid': True,
        'email': user_email,
        'expiry_date': expiry_date.isoformat(),
        'device_id': device_id
    }
    
    # Provide decryption seed if requested
    if request_seed and valid:
        # Generate deterministic seed from license
        seed_material = f"{license_key}:{device_id}:{SECRET_SALT}"
        seed = hashlib.sha256(seed_material.encode()).hexdigest()[:32]
        response['decryption_seed'] = seed
    
    return jsonify(response)
```

## 📦 Customer Distribution

### Option A: Docker Hub Access Token

Generate per-customer access tokens:

```bash
# On Docker Hub:
# Account Settings → Security → New Access Token
# Scope: Read-only access to specific repository
```

Provide customer with:
```bash
# Customer receives:
# 1. Docker Hub credentials or access token
# 2. License key
# 3. Installation instructions

docker login -u customer_username
docker-compose -f docker-compose.secure.yml up
```

### Option B: Pre-authenticated docker-compose

Create a customer-specific docker-compose file:

```yaml
# docker-compose.customer123.yml
version: '3.8'
services:
  snf-ai:
    image: YOUR_USERNAME/snf-ai-windsurf:latest
    environment:
      - SNF_LICENSE_KEY=SNF-CUSTOMER123-XXXXX
    ports:
      - "5002:5002"
```

Customer usage:
```bash
# One-command start
docker-compose -f docker-compose.customer123.yml up
```

## 🚀 Customer Installation Guide

Provide this to your customers:

```markdown
# SNF-AI Windsurf Installation

## Prerequisites
- Docker and Docker Compose installed
- Internet connection for license validation

## Step 1: Set License Key

export SNF_LICENSE_KEY="your-license-key-here"

## Step 2: Pull and Run

docker-compose -f docker-compose.secure.yml up

## Step 3: Access Application

Open browser to: http://localhost:5002

## Troubleshooting

### License Validation Failed
- Check SNF_LICENSE_KEY is correct
- Ensure internet connection for validation
- Verify license hasn't expired

### Model Decryption Failed
- Contact support with your license key
- Device ID may have changed (reinstall license)

### Container Won't Start
- Check Docker logs: docker logs snf-ai-windsurf
- Ensure port 5002 is available
```

## 🔐 Security Best Practices

### For Distributors (You)

1. **Master Key Security**
   - Store in password manager
   - Never commit to Git
   - Backup securely
   - Rotate periodically

2. **Docker Hub**
   - Use private repositories
   - Enable 2FA
   - Per-customer access tokens
   - Regular audit of access

3. **License Server**
   - HTTPS only
   - Rate limiting
   - Logging and monitoring
   - Backup license database

4. **Image Updates**
   - Re-encrypt models with same key
   - Version tagging
   - Changelog for customers

### For Customers

1. **License Key**
   - Keep confidential
   - Don't share
   - One device per license

2. **Environment Variables**
   - Use `.env` files
   - Don't commit license keys
   - Secure file permissions

3. **Network**
   - First start requires internet
   - Subsequent: 72-hour grace period
   - Firewall: allow outbound HTTPS

## 🛡️ Security Features

### What Customers CANNOT Do

- ❌ Run without valid license
- ❌ Copy to another device
- ❌ Extract unencrypted models
- ❌ Bypass license validation
- ❌ Remove heartbeat monitoring
- ❌ Share with others
- ❌ Use after expiration

### What Customers CAN Do

- ✅ Run offline for 72 hours (after initial validation)
- ✅ Update Docker image (with same license)
- ✅ Backup encrypted data
- ✅ Transfer license (contact support)

## 📊 Monitoring & Analytics

Track usage via license API:

```python
# Log every validation request
{
    "license_key": "SNF-XXX",
    "device_id": "abc123",
    "timestamp": "2025-10-27T18:00:00Z",
    "ip_address": "1.2.3.4",
    "container_id": "docker_xyz"
}
```

Monitor for:
- Multiple devices using same license
- Unusual validation patterns
- Expired licenses still in use
- Tampering attempts

## 🔄 License Management

### Revoke License

```python
# In license database
UPDATE licenses 
SET is_active = FALSE 
WHERE license_key = 'SNF-XXX';

# Next heartbeat will fail
# Container shuts down automatically
```

### Transfer License

```python
# Reset device binding
UPDATE licenses 
SET device_id = NULL 
WHERE license_key = 'SNF-XXX';

# Customer re-validates on new device
```

### Extend Expiration

```python
UPDATE licenses 
SET expiry_date = expiry_date + INTERVAL '30 days'
WHERE license_key = 'SNF-XXX';
```

## 🧪 Testing

### Test License Validation

```bash
# Set test license
export SNF_LICENSE_KEY="SNF-TEST-12345678"

# Run validator
python3 backend/secure_license_validator.py
```

### Test Model Encryption/Decryption

```bash
# Encrypt test model
export SNF_MASTER_ENCRYPTION_KEY="test-key-123"
python3 backend/secure_model_manager.py encrypt

# Check encrypted files
ls -lh models/*.encrypted
```

### Test Full Stack

```bash
# Start with test license
export SNF_LICENSE_KEY="SNF-TEST-12345678"
docker-compose -f docker-compose.secure.yml up

# Check logs
docker logs snf-ai-windsurf
```

## 🆘 Support

### Common Issues

**"License validation failed"**
- Check internet connection
- Verify license key
- Check expiration date

**"Device mismatch"**
- License bound to different device
- Contact support to reset

**"Model decryption failed"**
- License/device mismatch
- Corrupted encrypted files
- Contact support

## 📝 Changelog

### Version 1.0.0
- Initial secure deployment system
- Multi-layer security
- Encrypted models
- License validation
- Hardware binding
- Heartbeat monitoring

---

**Questions?** Contact: support@twhyne.com
**License Portal:** https://web-production-d31c0.up.railway.app/register
