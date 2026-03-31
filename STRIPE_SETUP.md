# Stripe Integration Setup - $20/month License

## Quick Setup (5 minutes)

### Step 1: Create Stripe Account
1. Go to https://stripe.com
2. Sign up for free account
3. Activate your account

### Step 2: Create Product & Price

**In Stripe Dashboard:**

1. **Products** → **Add Product**
   - Name: `SNF-AI Windsurf 30-Day License`
   - Description: `30-day access to SNF-AI Windsurf on-premise platform`
   - Image: (optional - upload logo)

2. **Pricing**
   - Pricing model: `One time`
   - Price: `$20.00 USD`
   - Click **Save product**

3. **Copy Price ID**
   - You'll see something like: `price_1ABC123XYZ`
   - Copy this - you'll need it

### Step 3: Get API Keys

**In Stripe Dashboard:**

1. **Developers** → **API Keys**
2. Copy:
   - **Secret key** (starts with `sk_test_...` for test mode)
   - **Publishable key** (starts with `pk_test_...`)

### Step 4: Set Up Webhook

**In Stripe Dashboard:**

1. **Developers** → **Webhooks** → **Add endpoint**
2. **Endpoint URL**: `https://sunny-imagination-production.up.railway.app/api/stripe-webhook`
3. **Events to send**:
   - Select: `checkout.session.completed`
4. Click **Add endpoint**
5. Copy **Signing secret** (starts with `whsec_...`)

### Step 5: Configure Railway Environment Variables

```bash
cd license-website
railway link  # Link to your project

# Set Stripe variables
railway variables --set "STRIPE_SECRET_KEY=sk_test_YOUR_KEY_HERE"
railway variables --set "STRIPE_PRICE_ID=price_YOUR_PRICE_ID_HERE"
railway variables --set "STRIPE_WEBHOOK_SECRET=whsec_YOUR_WEBHOOK_SECRET_HERE"
```

### Step 6: Deploy Updated Code

```bash
# Make sure you're in license-website directory
railway up
```

---

## Testing in Test Mode

### 1. Make a Test Purchase

1. Visit: https://sunny-imagination-production.up.railway.app
2. Register account
3. Click "Purchase New License ($20/month)"
4. Use Stripe test card:
   - Card: `4242 4242 4242 4242`
   - Expiry: Any future date (e.g., `12/34`)
   - CVC: Any 3 digits (e.g., `123`)
   - ZIP: Any 5 digits (e.g., `12345`)

### 2. Verify License Generated

1. After payment, you'll be redirected to dashboard
2. Check if license key appears
3. Test validation:
```bash
curl -X POST https://sunny-imagination-production.up.railway.app/api/validate \
  -H "Content-Type: application/json" \
  -d '{"license_key": "SNF-XXXXXXXX-XXXXXXXX"}'
```

### 3. Check Webhook Logs

**In Railway:**
- Dashboard → Service → Deployments → Logs
- Look for: `License generated for [email]: SNF-XXXXXXXX-XXXXXXXX`

**In Stripe:**
- Developers → Webhooks → Your endpoint
- Click to see recent events

---

## Going Live (Production Mode)

### 1. Activate Stripe Account
- Complete business verification
- Add bank account for payouts

### 2. Switch to Live Keys

**In Stripe Dashboard:**
- Toggle from "Test mode" to "Live mode" (top right)
- Get new API keys
- Create new webhook with live mode URL

**Update Railway:**
```bash
railway variables --set "STRIPE_SECRET_KEY=sk_live_YOUR_LIVE_KEY"
railway variables --set "STRIPE_PRICE_ID=price_YOUR_LIVE_PRICE_ID"
railway variables --set "STRIPE_WEBHOOK_SECRET=whsec_YOUR_LIVE_WEBHOOK_SECRET"
```

### 3. Test Real Payment
- Use real credit card (will charge $20)
- Verify license generated
- Refund test transaction in Stripe dashboard

---

## How It Works

### Customer Flow:
1. Customer registers on website
2. Clicks "Purchase New License"
3. Redirected to Stripe Checkout (secure payment page)
4. Enters credit card info
5. Stripe processes payment
6. Webhook sends notification to your server
7. Server generates license key automatically
8. Customer redirected back to dashboard with license key

### Without Stripe (Test Mode):
- If Stripe not configured, falls back to manual license generation
- Useful for testing or manual sales

---

## Pricing Options

### Current: One-Time $20 Payment (30 days)
```python
mode='payment'
line_items=[{'price': STRIPE_PRICE_ID, 'quantity': 1}]
```

### Option 2: Monthly Recurring Subscription
Change product to subscription:
```python
mode='subscription'
line_items=[{'price': STRIPE_PRICE_ID, 'quantity': 1}]
```

Then handle `customer.subscription.deleted` webhook to revoke licenses.

### Option 3: Different Pricing Tiers
Create multiple products:
- Basic: $15/month (30 days)
- Pro: $20/month (30 days + priority support)
- Enterprise: $50/month (60 days + dedicated support)

---

## Revenue Tracking

### In Stripe Dashboard:
- **Home** → See total revenue
- **Payments** → See all transactions
- **Customers** → See customer list
- **Reports** → Export data

### Automate Reporting:
Use Stripe API to pull data:
```python
import stripe
stripe.api_key = 'sk_test_...'

# Get all charges
charges = stripe.Charge.list(limit=100)
for charge in charges:
    print(f"{charge.customer_email}: ${charge.amount/100}")
```

---

## Email Notifications (Future Enhancement)

### Send License via Email:

1. **Add email library:**
```bash
pip install sendgrid
```

2. **Update webhook in app.py:**
```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

@app.route('/api/stripe-webhook', methods=['POST'])
def stripe_webhook():
    # ... after license generation ...
    
    message = Mail(
        from_email='licenses@yourdomain.com',
        to_emails=email,
        subject='Your SNF-AI License Key',
        html_content=f'''
        <h1>Welcome to SNF-AI Windsurf!</h1>
        <p>Your license key: <strong>{license_key}</strong></p>
        <p>Expires: {expiry_date}</p>
        '''
    )
    
    sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
    sg.send(message)
```

---

## Security Best Practices

### ✅ Do:
- Use environment variables for keys (never commit to Git)
- Verify webhook signatures
- Use HTTPS only
- Keep Stripe library updated

### ❌ Don't:
- Hardcode API keys in code
- Expose secret keys in frontend
- Skip webhook signature verification
- Store credit card data yourself (Stripe handles this)

---

## Troubleshooting

### "Webhook signature verification failed"
- Check `STRIPE_WEBHOOK_SECRET` is correct
- Make sure it's the webhook secret, not API key
- Test with Stripe CLI: `stripe listen --forward-to localhost:5000/api/stripe-webhook`

### "No license generated after payment"
- Check Railway logs for errors
- Verify webhook endpoint is publicly accessible
- Test webhook manually in Stripe dashboard

### "Payment successful but redirected to wrong URL"
- Check `success_url` in checkout session
- Make sure `request.host_url` is correct

---

## Costs

### Stripe Fees:
- **Online payments**: 2.9% + $0.30 per transaction
- **For $20 payment**: $0.88 fee = **$19.12 net**

### Railway Hosting:
- **Free tier**: $5 free credit/month
- **After free tier**: ~$5-10/month for small app

### Total Cost to You:
- Per $20 sale: $0.88 to Stripe
- Hosting: Free (or ~$5/month)
- **Net revenue per license**: ~$19.12

---

## Summary

✅ **Added:**
- Stripe integration in `app.py`
- $20/month pricing on website
- Automatic license generation after payment
- Webhook to receive payment notifications
- Test mode fallback

✅ **Setup Required:**
1. Create Stripe account (5 min)
2. Create product ($20 price) (2 min)
3. Get API keys (1 min)
4. Set up webhook (2 min)
5. Configure Railway variables (2 min)
6. Deploy (1 min)

**Total setup time: ~15 minutes**

**Ready to accept payments!** 🚀
