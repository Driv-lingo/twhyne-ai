# Deploy License Server to Railway - Quick Start

## You have 2 options:

---

## Option 1: Deploy from GitHub (Recommended)

### Step 1: Push to GitHub
```bash
cd /Users/leverncurrie/Downloads/SNF_AI_Demo/clean-windsurf

# Add all new files
git add backend/license_api_server.py
git add backend/Procfile
git add backend/railway.toml
git add backend/secure_*.py
git add requirements-api.txt

# Commit
git commit -m "Add license API server for Railway"

# Push to your branch
git push origin your-branch-name
```

### Step 2: Deploy on Railway

1. Go to https://railway.app
2. Click "**New Project**"
3. Click "**Deploy from GitHub repo**"
4. Select your repository: `Driv-lingo/SNF_AI_Demo` or similar
5. Railway will ask "**Where is your code?**"
   - Set **Root Directory**: `backend`
   - Or just leave blank and it will auto-detect

### Step 3: Set Environment Variables

In Railway dashboard, click **Variables** tab:

```bash
SNF_SECRET_SALT=<paste-value-below>
SNF_ADMIN_SECRET=<paste-value-below>
PORT=5003
```

**Generate values now:**
```bash
# Run these commands:
echo "SNF_SECRET_SALT=$(openssl rand -hex 16)"
echo "SNF_ADMIN_SECRET=$(openssl rand -base64 24)"
```

### Step 4: Deploy

- Railway will automatically deploy
- Wait 2-3 minutes
- Get your URL from Railway dashboard

---

## Option 2: Use Railway CLI (Faster)

### Step 1: Install Railway CLI
```bash
# Mac
brew install railway

# Or use npm
npm install -g @railway/cli
```

### Step 2: Login
```bash
railway login
```

### Step 3: Deploy from backend directory
```bash
cd /Users/leverncurrie/Downloads/SNF_AI_Demo/clean-windsurf/backend

# Initialize Railway project
railway init

# Set environment variables
railway variables set SNF_SECRET_SALT=$(openssl rand -hex 16)
railway variables set SNF_ADMIN_SECRET=$(openssl rand -base64 24)
railway variables set PORT=5003

# Deploy
railway up
```

### Step 4: Get URL
```bash
railway domain
```

---

## After Successful Deployment

### Test it works:
```bash
# Replace with your actual Railway URL
export RAILWAY_URL="https://your-app.up.railway.app"

# Test status
curl $RAILWAY_URL/api/status

# Test registration
curl -X POST $RAILWAY_URL/api/registration/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

### Expected Response:
```json
{
  "success": true,
  "license_key": "SNF-XXXXXXXX-XXXXXXXX",
  "duration_days": 30,
  "expiry_date": "2025-11-26...",
  "message": "Registration successful. Your license is valid for 30 days."
}
```

---

## Troubleshooting

### Build fails with "requirements not found"
**Fix:** Make sure `requirements-api.txt` is in the root directory:
```bash
# From project root
cat requirements-api.txt
# Should show: Flask, flask-cors, requests
```

### Server starts but crashes
**Check Railway logs:**
1. Railway Dashboard → Your Project
2. Click "Deployments"
3. View logs

**Common issues:**
- Missing environment variables → Add them in Variables tab
- Wrong Python version → Railway uses Python 3.11 by default (should work)
- Import errors → Check requirements-api.txt

### Port already in use
**Fix:** Make sure PORT=5003 is set in Railway Variables

---

## Which option should you use?

- **Use Option 1** if your code is already on GitHub
- **Use Option 2** if you want to deploy quickly from local

**Recommended: Option 2 (Railway CLI)** - It's faster and easier to debug.

---

## Quick Railway CLI Commands

```bash
# Deploy
railway up

# View logs
railway logs

# Open in browser
railway open

# Get domain
railway domain

# Set variables
railway variables set KEY=value

# Check status
railway status
```

Ready to deploy? Pick an option and follow the steps!
