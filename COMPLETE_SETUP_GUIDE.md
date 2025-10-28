# Complete License System Setup Guide

## Overview

Simple 30-day license system with:
- User registration website
- License purchase & management
- Docker container validation
- Monthly renewal cycle

**No complex encryption. No Railway headaches. Just works.**

---

## Step 1: Deploy License Website (5 minutes)

### Option A: Railway CLI (Easiest)

```bash
cd license-website

# Install Railway CLI
brew install railway

# Login
railway login

# Deploy
railway init
railway up

# Set secret key
railway variables set SECRET_KEY=$(openssl rand -hex 32)

# Get your URL
railway domain
```

Save the URL - you'll need it!

### Option B: Any VPS

```bash
# SSH to your server
ssh user@your-server.com

# Install dependencies
sudo apt update
sudo apt install python3 python3-pip

# Upload the license-website folder
# Then:
cd license-website
pip3 install -r requirements.txt
pip3 install gunicorn

# Run
gunicorn -w 4 -b 0.0.0.0:5000 app:app &
```

---

## Step 2: Update Docker Image

### Build with License Check

```bash
# Your license website URL from Step 1
export LICENSE_API_URL="https://your-website.com"

# Build Docker image
docker build -t twhyne/twhyne:prod .

# Test locally first
docker run -e SNF_LICENSE_KEY=test -e LICENSE_API_URL=$LICENSE_API_URL twhyne/twhyne:prod

# Push to Docker Hub
docker login
docker push twhyne/twhyne:prod
```

### Make Docker Hub Repository Private

1. Go to https://hub.docker.com
2. Find `twhyne/twhyne` repository
3. Settings → Make Private
4. Create access tokens for customers

---

## Step 3: Test Complete Flow

### Generate Test License

```bash
# Open your license website
open https://your-website.com

# Or use curl:
curl -X POST https://your-website.com/api/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "test123"}'

curl -X POST https://your-website.com/api/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "test123"}'

# Purchase license (copy the license key from response)
curl -X POST https://your-website.com/api/purchase-license \
  -H "Content-Type: application/json"
```

### Test Docker Container

```bash
# Use the license key from above
export SNF_LICENSE_KEY="SNF-XXXXXXXX-XXXXXXXX"
export LICENSE_API_URL="https://your-website.com"

# Run container
docker-compose -f docker-compose.licensed.yml up
```

**Expected output:**
```
✓ License valid until: 2025-11-26
✓ License validation successful!
✓ Periodic license check enabled (every 24h)
```

---

## Step 4: Customer Onboarding

### What to Give Each Customer

1. **License Website URL**
   - `https://your-website.com`
   - They register and purchase

2. **Docker Hub Credentials**
   - Create access token in Docker Hub
   - Send token to customer

3. **Installation Instructions** (see template below)

4. **docker-compose.licensed.yml** file

### Customer Installation Template

```markdown
# SNF-AI Windsurf Installation

## Step 1: Get Your License

1. Go to: https://your-website.com
2. Register for an account
3. Purchase a 30-day license ($XX)
4. Copy your license key from the dashboard

## Step 2: Install Docker

Download Docker Desktop:
- Mac: https://www.docker.com/products/docker-desktop
- Windows: https://www.docker.com/products/docker-desktop

## Step 3: Login to Docker Hub

```bash
docker login -u <username> -p <token-we-provided>
```

## Step 4: Set Your License Key

```bash
# Mac/Linux
export SNF_LICENSE_KEY="your-key-from-website"

# Windows PowerShell
$env:SNF_LICENSE_KEY="your-key-from-website"
```

## Step 5: Run

```bash
docker-compose -f docker-compose.licensed.yml up
```

## Step 6: Access Application

Open browser to: http://localhost:5002

## Support

Email: support@twhyne.com
```

---

## Managing Licenses

### Extend License (from website backend)

```bash
# SSH to your license website server
cd license-website

# Python console
python3
>>> from app import load_db, save_db
>>> from datetime import datetime, timedelta
>>> db = load_db()
>>> license_key = "SNF-XXXXXXXX-XXXXXXXX"
>>> db['licenses'][license_key]['expiry_date'] = (datetime.now() + timedelta(days=60)).isoformat()
>>> save_db(db)
```

### Revoke License

```bash
>>> db['licenses'][license_key]['is_active'] = False
>>> save_db(db)
```

### View All Licenses

```bash
>>> for key, lic in db['licenses'].items():
...     print(f"{key}: {lic['email']} - Expires: {lic['expiry_date'][:10]}")
```

---

## Pricing & Billing

### Manual Payment

Current setup: Manual license generation
- Customer emails you
- You process payment (PayPal, bank transfer, etc.)
- You generate license via website

### Automated Payment (Stripe)

Add to `license-website/app.py`:

```python
import stripe
stripe.api_key = 'sk_live_...'

# Update purchase endpoint to create Stripe checkout
# See license-website/README.md for full code
```

---

## Monitoring

### Check License Usage

```bash
cd license-website
python3 -c "
from app import load_db
db = load_db()
print(f'Total users: {len(db[\"users\"])}')
print(f'Total licenses: {len(db[\"licenses\"])}')
active = sum(1 for l in db['licenses'].values() if l['is_active'])
print(f'Active licenses: {active}')
"
```

### Check Docker Container Logs

```bash
# Customer side
docker logs snf-ai-windsurf

# Should show:
# ✓ License valid until: ...
# ✓ Periodic license check enabled
```

---

## Troubleshooting

### "License validation failed"

**Customer side:**
- Check `SNF_LICENSE_KEY` is set correctly
- Check license hasn't expired (30 days)
- Test license: `curl -X POST https://your-website.com/api/validate -H "Content-Type: application/json" -d '{"license_key": "SNF-..."}'`

**Your side:**
- Check license website is running
- Check database has the license
- Check license `is_active` = true

### "Cannot connect to license server"

- License website is down → restart it
- Firewall blocking → open port 5000 (or 80/443)
- URL wrong in Docker image → rebuild image with correct `LICENSE_API_URL`

### Container exits after 24 hours

- License expired → extend or renew
- License server unreachable → check website status

---

## Security Checklist

- [  ] License website uses HTTPS
- [ ] Docker Hub repository is private
- [ ] Customer access tokens (not passwords) for Docker Hub
- [ ] License database backed up regularly
- [ ] SECRET_KEY environment variable set
- [ ] Rate limiting enabled (optional)
- [ ] Email verification added (optional)

---

## Revenue Tracking

### Simple Spreadsheet

Track manually:
- Customer email
- License key
- Purchase date
- Expiry date
- Payment received
- Renewal status

### Automated (Stripe + Database)

When you integrate Stripe:
- Automatic recurring billing
- Customer portal for subscription management
- Webhook for auto-renewals
- Revenue dashboard

---

## Next Steps

1. ✅ Deploy license website
2. ✅ Update Docker image
3. ✅ Test complete flow
4. ✅ Create customer documentation
5. ✅ Onboard first customer
6. 📈 Set up payment processing (Stripe recommended)
7. 📧 Add email notifications (license expiring, renewal reminders)
8. 📊 Add analytics dashboard

---

**You now have a complete, working 30-day license system!**

Simple, maintainable, and effective.
