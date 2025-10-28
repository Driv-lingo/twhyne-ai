# License Management Website

Simple website for users to register, purchase, and manage SNF-AI licenses.

## Features

- User registration & login
- Purchase 30-day licenses
- View active licenses
- Copy license keys
- Simple JSON database (upgrade to SQL for production)

## Quick Start

### Run Locally

```bash
cd license-website
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

### Deploy to Any Host

**Works on:**
- Heroku
- Railway (easier than before - it's just a Flask app)
- Vercel
- DigitalOcean App Platform
- Any VPS (DigitalOcean, Linode, etc.)

#### Deploy to Railway (Simple)

1. Create new Railway project
2. **Don't use GitHub** - use Railway CLI instead:

```bash
cd license-website
railway init
railway up
```

3. Set environment variable:
```bash
railway variables set SECRET_KEY=$(openssl rand -hex 32)
```

4. Get URL:
```bash
railway domain
```

Done!

#### Deploy to Heroku

```bash
cd license-website
heroku create snf-ai-licenses
git init
git add .
git commit -m "Initial commit"
git push heroku master
```

#### Deploy to VPS (Ubuntu/Debian)

```bash
# On your server
sudo apt update
sudo apt install python3 python3-pip nginx

# Clone your code
cd /var/www
git clone <your-repo>
cd license-website

# Install dependencies
pip3 install -r requirements.txt

# Run with gunicorn
pip3 install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Update Docker Containers to Use This Website

Edit `backend/simple_license_check.py`:

```python
LICENSE_API = "https://your-website.com"  # Your deployed URL
```

## Database

Currently uses `license_db.json` (simple file storage).

For production:
- Switch to PostgreSQL or MySQL
- Update `load_db()` and `save_db()` functions
- Add proper database migrations

## Payment Integration

To add real payments (Stripe):

1. Install Stripe:
```bash
pip install stripe
```

2. Update `/api/purchase-license`:
```python
import stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

@app.route('/api/purchase-license', methods=['POST'])
def api_purchase_license():
    # Create Stripe checkout session
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {'name': 'SNF-AI License (30 days)'},
                'unit_amount': 2999,  # $29.99
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=request.host_url + 'dashboard?payment=success',
        cancel_url=request.host_url + 'dashboard?payment=cancel',
    )
    return jsonify({'checkout_url': session.url})
```

## Security Improvements for Production

1. **Use real database** (not JSON file)
2. **Add email verification**
3. **Add password reset**
4. **Use HTTPS** (Let's Encrypt)
5. **Add rate limiting**
6. **Add CAPTCHA** on registration
7. **Hash sessions properly**
8. **Add audit logs**

## Testing

```bash
# Start server
python app.py

# Register user
curl -X POST http://localhost:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "password123"}'

# Login
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "password123"}'

# Purchase license (requires login session)
curl -X POST http://localhost:5000/api/purchase-license \
  -H "Content-Type: application/json" \
  --cookie "session=..."

# Validate license (Docker containers use this)
curl -X POST http://localhost:5000/api/validate \
  -H "Content-Type: application/json" \
  -d '{"license_key": "SNF-..."}'
```

## Customization

Edit `templates/index.html` to update:
- Pricing ($XX/month)
- Features list
- Company info
- Branding

## Support

For issues or questions about the license system, contact your support team.
