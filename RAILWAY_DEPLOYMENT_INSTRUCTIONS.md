# Railway License Server Deployment Instructions

## Step-by-Step Deployment

### 1. Create Railway Account
- Go to https://railway.app
- Sign up with GitHub

### 2. Create New Project
- Click "New Project"
- Select "Deploy from GitHub repo"
- Connect your GitHub account
- Select the `SNF_AI_Demo/clean-windsurf` repository

### 3. Configure Build Settings

In Railway dashboard:
- **Root Directory**: Leave blank (uses project root)
- **Build Command**: `pip install -r requirements-api.txt`
- **Start Command**: `cd backend && python3 license_api_server.py`

### 4. Set Environment Variables

Click "Variables" tab and add:

```bash
SNF_SECRET_SALT=<generate-random-32-char-string>
SNF_ADMIN_SECRET=<your-admin-password>
PORT=5003
```

**Generate SECRET_SALT:**
```bash
openssl rand -hex 16
```

**Generate ADMIN_SECRET:**
```bash
openssl rand -base64 24
```

**IMPORTANT**: Save these values securely! You'll need them for:
- `SNF_SECRET_SALT` - Model decryption seed generation
- `SNF_ADMIN_SECRET` - Admin API access (revoke/extend licenses)

### 5. Deploy

- Click "Deploy"
- Wait for build to complete (~2-3 minutes)
- Railway will provide a public URL like: `https://your-app-name.up.railway.app`

### 6. Test Deployment

```bash
# Test registration endpoint
curl -X POST https://your-app-name.up.railway.app/api/registration/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# Expected response:
{
  "success": true,
  "license_key": "SNF-XXXXXXXX-XXXXXXXX",
  "email": "test@example.com",
  "expiry_date": "2025-11-26T...",
  "duration_days": 30,
  "message": "Registration successful. Your license is valid for 30 days."
}
```

### 7. Update Your Code

Update the LICENSE_API URL in your code:

```python
# In backend/secure_license_validator.py
LICENSE_API = os.environ.get(
    'SNF_LICENSE_API',
    'https://your-app-name.up.railway.app'  # Replace with your Railway URL
)
```

## Admin Operations

### Revoke a License

```bash
curl -X POST https://your-app-name.up.railway.app/api/admin/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "SNF-XXXXXXXX-XXXXXXXX",
    "admin_secret": "your-admin-secret"
  }'
```

### Extend a License

```bash
curl -X POST https://your-app-name.up.railway.app/api/admin/extend \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "SNF-XXXXXXXX-XXXXXXXX",
    "additional_days": 30,
    "admin_secret": "your-admin-secret"
  }'
```

### Check Status

```bash
curl https://your-app-name.up.railway.app/api/status
```

## Troubleshooting

### Build Fails
- Check that `requirements-api.txt` exists and has correct dependencies
- Verify Python version (should be 3.11+)

### Server Won't Start
- Check logs in Railway dashboard
- Verify environment variables are set
- Ensure PORT is set to 5003

### License Validation Fails
- Check that SNF_SECRET_SALT is set
- Verify the server is publicly accessible
- Test with curl first

## Next Steps

After successful deployment:
1. ✅ License server is live
2. ⏭️ Update LICENSE_API in code
3. ⏭️ Test license validation flow
4. ⏭️ Proceed to model encryption
