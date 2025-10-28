# Changelog

All notable changes to SNF-AI Windsurf will be documented in this file.

## [1.0.0] - 2024-10-28
### Added
- License enforcement system with Railway backend
- 30-day license validation
- Offline expiry protection (7-day grace period)
- Stripe payment integration ($20/month)
- Docker distribution with license check
- Customer installation scripts

### Security
- License validation required on container startup
- Daily license verification (24-hour intervals)
- Cached license expiry for offline enforcement

## [0.9.0] - 2024-10-27
### Added
- Initial Docker containerization
- Multi-node AI system
- Frontend and backend integration

---

## Version History

| Version | Date | License Required | Notes |
|---------|------|------------------|-------|
| 1.0.0 | 2024-10-28 | ✅ Yes | First licensed release |
| 0.9.0 | 2024-10-27 | ❌ No | Beta version |
