# Railway Deployment Checklist

## Your Railway URL
```
https://web-production-5980e.up.railway.app
```

## Deployment Status Checklist

### 1. Verify Railway Project Settings

In Railway Dashboard (https://railway.app):

- [ ] **Project Created**: Project exists in your Railway account
- [ ] **GitHub Connected**: Repository linked correctly
- [ ] **Service Created**: Service is running (not stopped)

### 2. Verify Build Configuration

Check in Railway Settings → Deploy:

- [ ] **Root Directory**: Should be blank or "."
- [ ] **Build Command**: `pip install -r requirements-api.txt`
- [ ] **Start Command**: `cd backend && python3 license_api_server.py`

### 3. Verify Environment Variables

Check in Railway Variables tab - Must have:

- [ ] `SNF_SECRET_SALT` = (32 character hex string)
- [ ] `SNF_ADMIN_SECRET` = (24+ character string)
- [ ] `PORT` = 5003

**Generate these if missing:**
```bash
# For SNF_SECRET_SALT
openssl rand -hex 16

# For SNF_ADMIN_SECRET  
openssl rand -base64 24
```

### 4. Check Deployment Logs

In Railway Dashboard → Deployments:

- [ ] **Build succeeded** (green checkmark)
- [ ] **Deploy succeeded** (green checkmark)
- [ ] **Logs show**: "SNF-AI License Server" and "Running on http://0.0.0.0:5003"

**Common Log Errors:**
- "Module not found" → Check requirements-api.txt exists
- "Port already in use" → Verify PORT=5003 is set
- "Permission denied" → Check file paths in start command

### 5. Test Endpoints

Once deployed, test these:

**Check Status:**
```bash
curl https://web-production-5980e.up.railway.app/api/status
```
Expected: `{"status":"healthy",...}`

**Test Registration:**
```bash
curl -X POST https://web-production-5980e.up.railway.app/api/registration/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```
Expected: `{"success":true,"license_key":"SNF-...",...}`

**Test Root:**
```bash
curl https://web-production-5980e.up.railway.app/
```
Expected: `{"service":"SNF-AI License Server",...}`

### 6. Common Issues & Fixes

#### Issue: 404 "Application not found"
**Possible Causes:**
- [ ] Service is stopped → Click "Start" in Railway
- [ ] Deployment failed → Check build logs
- [ ] Wrong URL → Verify in Railway Settings → Domains

**Fix:** In Railway, check:
1. Settings → Domains → Is your URL listed?
2. Deployments → Latest deployment status?
3. If failed, click "Redeploy"

#### Issue: Build Fails
**Check:**
- [ ] requirements-api.txt exists in repo root
- [ ] File contains: `Flask`, `flask-cors`, `requests`

**Fix:** Create requirements-api.txt if missing:
```bash
Flask>=2.3.0
flask-cors>=4.0.0
requests>=2.31.0
```

#### Issue: Server Starts but Crashes
**Check Logs for:**
- Missing environment variables → Add to Railway Variables
- Import errors → Update requirements-api.txt
- Port conflicts → Ensure PORT=5003

### 7. Next Steps After Successful Deployment

Once all checks pass:

- [ ] Save Railway URL: `https://web-production-5980e.up.railway.app`
- [ ] Save SECRET_SALT securely (needed for model encryption)
- [ ] Save ADMIN_SECRET securely (needed for license management)
- [ ] Test license validation from local code
- [ ] Proceed to Step 3: Model Encryption

---

## Quick Troubleshooting Commands

**Check if Railway is accessible:**
```bash
curl https://web-production-5980e.up.railway.app/
```

**Check logs in Railway:**
1. Go to Railway Dashboard
2. Click your project
3. Click "Deployments"
4. Click latest deployment
5. View logs

**Redeploy:**
1. Railway Dashboard → Deployments
2. Click "⋮" menu on latest deployment
3. Click "Redeploy"

---

**Current Status:** Railway URL configured, waiting for deployment verification.

**What to do now:**
1. Go to Railway dashboard: https://railway.app
2. Check deployment status
3. Verify environment variables are set
4. Check deployment logs
5. Run the test commands above
