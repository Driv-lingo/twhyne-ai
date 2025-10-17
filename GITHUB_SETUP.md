# GitHub Repository Setup Instructions

## Step 1: Create Repository on GitHub

1. Go to https://github.com/new
2. Fill in the details:
   - **Repository name**: `twhyne-ai` (or your preferred name)
   - **Description**: "Intelligent Multi-Modal AI System with RAG, Vision, and Expert Node Routing"
   - **Visibility**: Choose Public or Private
   - **DO NOT** initialize with README, .gitignore, or license (we already have these)
3. Click "Create repository"

## Step 2: Initialize Local Repository and Push

Run these commands in your terminal:

```bash
# Navigate to project directory
cd /Users/leverncurrie/Downloads/SNF_AI_Demo/clean-windsurf

# Initialize git repository
git init

# Configure git (use your GitHub email)
git config user.name "Your Name"
git config user.email "your-github-email@example.com"

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Twhyne AI multi-modal system with RAG, vision, and CI/CD pipeline"

# Rename default branch to 'prod'
git branch -M prod

# Add your GitHub repository as remote (REPLACE WITH YOUR REPO URL)
git remote add origin https://github.com/YOUR_USERNAME/twhyne-ai.git

# Push prod branch
git push -u origin prod

# Create and push pre-prod branch
git checkout -b pre-prod
git push -u origin pre-prod

# Create and push testing branch
git checkout -b testing
git push -u origin testing

# Verify all branches are created
git branch -a
```

## Step 3: Configure Branch Protection on GitHub

### For `prod` branch:
1. Go to your repository on GitHub
2. Click **Settings** → **Branches**
3. Click **Add rule** under "Branch protection rules"
4. Branch name pattern: `prod`
5. Enable:
   - ✅ Require a pull request before merging
   - ✅ Require approvals (at least 1)
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
   - ✅ Do not allow bypassing the above settings
   - ✅ Restrict who can push to matching branches
6. Click **Create**

### For `pre-prod` branch:
1. Click **Add rule** again
2. Branch name pattern: `pre-prod`
3. Enable:
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
4. Click **Create**

## Step 4: Set Default Branch

1. Go to **Settings** → **Branches**
2. Under "Default branch", click the switch icon
3. Select `testing` as the default branch
4. Click **Update**
5. Confirm the change

This ensures all new work starts on the development branch.

## Step 5: Verify CI/CD Setup

1. Go to the **Actions** tab in your repository
2. You should see three workflows:
   - Testing Branch CI
   - Pre-Production CI/CD
   - Production Deployment
3. Make a small change and push to `testing` to trigger the first workflow

## Step 6: Test the Pipeline

```bash
# Make sure you're on testing branch
git checkout testing

# Make a test change
echo "# Test" >> TEST.md
git add TEST.md
git commit -m "test: verify CI/CD pipeline"
git push origin testing

# Check GitHub Actions tab to see the workflow run
```

## Branch Workflow Summary

```
┌─────────────────────────────────────────────────────────┐
│                    Development Flow                      │
└─────────────────────────────────────────────────────────┘

testing (development)
   │
   │ Pull Request + Review
   ↓
pre-prod (staging)
   │
   │ Pull Request + Review + Approval
   ↓
prod (production)
```

## Quick Commands Reference

```bash
# Start new feature
git checkout testing
git pull origin testing
git checkout -b feature/my-feature
# ... make changes ...
git add .
git commit -m "feat: add new feature"
git push origin feature/my-feature
# Create PR to testing on GitHub

# Promote to pre-prod
git checkout pre-prod
git pull origin pre-prod
git merge testing
git push origin pre-prod

# Deploy to production
git checkout prod
git pull origin prod
git merge pre-prod
git push origin prod
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

## Important Notes

⚠️ **Model Files**: The `.gguf` model files are excluded from git (they're too large). You'll need to:
- Use Git LFS for model files, OR
- Download them separately during deployment, OR
- Store them in external storage (S3, etc.)

⚠️ **Environment Variables**: For production, add secrets in:
- GitHub → Settings → Secrets and variables → Actions
- Add any API keys or sensitive configuration

⚠️ **First Push**: The first push might take a while depending on your project size.

## Troubleshooting

### If you get authentication errors:
```bash
# Use GitHub CLI
gh auth login

# Or use personal access token
# Go to GitHub → Settings → Developer settings → Personal access tokens
# Generate new token with 'repo' scope
# Use token as password when pushing
```

### If remote already exists:
```bash
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/twhyne-ai.git
```

### If you need to force push (use with caution):
```bash
git push -f origin prod
```

## Next Steps

1. ✅ Push code to GitHub
2. ✅ Configure branch protection
3. ✅ Set up team access (if applicable)
4. ✅ Add repository secrets for deployment
5. ✅ Test CI/CD pipeline
6. ✅ Create first release

---

**Ready to push?** Start with Step 2 above! 🚀
