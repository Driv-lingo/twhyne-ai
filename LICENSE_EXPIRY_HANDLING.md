# License Expiry Handling

## How License Expiration Works

### 1. **During Container Runtime**
The Docker container checks the license every 24 hours:
- **7 days before expiry**: Shows warnings in logs
- **Day of expiry**: Container stops automatically
- **After expiry**: Container won't start

### 2. **Customer Experience**

#### **Normal Operation (License Valid)**
```
Customer runs START-SNF-AI.bat
→ Container starts
→ Browser opens
→ Everything works
```

#### **License Expiring Soon (7 days)**
```
Container logs show:
⚠️ License expires in 7 days
Please renew at: https://sunny-imagination-production.up.railway.app
```

#### **License Expired**
```
Customer runs START-SNF-AI.bat
→ Container starts
→ License check fails
→ Container exits
→ Script shows:

ERROR: License expired!
Please renew at: https://sunny-imagination-production.up.railway.app
```

### 3. **Renewal Process**

**Customer's Steps:**
1. Visit license website
2. Login to account
3. Purchase renewal ($20)
4. Get same license key (extended by 30 days)
5. Run START-SNF-AI.bat again
6. Works immediately (no need to re-enter key)

**What Happens Behind the Scenes:**
- License key stays the same
- Only expiry date changes in database
- Container validates with Railway server
- If valid, continues running

---

## Enhanced Scripts with Expiry Notification

We could add a pre-check to the scripts:
