# 🔒 Quick Start: Secure Deployment

## For You (Distributor)

### One-Time Setup

```bash
# 1. Download models from Hugging Face
python3 backend/model_downloader.py

# 2. Generate and save master encryption key
export SNF_MASTER_ENCRYPTION_KEY=$(openssl rand -base64 32)
echo $SNF_MASTER_ENCRYPTION_KEY > master_key.secret
chmod 600 master_key.secret

# 3. Encrypt models
./scripts/encrypt_models.sh

# 4. Build and push Docker image
docker build -f Dockerfile.secure -t YOUR_USERNAME/snf-ai-windsurf:latest .
docker push YOUR_USERNAME/snf-ai-windsurf:latest

# 5. Make Docker Hub repository private

# 6. Deploy license server to Railway
# Upload: backend/license_api_server.py
# Set env: SNF_SECRET_SALT, SNF_ADMIN_SECRET
```

## For Customers

### Installation

```bash
# 1. Get your 30-day license key from: https://your-license-server.up.railway.app/register

# 2. Set license key
export SNF_LICENSE_KEY="SNF-XXXXXXXX-XXXXXXXX"

# 3. Pull and run
docker login  # Use provided credentials
docker-compose -f docker-compose.secure.yml up
```

### Access
- **Application**: http://localhost:5002
- **Dashboard**: http://localhost:5002/dashboard/

## 🛡️ Security Summary

✅ **Private Docker Registry** - Can't download without auth  
✅ **Encrypted Models** - Useless without valid license  
✅ **License Validation** - Online check required  
✅ **Hardware Binding** - One device per license  
✅ **Heartbeat Monitoring** - Re-validates every 6 hours  
✅ **72-Hour Grace** - Works offline temporarily  

## 📋 Checklist

### Distributor
- [ ] Downloaded models from Hugging Face
- [ ] Generated and saved master encryption key
- [ ] Encrypted all model files
- [ ] Built secure Docker image
- [ ] Pushed to private Docker Hub
- [ ] Deployed license server to Railway
- [ ] Tested full workflow

### Customer
- [ ] Received license key
- [ ] Received Docker Hub credentials
- [ ] Set SNF_LICENSE_KEY environment variable
- [ ] Pulled Docker image
- [ ] Started container
- [ ] Accessed application at localhost:5002

## 🆘 Troubleshooting

### Build Issues
```bash
# Models not encrypting?
ls -lh models/*.gguf  # Should exist before encryption
echo $SNF_MASTER_ENCRYPTION_KEY  # Should be set

# Docker build failing?
docker build -f Dockerfile.secure -t test:latest . --no-cache
```

### Customer Issues
```bash
# License validation failed?
docker logs snf-ai-windsurf  # Check logs
curl http://localhost:5002/status  # Check server

# Can't pull image?
docker login  # Re-authenticate
docker pull YOUR_USERNAME/snf-ai-windsurf:latest
```

## 📚 Full Documentation

- **Complete Guide**: See [SECURE_DEPLOYMENT_GUIDE.md](./SECURE_DEPLOYMENT_GUIDE.md)
- **License API**: See [license_api_server.py](./backend/license_api_server.py)
- **Security Code**: See [secure_license_validator.py](./backend/secure_license_validator.py)

## ⚠️ Important Notes

1. **Never lose master encryption key** - You can't rebuild images without it
2. **Keep SECRET_SALT secret** - Used for decryption seed generation
3. **Use HTTPS** - License server must use HTTPS in production
4. **Backup licenses** - Save license_database.json regularly
5. **Monitor usage** - Check validation logs for abuse

---

**Ready to deploy?** Follow [SECURE_DEPLOYMENT_GUIDE.md](./SECURE_DEPLOYMENT_GUIDE.md) for detailed steps.
