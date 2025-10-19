# SNF-AI Windsurf - License-Only Version

## ⚠️ NO TRIAL MODE - LICENSE REQUIRED

This is the production version of SNF-AI Windsurf that **requires a valid license** to operate.

## Key Changes from Previous Versions

### ❌ Removed
- **No 7-day trial option**
- **No limited free access**
- **No trial mode UI elements**

### ✅ Enforced
- **License validation required on every launch**
- **Valid 90-day license key mandatory**
- **Purchase required before use**

## License System

### Purchase Process
1. User visits: https://web-production-d31c0.up.railway.app/register
2. Completes registration and payment
3. Receives 90-day license key via email
4. Enters key in application to activate

### License Features
- **Duration**: 90 days from activation
- **Devices**: Up to 3 devices per license
- **Renewal**: Required after expiry
- **Validation**: Online (with offline fallback)

### What Happens Without License?

When launching without a valid license:
1. License activation dialog appears
2. User must either:
   - Enter valid license key
   - Click "Get License" to purchase
3. **No access without valid license**

## Application Features (With Valid License)

### Full Mode (with models)
- ✅ Language Processing
- ✅ Code Generation
- ✅ Mathematical Calculations
- ✅ Image Processing
- ✅ Real-time Information
- ✅ Task Planning

### Limited Mode (without models, but licensed)
- ✅ Mathematical Calculations
- ✅ Image Processing
- ✅ Real-time Information
- ❌ Language Processing (needs models)
- ❌ Code Generation (needs models)

## Build Instructions

```bash
# Build the license-only version
chmod +x BUILD_FINAL.sh
./BUILD_FINAL.sh
```

## Distribution

The final package includes:
- `SNF-AI-Windsurf.app` - Main application
- `Install.command` - Installer script
- `Uninstall.command` - Uninstaller
- `USER_GUIDE.md` - Documentation

## Revenue Model

- **No Free Tier**: Every user must purchase
- **90-Day License**: $XX.XX (set your price)
- **Renewal Reminders**: Sent before expiry
- **Multi-Device**: Premium feature (3 devices)

## API Integration

The app connects to your Railway API:
- **Base URL**: https://web-production-d31c0.up.railway.app
- **Endpoints**:
  - `/api/registration/register` - New licenses
  - `/api/registration/validate` - License validation
  - `/api/registration/renew` - License renewal

## Security

- Device ID binding prevents sharing
- License keys are validated server-side
- Offline mode uses cached validation
- Expiry dates are enforced

## Summary

This is a **commercial-only** version with:
- ❌ No trial period
- ❌ No free access
- ✅ License purchase required
- ✅ Full feature access with valid license
- ✅ Professional deployment ready

---

**Version 3.0.0 - License Required Edition**
© 2025 Twhyne AI. All rights reserved.
