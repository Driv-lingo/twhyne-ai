# Customer Onboarding Email Templates

## Template 1: Welcome & License Key

```
Subject: Welcome to SNF-AI Windsurf - Your License Key

Hi [Customer Name],

Welcome to SNF-AI Windsurf! 🚀

Your 30-day license is ready. Here's everything you need to get started:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 YOUR LICENSE INFORMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

License Portal: https://sunny-imagination-production.up.railway.app
Your Email: [customer@email.com]
Temporary Password: [generate-random-password]

Please log in and change your password immediately.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 QUICK START GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1: Get Your License Key
1. Visit: https://sunny-imagination-production.up.railway.app
2. Log in with the credentials above
3. Click "Purchase New License" (already paid)
4. Copy your license key from the dashboard

STEP 2: Install Docker
Download Docker Desktop:
• Mac: https://www.docker.com/products/docker-desktop
• Windows: https://www.docker.com/products/docker-desktop

STEP 3: Access Docker Image
Username: [docker-username]
Token: [docker-token]

Run this command:
docker login -u [docker-username] -p [docker-token]

STEP 4: Run SNF-AI Windsurf

Mac/Linux:
export SNF_LICENSE_KEY="your-key-from-dashboard"
docker-compose -f docker-compose.licensed.yml up

Windows PowerShell:
$env:SNF_LICENSE_KEY="your-key-from-dashboard"
docker-compose -f docker-compose.licensed.yml up

STEP 5: Access Your Application
Open your browser to: http://localhost:5002

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📖 IMPORTANT INFORMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• License Duration: 30 days
• Expiry Date: [calculated-date]
• Renewal: Automatic reminder 3 days before expiry
• Support: support@twhyne.com

Your license is validated when the container starts and checked daily.
If your license expires, the container will stop automatically.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 DOCUMENTATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Full documentation: [your-docs-url]
Video tutorial: [your-video-url]
FAQ: [your-faq-url]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Need help? Reply to this email or contact support@twhyne.com

Best regards,
The SNF-AI Windsurf Team
```

---

## Template 2: License Expiring Soon

```
Subject: Your SNF-AI Windsurf License Expires in 3 Days

Hi [Customer Name],

Your SNF-AI Windsurf license will expire in 3 days.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ LICENSE EXPIRATION NOTICE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Current License: SNF-XXXXXXXX-XXXXXXXX
Expires: [date]

Your Docker container will stop working when the license expires.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 RENEW YOUR LICENSE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Visit: https://sunny-imagination-production.up.railway.app
2. Log in
3. Click "Purchase New License"
4. Update your docker-compose with the new license key

Or reply to this email and we'll process your renewal manually.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Questions? Contact support@twhyne.com

Best regards,
The SNF-AI Windsurf Team
```

---

## Template 3: License Expired

```
Subject: Your SNF-AI Windsurf License Has Expired

Hi [Customer Name],

Your SNF-AI Windsurf license has expired.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ LICENSE EXPIRED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your license: SNF-XXXXXXXX-XXXXXXXX
Expired on: [date]

Your Docker container will no longer start.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 RENEW NOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Visit: https://sunny-imagination-production.up.railway.app
2. Log in
3. Purchase a new 30-day license
4. Update your docker-compose with the new license key
5. Restart your container

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Need assistance? Reply to this email or contact support@twhyne.com

Best regards,
The SNF-AI Windsurf Team
```

---

## Template 4: Docker Hub Credentials

```
Subject: SNF-AI Windsurf - Docker Access Credentials

Hi [Customer Name],

Here are your Docker Hub credentials to access the SNF-AI Windsurf image:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🐳 DOCKER HUB ACCESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Username: [docker-username]
Access Token: [docker-access-token]

⚠️ IMPORTANT: Keep these credentials secure. Do not share them.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 LOGIN TO DOCKER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Open terminal and run:
docker login -u [docker-username] -p [docker-access-token]

You should see: "Login Succeeded"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📥 DOWNLOAD IMAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

docker pull twhyne/twhyne:prod

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Next steps: Check your separate email for license key and setup instructions.

Best regards,
The SNF-AI Windsurf Team
```

---

## Template 5: Payment Receipt

```
Subject: Payment Received - SNF-AI Windsurf License

Hi [Customer Name],

Thank you for your payment!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💳 PAYMENT CONFIRMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Date: [date]
Amount: $XX.00
Description: SNF-AI Windsurf 30-Day License
Payment Method: [method]
Receipt #: [receipt-number]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 WHAT'S NEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your license is being provisioned and you'll receive:

1. Docker Hub credentials (within 5 minutes)
2. License portal access (within 5 minutes)
3. Setup instructions (within 5 minutes)

Look for emails with the subject: "SNF-AI Windsurf - Your License Key"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Questions? Contact support@twhyne.com

Best regards,
The SNF-AI Windsurf Team
```

---

## Automation Ideas

### Send expiration reminders automatically:

1. **Cron job** on your server:
```python
# check_expiring_licenses.py
from datetime import datetime, timedelta
from app import load_db
import smtplib

db = load_db()
three_days = datetime.now() + timedelta(days=3)

for key, lic in db['licenses'].items():
    expiry = datetime.fromisoformat(lic['expiry_date'])
    if expiry <= three_days and lic['is_active']:
        send_expiration_email(lic['email'], key, expiry)
```

2. **Run daily**:
```bash
# Add to crontab
0 9 * * * cd /path/to/license-website && python3 check_expiring_licenses.py
```

### With Stripe:
- Automatic recurring billing
- Customer portal for subscription management
- Webhook notifications for renewals/cancellations
