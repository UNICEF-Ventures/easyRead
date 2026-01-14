#!/bin/bash
# Setup script to initialize git-based deployment on the VPS
# Run this once on the VPS to enable automated deployments

set -e

echo "🔧 Setting up automated deployment on VPS..."

# Check if we're on the VPS
if [ ! -d ~/easyread ]; then
    echo "❌ Error: ~/easyread directory not found"
    echo "This script should be run on the VPS"
    exit 1
fi

cd ~/easyread

# Check if it's already a git repository
if [ -d .git ]; then
    echo "✅ Git repository already initialized"
else
    echo "📦 Initializing git repository..."
    git init
    git remote add origin git@github.com:UNICEF-Ventures/easyRead.git
    echo "✅ Git repository initialized"
fi

# Fetch latest code
echo "📥 Fetching latest code..."
git fetch origin

# Checkout vps-version branch
echo "🔀 Checking out vps-version branch..."
git checkout -B vps-version origin/vps-version || git checkout vps-version

# Ensure .env file exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "Please create .env file with necessary configuration"
    echo "You can use .env.vps.example as a template"
else
    echo "✅ .env file found"
fi

echo ""
echo "✅ VPS deployment setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Ensure .env file is configured with production values"
echo "2. Set up GitHub secrets for automated deployment:"
echo "   - VPS_SSH_KEY: Private SSH key for GitHub Actions to access this VPS"
echo "3. Push to vps-version branch to trigger automatic deployment"
echo ""
echo "🔑 To generate SSH key for GitHub Actions:"
echo "   ssh-keygen -t ed25519 -C 'github-actions@easyread' -f ~/.ssh/github_actions_key"
echo "   cat ~/.ssh/github_actions_key.pub >> ~/.ssh/authorized_keys"
echo "   cat ~/.ssh/github_actions_key  # Add this to GitHub Secrets as VPS_SSH_KEY"
