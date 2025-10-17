# Twhyne AI - Deployment Guide

## Branch Strategy

This repository uses a three-branch deployment pipeline:

```
testing → pre-prod → prod
```

### Branch Descriptions

#### 🧪 **testing** (Development Branch)
- **Purpose**: Active development and feature testing
- **CI/CD**: Runs tests on every push
- **Deployment**: Not deployed, local testing only
- **Merge Target**: pre-prod

**Use for:**
- New feature development
- Bug fixes
- Experimental changes
- Integration testing

#### 🔍 **pre-prod** (Pre-Production/Staging)
- **Purpose**: Final validation before production
- **CI/CD**: Full test suite + security scans + build artifacts
- **Deployment**: Staging environment (if configured)
- **Merge Target**: prod

**Use for:**
- User acceptance testing (UAT)
- Performance testing
- Final integration validation
- Release candidate builds

#### 🚀 **prod** (Production/Main)
- **Purpose**: Stable production code
- **CI/CD**: Full test suite + production deployment + release artifacts
- **Deployment**: Production environment
- **Protected**: Requires pull request reviews

**Use for:**
- Production releases
- Hotfix deployments
- Stable releases only

---

## Workflow

### 1. Development Flow
```bash
# Work on testing branch
git checkout testing
git pull origin testing

# Make changes
git add .
git commit -m "feat: add new feature"
git push origin testing
```

### 2. Promote to Pre-Production
```bash
# Create PR from testing → pre-prod
# After review and approval:
git checkout pre-prod
git merge testing
git push origin pre-prod
```

### 3. Deploy to Production
```bash
# Create PR from pre-prod → prod
# After final review and approval:
git checkout prod
git merge pre-prod
git push origin prod

# Optional: Tag release
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

---

## CI/CD Pipeline

### Testing Branch
- ✅ Backend syntax check
- ✅ Frontend linting
- ✅ Build verification
- ✅ Unit tests
- ✅ Integration tests

### Pre-Prod Branch
- ✅ All testing branch checks
- ✅ Security scanning (Python & npm)
- ✅ Build artifacts creation
- ✅ Deployment package generation

### Prod Branch
- ✅ All pre-prod checks
- ✅ Production build
- ✅ Release artifact creation
- ✅ GitHub release (on tags)
- ✅ Deployment notifications

---

## GitHub Actions Workflows

### `.github/workflows/testing.yml`
Runs on every push to `testing` branch:
- Backend tests
- Frontend tests
- Integration tests

### `.github/workflows/pre-prod.yml`
Runs on every push to `pre-prod` branch:
- Full test suite
- Security scans
- Artifact creation

### `.github/workflows/prod.yml`
Runs on every push to `prod` branch:
- Production deployment
- Release creation
- Artifact archival

---

## Setup Instructions

### 1. Create GitHub Repository
```bash
# Initialize git (if not already done)
cd /Users/leverncurrie/Downloads/SNF_AI_Demo/clean-windsurf
git init

# Add all files
git add .
git commit -m "Initial commit: Twhyne AI multi-modal system"

# Create repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/twhyne-ai.git
git branch -M prod  # Rename main branch to prod
git push -u origin prod
```

### 2. Create Additional Branches
```bash
# Create pre-prod branch
git checkout -b pre-prod
git push -u origin pre-prod

# Create testing branch
git checkout -b testing
git push -u origin testing
```

### 3. Configure Branch Protection (on GitHub)

#### For `prod` branch:
- ✅ Require pull request reviews (1+ reviewers)
- ✅ Require status checks to pass
- ✅ Require branches to be up to date
- ✅ Do not allow force pushes
- ✅ Do not allow deletions

#### For `pre-prod` branch:
- ✅ Require status checks to pass
- ✅ Require branches to be up to date

### 4. Set Default Branch
- Go to Settings → Branches
- Set default branch to `testing`
- This ensures new work starts on the development branch

---

## Environment Variables

For production deployment, configure these secrets in GitHub:
- `GITHUB_TOKEN` (automatically provided)
- Add any API keys or credentials as repository secrets

---

## Model Files

⚠️ **Important**: Model files (`.gguf`) are large and should not be committed to Git.

### Recommended Approach:
1. Store models in Git LFS or external storage
2. Download during deployment:
   ```bash
   # Add to deployment script
   wget https://huggingface.co/MODEL_PATH/resolve/main/model.gguf -P models/
   ```

---

## Deployment Checklist

Before merging to production:

- [ ] All tests passing in pre-prod
- [ ] Security scans completed
- [ ] Performance testing done
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version number bumped
- [ ] Stakeholders notified

---

## Rollback Procedure

If issues occur in production:

```bash
# Revert to previous commit
git checkout prod
git revert HEAD
git push origin prod

# Or rollback to specific tag
git checkout prod
git reset --hard v1.0.0
git push origin prod --force  # Use with caution!
```

---

## Support

For issues or questions:
- Create an issue in GitHub
- Check CI/CD logs in Actions tab
- Review deployment artifacts

---

**Last Updated**: October 17, 2025
