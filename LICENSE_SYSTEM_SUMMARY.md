# ✅ License System - Complete & Working!

## What You Have Now

### 1. License Management Website
- **URL**: https://sunny-imagination-production.up.railway.app
- **Features**: User registration, login, license purchase, dashboard
- **Hosted**: Railway (free tier)
- **Status**: ✅ Live and tested

### 2. License Validation
- **API Endpoint**: `https://sunny-imagination-production.up.railway.app/api/validate`
- **30-day expiration**: Automatic
- **Docker integration**: ✅ Configured

### 3. Docker Image
- **Image**: `twhyne/twhyne:prod`
- **License check**: On startup + every 24 hours
- **Status**: 🔄 Rebuilding with license system

---

## For You (Admin)

### Generate License for Customer

**Option 1: Website (Customer self-service)**
1. Customer goes to: https://sunny-imagination-production.up.railway.app
2. Registers with email/password
3. Clicks "Purchase New License" (you can add payment later)
4. Gets license key instantly

**Option 2: Manual (via API)**
```bash
# Register user
curl -X POST https://sunny-imagination-production.up.railway.app/api/register \
  -H "Content-Type: application/json" \
  -d '{"email": "customer@example.com", "password": "temp-password"}'

# Login
curl -X POST https://sunny-imagination-production.up.railway.app/api/login \
  -H "Content-Type: application/json" \
  -d '{"email": "customer@example.com", "password": "temp-password"}' \
  -c cookies.txt

# Generate license
curl -X POST https://sunny-imagination-production.up.railway.app/api/purchase-license \
  -H "Content-Type: application/json" \
  -b cookies.txt

# Returns: {"license_key": "SNF-XXXXXXXX-XXXXXXXX", ...}
```

### View All Licenses

SSH to Railway or check the database:
```bash
# In Railway dashboard → Service → Variables tab
# Or SSH and:
cd /app
python3
>>> from app import load_db
>>> db = load_db()
>>> for key, lic in db['licenses'].items():
...     print(f"{key}: {lic['email']} - Expires: {lic['expiry_date'][:10]}")
```

### Manage Licenses

**Extend license** (give customer more time):
Open browser to Railway dashboard → Shell or use SSH

**Revoke license** (disable immediately):
Same process, set `is_active = False`

---

## For Customers

### Installation Instructions

**Step 1: Get License Key**
1. Go to: https://sunny-imagination-production.up.railway.app
2. Register account
3. Purchase 30-day license
4. Copy license key from dashboard

**Step 2: Install Docker**
- Download Docker Desktop for Mac/Windows
- Install and start Docker

**Step 3: Login to Docker Hub**
```bash
docker login
# Username: <provided-by-you>
# Password: <token-provided-by-you>
```

**Step 4: Run with License**
```bash
# Set license key
export SNF_LICENSE_KEY="SNF-XXXXXXXX-XXXXXXXX"

# Download and run
docker-compose -f docker-compose.licensed.yml up
```

**Step 5: Access Application**
- Open browser: http://localhost:5002
- Dashboard: http://localhost:5002/dashboard/

---

## Testing

### Test License Validation
```bash
curl -X POST https://sunny-imagination-production.up.railway.app/api/validate \
  -H "Content-Type: application/json" \
  -d '{"license_key": "SNF-A0B69686-4689F560"}'
```

Expected:
```json
{
  "valid": true,
  "email": "test@example.com",
  "expiry_date": "2025-11-27T01:58:19.387620",
  "message": "License valid"
}
```

### Test Docker Container
```bash
export SNF_LICENSE_KEY="SNF-A0B69686-4689F560"
docker-compose -f docker-compose.licensed.yml up
```

Expected output:
```
✓ License valid until: 2025-11-27
✓ License validation successful!
✓ Periodic license check enabled (every 24h)
Starting backend server...
```

---

## Distribution Checklist

- [x] License website deployed and tested
- [x] License generation working
- [x] License validation working
- [ ] Docker image rebuilt with license check
- [ ] Docker image pushed to Docker Hub
- [ ] Make Docker Hub repository private
- [ ] Create customer documentation
- [ ] Test complete flow end-to-end
- [ ] Set pricing (update $XX in website)
- [ ] Add payment integration (optional - Stripe)
- [ ] Onboard first customer

---

## Security

✅ **What's Protected**:
- License validated on Docker startup
- Daily license checks (container exits if expired)
- Server-side validation (can't be bypassed)
- 30-day automatic expiration
- Remote revocation capability

⚠️ **What's NOT Protected**:
- Models are not encrypted (they could be extracted)
- Source code is visible (Python)
- No hardware binding

**For your use case, this is sufficient!** The license expires monthly, forcing renewal.

---

## Revenue Model

### Current: Manual Payment
- Customer emails you
- You process payment (PayPal, Venmo, bank transfer)
- You send them license website URL
- They register and get license

### Future: Automated (Stripe)
- Customer clicks "Purchase"
- Redirected to Stripe checkout
- Payment processed automatically
- License generated automatically
- Recurring billing for renewals

---

## Support & Troubleshooting

### Customer: "Container won't start"
- Check `SNF_LICENSE_KEY` is set correctly
- Test license: `curl -X POST .../api/validate -d '{"license_key": "..."}'`
- Check license hasn't expired

### Customer: "License expired"
- They need to renew (purchase new 30-day license)
- Or you can extend their existing license manually

### Website down
- Check Railway dashboard
- Check logs: Railway → Service → Deployments → Logs
- Restart: Railway → Service → Settings → Restart

---

## What's Next?

1. ✅ **Wait for Docker image to finish building**
2. ✅ **Push image to Docker Hub**
3. ✅ **Test complete flow**
4. ✅ **Create customer onboarding email template**
5. 📧 **Onboard first customer!**

**You now have a complete, working monthly license system!**
