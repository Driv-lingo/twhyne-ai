# Simple Monthly License System

## How It Works

1. **User gets license key** (30-day validity)
2. **Docker container checks license on startup**
3. **License checked daily while running**
4. **Container exits if license expires**

No model encryption. Simple and effective.

---

## For You (Distributor)

### Step 1: Deploy License Server to Railway

The license server (`backend/license_api_server.py`) generates and validates licenses.

**Quick Deploy:**
1. Push this code to GitHub
2. Create new Railway service from GitHub
3. Set Root Directory to `backend`
4. Add environment variables:
   ```
   SNF_SECRET_SALT=<run: openssl rand -hex 16>
   SNF_ADMIN_SECRET=<password-for-admin-api>
   PORT=5003
   ```
5. Deploy

### Step 2: Build & Push Docker Image

```bash
# Build
docker build -t yourname/snf-ai-windsurf:latest .

# Push to Docker Hub (make repository PRIVATE)
docker push yourname/snf-ai-windsurf:latest
```

### Step 3: Generate License for Customer

```bash
# Generate 30-day license
curl -X POST https://your-railway-app.up.railway.app/api/registration/register \
  -H "Content-Type: application/json" \
  -d '{"email": "customer@example.com"}'

# Response includes license key:
# "license_key": "SNF-XXXXXXXX-XXXXXXXX"
```

### Step 4: Give Customer:
1. Docker Hub credentials (or pull token)
2. License key
3. Installation instructions (see below)

---

## For Customers

### Installation

```bash
# 1. Set your license key
export SNF_LICENSE_KEY="SNF-XXXXXXXX-XXXXXXXX"

# 2. Login to Docker Hub (use provided credentials)
docker login

# 3. Pull and run
docker-compose -f docker-compose.licensed.yml up
```

### Access
- Application: http://localhost:5002
- Dashboard: http://localhost:5002/dashboard/

---

## License Management

### Extend License (30 more days)

```bash
curl -X POST https://your-railway-app.up.railway.app/api/admin/extend \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "SNF-XXXXXXXX-XXXXXXXX",
    "additional_days": 30,
    "admin_secret": "your-admin-secret"
  }'
```

### Revoke License

```bash
curl -X POST https://your-railway-app.up.railway.app/api/admin/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "SNF-XXXXXXXX-XXXXXXXX",
    "admin_secret": "your-admin-secret"
  }'
```

### Check License Status

```bash
# Customer can check their license
curl -X POST https://your-railway-app.up.railway.app/api/registration/validate \
  -H "Content-Type: application/json" \
  -d '{"license_key": "SNF-XXXXXXXX-XXXXXXXX"}'
```

---

## What Happens When License Expires

1. **On startup**: Container won't start, shows error message
2. **While running**: Daily check detects expiration, container exits
3. **Customer action**: Must renew license to continue

---

## Security Features

✅ **License validation on startup** - Can't run without valid license  
✅ **Daily license checks** - Catches expiration while running  
✅ **30-day expiration** - Automatic monthly billing cycle  
✅ **Private Docker image** - Need credentials to pull  
✅ **Server-side validation** - Can't be bypassed locally  
✅ **Remote revocation** - Cancel access instantly  

---

## Files Overview

- `backend/simple_license_check.py` - License validation logic
- `backend/license_api_server.py` - License server for Railway
- `start.sh` - Modified to check license before startup
- `docker-compose.licensed.yml` - Requires license key
- `Dockerfile` - No changes needed

---

## Testing

### Test Locally

```bash
# Start license server
cd backend
python3 license_api_server.py &

# Generate test license
curl -X POST http://localhost:5003/api/registration/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com"}'

# Use license
export SNF_LICENSE_KEY="SNF-XXXXXXXX-XXXXXXXX"
docker-compose -f docker-compose.licensed.yml up
```

### Test License Expiration

```bash
# In license_api_server.py, temporarily change:
# duration_days = data.get('duration_days', 30)
# to:
# duration_days = data.get('duration_days', 1)  # 1 day for testing

# Generate short-lived license
curl -X POST http://localhost:5003/api/registration/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "duration_days": 1}'

# Wait 24 hours or modify the date check
```

---

## Troubleshooting

### "License key not provided"
- Set `SNF_LICENSE_KEY` environment variable
- Check docker-compose.licensed.yml has the variable

### "License validation failed"
- Check license hasn't expired
- Verify license server is accessible
- Test with curl manually

### Container exits after running
- License expired - extend or renew
- Daily check failed - check server logs

---

## Next Steps

1. ✅ Test license server locally
2. ✅ Deploy license server to Railway  
3. ✅ Build Docker image
4. ✅ Push to private Docker Hub
5. ✅ Generate test license
6. ✅ Test full flow
7. ✅ Distribute to first customer

**Simple, effective, no complex encryption needed!**
