# Deployment Guide

This guide covers automated deployment to the VPS (unicef-tailscale).

## Overview

The application uses **GitHub Actions** for automated deployment. Pushing to the `vps-version` branch automatically deploys to the VPS.

## Initial Setup (One-Time)

### 1. Set Up Git on VPS

SSH into the VPS and run the setup script:

```bash
ssh ec2-user@unicef-tailscale
cd ~/easyread
bash <(curl -s https://raw.githubusercontent.com/UNICEF-Ventures/easyRead/vps-version/setup-vps-deployment.sh)
```

Or manually:

```bash
ssh ec2-user@unicef-tailscale
cd ~/easyread
git init
git remote add origin git@github.com:UNICEF-Ventures/easyRead.git
git fetch origin
git checkout -B vps-version origin/vps-version
```

### 2. Configure Environment Variables

Ensure `.env` file exists with production configuration:

```bash
cp .env.vps.example .env
# Edit .env with production values
nano .env
```

Required variables:
- `SECRET_KEY` - Django secret key
- `POSTGRES_PASSWORD` - Database password
- `AWS_ACCESS_KEY_ID` - AWS credentials for Bedrock
- `AWS_SECRET_ACCESS_KEY`
- `VITE_AUTH_METHOD=oauth` - Enable OAuth authentication
- `VITE_OIDC_CLIENT_ID` - Auth0 client ID
- (See `.env.vps.example` for full list)

### 3. Set Up GitHub Actions SSH Access

Generate SSH key for GitHub Actions:

```bash
ssh ec2-user@unicef-tailscale
ssh-keygen -t ed25519 -C 'github-actions@easyread' -f ~/.ssh/github_actions_key -N ''
cat ~/.ssh/github_actions_key.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/github_actions_key
```

Add the private key to GitHub Secrets:
1. Go to repository Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `VPS_SSH_KEY`
4. Value: Paste the entire private key (output from `cat ~/.ssh/github_actions_key`)

## Automated Deployment

### How It Works

1. Push code to `vps-version` branch
2. GitHub Actions workflow triggers automatically
3. Workflow SSHs into VPS
4. Pulls latest code from GitHub
5. Rebuilds Docker containers
6. Restarts services

### Triggering Deployment

```bash
# Make your changes locally
git checkout vps-version
git add .
git commit -m "Your changes"
git push github vps-version
```

GitHub Actions will automatically:
- ✅ Pull latest code on VPS
- ✅ Rebuild frontend and backend containers
- ✅ Restart all services
- ✅ Verify deployment

### Manual Deployment

To manually deploy without GitHub Actions:

```bash
ssh ec2-user@unicef-tailscale
cd ~/easyread
git pull origin vps-version
docker-compose -f docker-compose.vps.yml build --no-cache
docker-compose -f docker-compose.vps.yml up -d
```

## Monitoring

### View Logs

```bash
ssh ec2-user@unicef-tailscale

# All services
docker-compose -f ~/easyread/docker-compose.vps.yml logs -f

# Specific service
docker-compose -f ~/easyread/docker-compose.vps.yml logs -f frontend
docker-compose -f ~/easyread/docker-compose.vps.yml logs -f backend
```

### Check Service Status

```bash
docker-compose -f ~/easyread/docker-compose.vps.yml ps
```

### Access Application

- **Production URL**: https://easyread.ooi.ventures
- **Health Check**: https://easyread.ooi.ventures/api/health/

## Rollback

To rollback to a previous version:

```bash
ssh ec2-user@unicef-tailscale
cd ~/easyread

# Find commit to rollback to
git log --oneline -10

# Rollback to specific commit
git reset --hard <commit-hash>

# Rebuild and restart
docker-compose -f docker-compose.vps.yml build --no-cache
docker-compose -f docker-compose.vps.yml up -d
```

## Troubleshooting

### Deployment Failed

Check GitHub Actions logs:
1. Go to repository → Actions
2. Click on failed workflow run
3. Review error messages

### Services Not Starting

```bash
ssh ec2-user@unicef-tailscale
cd ~/easyread

# Check logs
docker-compose -f docker-compose.vps.yml logs --tail=100

# Restart services
docker-compose -f docker-compose.vps.yml down
docker-compose -f docker-compose.vps.yml up -d
```

### OAuth Not Working

Verify environment variables are set:

```bash
ssh ec2-user@unicef-tailscale
grep VITE_AUTH_METHOD ~/easyread/.env
grep VITE_OIDC_CLIENT_ID ~/easyread/.env
```

Should show:
```
VITE_AUTH_METHOD=oauth
VITE_OIDC_CLIENT_ID=Bekf31qBtJ1nOAKweRPoJ4dSqK8ReCMM
```

If missing, update `.env` and rebuild:

```bash
docker-compose -f ~/easyread/docker-compose.vps.yml build --no-cache frontend
docker-compose -f ~/easyread/docker-compose.vps.yml up -d
```

## Security Notes

- ⚠️ Never commit `.env` file to git
- ⚠️ Protect GitHub Actions secrets
- ⚠️ Rotate SSH keys periodically
- ⚠️ Keep Docker images updated

## Support

For issues or questions about deployment, contact the development team.
