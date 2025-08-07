# EasyRead AWS Deployment Proposal

A step-by-step guide to deploy the EasyRead application to AWS without Docker, using native Python deployment.

## 🏗️ Target Architecture

```
CloudFront (Frontend) → ALB → EC2 (Backend + Nginx) → RDS PostgreSQL
                                     ↓
                               S3 (Media Storage)
```

## 📋 Prerequisites

- AWS CLI configured with appropriate permissions
- Python 3.11+ installed on deployment server
- Node.js 18+ for frontend build
- Access to current PostgreSQL database
- SSH access to EC2 instances

---

## Step 1: Database Setup (RDS PostgreSQL)

### 1.1 Create RDS Instance
- Create PostgreSQL 15.4+ instance with appropriate sizing

### 1.2 Enable pgvector Extension
- Connect to RDS instance
- Create the `vector` extension

---

## Step 2: S3 Storage Setup

### 2.1 Create S3 Bucket
- Create production bucket for media files
- Configure public read access for images

### 2.2 Upload Global Symbols Images
- Upload `images/globalsymbols_data/` to S3, preserving structure

---

## Step 3: Backend Configuration

### 3.1 Create Production Settings
- Create `backend/easyread_backend/settings_aws.py` with production overrides
- Configure RDS database connection
- Set up S3 storage backends
- Configure security settings (SSL, CORS, etc.)

### 3.2 Update Dependencies
- Add AWS-specific packages to requirements.txt
- Include django-storages, boto3, logging libraries

### 3.3 Production Python Setup
- Create requirements file with production dependencies
- Configure uwsgi/gunicorn for production WSGI serving

---

## Step 4: Frontend Configuration

### 4.1 Production Environment Setup
- Create production environment variables
- Configure API and media base URLs
- Set Global Symbols base URL for S3

### 4.2 Build Production Assets
- Install dependencies and build frontend

---

## Step 5: EC2 Server Setup

### 5.1 EC2 Instance Configuration
- Launch EC2 instance with appropriate sizing (t3.medium or larger recommended)
- Configure security groups for HTTP(S), SSH access
- Install system dependencies (Python 3.11+, Node.js 18+, nginx, postgresql-client)
- Set up swap if needed for memory management

### 5.2 System Dependencies Installation
```bash
# Ubuntu/Debian commands
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
sudo apt install -y nodejs npm nginx postgresql-client
sudo apt install -y git curl wget unzip
sudo apt install -y build-essential libpq-dev
```

### 5.3 User and Directory Setup
```bash
# Create dedicated user for the application
sudo useradd -m -s /bin/bash easyread
sudo usermod -aG sudo easyread

# Create application directories
sudo mkdir -p /opt/easyread
sudo chown easyread:easyread /opt/easyread
```

---

## Step 6: Application Deployment

### 6.1 Code Deployment
```bash
# Switch to easyread user and navigate to application directory
sudo su - easyread
cd /opt/easyread

# Clone the repository (or copy files via scp/rsync)
git clone https://github.com/your-org/easyread.git .
# OR: rsync -av --exclude '.git' --exclude 'node_modules' /local/path/ .

# Create production virtual environment
python3.11 -m venv production_env
source production_env/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Additional production dependencies
pip install gunicorn uwsgi psycopg2-binary django-storages boto3
```

### 6.2 Environment Variables
```bash
# Create production environment file
sudo tee /opt/easyread/.env.production << EOF
# Django settings
DEBUG=False
SECRET_KEY=your-production-secret-key
DJANGO_SETTINGS_MODULE=easyread_backend.settings_aws

# Database
DB_ENGINE=django.db.backends.postgresql
DB_NAME=easyread_prod
DB_USER=easyread_user
DB_PASSWORD=your-db-password
DB_HOST=your-rds-endpoint.region.rds.amazonaws.com
DB_PORT=5432

# AWS Configuration
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION_NAME=us-east-1
AWS_STORAGE_BUCKET_NAME=easyread-prod-media

# Admin credentials
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@your-organization.org
DJANGO_SUPERUSER_PASSWORD=your-secure-password

# Security
ALLOWED_HOSTS=your-domain.com,www.your-domain.com,ec2-instance-ip
CORS_ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com
EOF

# Set proper permissions
chmod 600 /opt/easyread/.env.production
```

### 6.3 Frontend Build
```bash
# Build frontend for production
cd /opt/easyread/frontend
npm install --production=false
npm run build

# Copy built files to nginx serve directory
sudo mkdir -p /var/www/easyread
sudo cp -r dist/* /var/www/easyread/
sudo chown -R www-data:www-data /var/www/easyread
```

### 6.4 Database Migration
```bash
# Navigate to backend directory
cd /opt/easyread/backend
source ../production_env/bin/activate

# Load environment variables
set -a
source ../.env.production
set +a

# Run migrations
python manage.py migrate

# Create superuser account
python manage.py createsuperuser --noinput

# Collect static files
python manage.py collectstatic --noinput
```

---

## Step 7: Service Configuration

### 7.1 Create Systemd Service for Django
```bash
# Create gunicorn service file
sudo tee /etc/systemd/system/easyread-backend.service << EOF
[Unit]
Description=EasyRead Django Backend
After=network.target

[Service]
Type=notify
User=easyread
Group=easyread
RuntimeDirectory=easyread
WorkingDirectory=/opt/easyread/backend
Environment="PATH=/opt/easyread/production_env/bin"
EnvironmentFile=/opt/easyread/.env.production
ExecStart=/opt/easyread/production_env/bin/gunicorn \\
    --bind unix:/run/easyread/easyread.sock \\
    --workers 4 \\
    --timeout 300 \\
    --max-requests 1000 \\
    --max-requests-jitter 50 \\
    --preload \\
    --access-logfile /var/log/easyread/access.log \\
    --error-logfile /var/log/easyread/error.log \\
    --log-level info \\
    easyread_backend.wsgi:application
ExecReload=/bin/kill -s HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Create log directory
sudo mkdir -p /var/log/easyread
sudo chown easyread:easyread /var/log/easyread

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable easyread-backend
sudo systemctl start easyread-backend
```

### 7.2 Configure Nginx
```bash
# Create nginx configuration
sudo tee /etc/nginx/sites-available/easyread << EOF
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    # Frontend static files
    location / {
        root /var/www/easyread;
        try_files \$uri \$uri/ /index.html;
        
        # Cache static assets
        location ~* \\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # Backend API
    location /api/ {
        include proxy_params;
        proxy_pass http://unix:/run/easyread/easyread.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Increase timeout for AI processing
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Admin interface
    location /admin/ {
        include proxy_params;
        proxy_pass http://unix:/run/easyread/easyread.sock;
    }

    # Media files (served directly by nginx for performance)
    location /media/ {
        alias /opt/easyread/media/;
        expires 1y;
        add_header Cache-Control "public";
    }

    # Static files (Django admin, etc.)
    location /static/ {
        alias /opt/easyread/backend/staticfiles/;
        expires 1y;
        add_header Cache-Control "public";
    }

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";
}
EOF

# Enable the site
sudo ln -s /etc/nginx/sites-available/easyread /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 7.3 SSL Configuration (Optional but Recommended)
```bash
# Install certbot for Let's Encrypt SSL
sudo apt install -y certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Test automatic renewal
sudo certbot renew --dry-run
```

---

## Step 8: Populate the Database

### 8.1 Image Data Migration
```bash
cd /opt/easyread/backend
source ../production_env/bin/activate

# Load environment variables
set -a
source ../.env.production
set +a

# Upload images to S3 first (if not done already)
aws s3 sync ../images/globalsymbols_data/ s3://your-bucket/images/globalsymbols_data/ --recursive

# Load images from CSV with S3 paths
python manage.py load_images_from_csv ../globalsymbols_images.csv --media-root s3://your-bucket/
```

---

## Step 9: Admin Account Setup

### 9.1 Create Admin Superuser Account

The EasyRead application includes an admin interface that requires authentication. You must create an admin superuser account to access administrative functions.

**Method 1: Interactive Setup (Recommended)**
```bash
# Connect to your production server and activate environment
cd /opt/easyread/backend
source ../production_env/bin/activate
set -a; source ../.env.production; set +a

python manage.py createsuperuser

# You'll be prompted for:
Username: admin
Email address: your-email@unicef.org
Password: [enter secure password]
Password (again): [confirm password]
```

**Method 2: Non-Interactive Setup (Scripted)**
```bash
# Set environment variables for automated setup
export DJANGO_SUPERUSER_USERNAME=admin
export DJANGO_SUPERUSER_EMAIL=your-email@unicef.org
export DJANGO_SUPERUSER_PASSWORD=your-secure-password

# Create superuser non-interactively
python manage.py createsuperuser --noinput
```

**Method 3: Using Management Commands**
```bash
# Alternative using Django shell
python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
User.objects.create_superuser('admin', 'your-email@unicef.org', 'your-secure-password')
"
```

### 8.2 Password Security Requirements

**Strong Password Guidelines:**
- Minimum 12 characters long
- Include uppercase and lowercase letters
- Include numbers and special characters
- Avoid common dictionary words
- Don't use personal information

**Example Strong Password:**
`EasyRead2024!AdminSecure#`

### 8.3 Environment Variable Configuration

For automated deployments, store the admin credentials securely:

**In your production environment variables:**
```bash
# Add to your production .env file or AWS Parameter Store
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@your-organization.org
DJANGO_SUPERUSER_PASSWORD=your-secure-password

# Optional: Auto-create superuser on deployment
AUTO_CREATE_SUPERUSER=true
```

**For Docker deployments:**
```yaml
# In docker-compose.prod.yml
services:
  backend:
    environment:
      - DJANGO_SUPERUSER_USERNAME=admin
      - DJANGO_SUPERUSER_EMAIL=admin@your-organization.org
      - DJANGO_SUPERUSER_PASSWORD=your-secure-password
```

### 8.4 Where Admin Credentials Are Used

The admin credentials provide access to the following areas:

**1. Web Admin Interface**
- **URL**: `https://your-domain.com/admin/login/`
- **Purpose**: Django admin interface for database management
- **Access**: User management, content management, system configuration

**2. EasyRead Admin Dashboard**
- **URL**: `https://your-domain.com/api/admin/dashboard/`
- **Purpose**: Custom React-based admin interface
- **Features**: Image management, content analytics, system monitoring

**3. API Authentication Endpoints**
- **Login**: `POST /api/admin/api/login/`
- **Status Check**: `GET /api/admin/check-auth/`
- **Logout**: `POST /api/admin/api/logout/`

### 8.5 API Authentication Usage

**Programmatic Admin Access:**
```bash
# Login to get session cookie
curl -X POST https://your-domain.com/api/admin/api/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-secure-password"}' \
  -c cookies.txt

# Check authentication status
curl -X GET https://your-domain.com/api/admin/check-auth/ \
  -b cookies.txt

# Access admin-only endpoints with session
curl -X GET https://your-domain.com/api/admin/dashboard/ \
  -b cookies.txt
```

### 8.6 Additional Admin Configuration

**Create Additional Admin Users (Optional):**
```bash
# Create additional staff users
python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
user = User.objects.create_user('staff_user', 'staff@your-org.org', 'staff-password');
user.is_staff = True;
user.save()
"
```

**Password Management:**
```bash
# Change admin password if needed
python manage.py changepassword admin

# Or reset programmatically
python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
user = User.objects.get(username='admin');
user.set_password('new-secure-password');
user.save()
"
```

### 8.7 Security Considerations

**Credential Storage:**
- **AWS Parameter Store**: Store admin credentials as SecureString parameters
- **AWS Secrets Manager**: Alternative for credential management
- **Environment Variables**: Use for container-based deployments
- **Never**: Store passwords in source code or configuration files

**AWS Parameter Store Setup:**
```bash
# Store admin credentials in AWS Parameter Store
aws ssm put-parameter \
  --name "/easyread/prod/DJANGO_SUPERUSER_USERNAME" \
  --value "admin" \
  --type "String"

aws ssm put-parameter \
  --name "/easyread/prod/DJANGO_SUPERUSER_PASSWORD" \
  --value "your-secure-password" \
  --type "SecureString"

aws ssm put-parameter \
  --name "/easyread/prod/DJANGO_SUPERUSER_EMAIL" \
  --value "admin@your-organization.org" \
  --type "String"
```

**Retrieve Parameters in Production:**
```bash
# In your deployment script or container startup
export DJANGO_SUPERUSER_USERNAME=$(aws ssm get-parameter --name "/easyread/prod/DJANGO_SUPERUSER_USERNAME" --query 'Parameter.Value' --output text)
export DJANGO_SUPERUSER_PASSWORD=$(aws ssm get-parameter --name "/easyread/prod/DJANGO_SUPERUSER_PASSWORD" --with-decryption --query 'Parameter.Value' --output text)
export DJANGO_SUPERUSER_EMAIL=$(aws ssm get-parameter --name "/easyread/prod/DJANGO_SUPERUSER_EMAIL" --query 'Parameter.Value' --output text)
```

**Production Deployment Script:**
```bash
#!/bin/bash
# deployment-script.sh

# Navigate to application directory
cd /opt/easyread/backend
source ../production_env/bin/activate

# Load admin credentials from AWS Parameter Store
echo "Loading admin credentials..."
export DJANGO_SUPERUSER_USERNAME=$(aws ssm get-parameter --name "/easyread/prod/DJANGO_SUPERUSER_USERNAME" --query 'Parameter.Value' --output text)
export DJANGO_SUPERUSER_PASSWORD=$(aws ssm get-parameter --name "/easyread/prod/DJANGO_SUPERUSER_PASSWORD" --with-decryption --query 'Parameter.Value' --output text)
export DJANGO_SUPERUSER_EMAIL=$(aws ssm get-parameter --name "/easyread/prod/DJANGO_SUPERUSER_EMAIL" --query 'Parameter.Value' --output text)

# Load production environment
set -a
source ../.env.production
set +a

# Run migrations
echo "Running database migrations..."
python manage.py migrate

# Create superuser if it doesn't exist
echo "Creating admin superuser..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
import os
User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(
        username=os.environ.get('DJANGO_SUPERUSER_USERNAME'),
        email=os.environ.get('DJANGO_SUPERUSER_EMAIL'),
        password=os.environ.get('DJANGO_SUPERUSER_PASSWORD')
    )
    print(f'Superuser {username} created successfully')
else:
    print(f'Superuser {username} already exists')
"

# Restart backend service to apply any changes
echo "Restarting backend service..."
sudo systemctl restart easyread-backend

echo "Admin account setup complete!"
```

### 8.8 Testing Admin Access

After deployment, verify admin access works correctly:

**1. Test Web Interface:**
```bash
# Visit admin URLs in browser
https://your-domain.com/admin/login/
https://your-domain.com/api/admin/dashboard/
```

**2. Test API Authentication:**
```bash
# Test API login
curl -X POST https://your-domain.com/api/admin/api/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-secure-password"}' \
  -v

# Expected: HTTP 200 with success message
```

**3. Verify Dashboard Access:**
- Login to admin interface
- Check that React dashboard loads properly
- Verify image management and analytics features work
- Test logout functionality

---

## Step 10: Post-Deployment Configuration and Monitoring

### 10.1 System Health Check
```bash
# Verify system health
curl https://your-domain.com/api/health/

# Check service status
sudo systemctl status easyread-backend
sudo systemctl status nginx

# Check logs
sudo journalctl -u easyread-backend -f
sudo tail -f /var/log/easyread/error.log
```

### 10.2 Validate Admin Features
- Test admin login and dashboard access
- Verify image upload and management works
- Check analytics reporting functionality
- Test content export features

### 10.3 Monitoring and Maintenance
```bash
# Set up log rotation
sudo tee /etc/logrotate.d/easyread << EOF
/var/log/easyread/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 easyread easyread
    postrotate
        systemctl reload easyread-backend > /dev/null 2>&1 || true
    endscript
}
EOF

# Set up monitoring script (optional)
sudo tee /usr/local/bin/easyread-monitor.sh << EOF
#!/bin/bash
# Simple monitoring script for EasyRead

# Check if service is running
if ! systemctl is-active --quiet easyread-backend; then
    echo "EasyRead backend service is down!"
    sudo systemctl restart easyread-backend
fi

# Check if nginx is running
if ! systemctl is-active --quiet nginx; then
    echo "Nginx service is down!"
    sudo systemctl restart nginx
fi

# Check database connectivity
if ! curl -f -s https://your-domain.com/api/health/ > /dev/null; then
    echo "EasyRead health check failed!"
fi
EOF

chmod +x /usr/local/bin/easyread-monitor.sh

# Add to crontab for periodic checks (every 5 minutes)
echo "*/5 * * * * /usr/local/bin/easyread-monitor.sh" | sudo crontab -
```

### 10.4 Security Hardening
- Rotate default admin password if needed
- Configure session timeout settings
- Set up monitoring for failed login attempts
- Review and configure CORS settings
- Enable firewall (UFW) with appropriate rules
- Set up fail2ban for SSH protection

---

## 🔐 Admin Account Summary

**Quick Reference for Admin Setup:**

| Component | Details |
|-----------|---------|
| **Username** | `admin` (or your choice) |
| **Email** | Your organization email |
| **Password** | Secure 12+ character password |
| **Web Login** | `https://your-domain.com/admin/login/` |
| **Dashboard** | `https://your-domain.com/api/admin/dashboard/` |
| **API Login** | `POST /api/admin/api/login/` |

**Environment Variables Needed:**
- `DJANGO_SUPERUSER_USERNAME`
- `DJANGO_SUPERUSER_EMAIL` 
- `DJANGO_SUPERUSER_PASSWORD`

**AWS Parameter Store Paths:**
- `/easyread/prod/DJANGO_SUPERUSER_USERNAME`
- `/easyread/prod/DJANGO_SUPERUSER_EMAIL`
- `/easyread/prod/DJANGO_SUPERUSER_PASSWORD` (SecureString)

**Admin Access Includes:**
- ✅ Django admin interface for database management
- ✅ Custom React dashboard for image management
- ✅ Analytics and system monitoring
- ✅ Content management and export features
- ✅ API authentication for programmatic access

---

## 🚀 Deployment Checklist

**Before Deployment:**
- [ ] RDS PostgreSQL instance created with pgvector extension
- [ ] S3 bucket configured for media storage
- [ ] EC2 instance launched and configured
- [ ] System dependencies installed (Python 3.11+, Node.js, nginx)
- [ ] Admin credentials stored securely (Parameter Store)
- [ ] Production environment variables configured

**During Deployment:**
- [ ] Application code deployed to /opt/easyread
- [ ] Python virtual environment created and dependencies installed
- [ ] Frontend built and deployed to nginx directory
- [ ] Database migrations applied
- [ ] Admin superuser account created
- [ ] Systemd service configured and started
- [ ] Nginx configured with SSL (optional)
- [ ] Images loaded from CSV with S3 paths updated

**After Deployment:**
- [ ] Backend service running (systemctl status easyread-backend)
- [ ] Nginx service running and proxying correctly
- [ ] Health check endpoints responding
- [ ] Admin login tested (web and API)
- [ ] Dashboard functionality verified
- [ ] Image upload and search working
- [ ] Content export features tested
- [ ] Analytics tracking operational
- [ ] Monitoring and log rotation configured

---

## 🔄 Development vs Production Environment

This deployment guide focuses on **production deployment without Docker**. For development, Docker remains the recommended approach:

### Development Environment (Docker-Based)
- **Use**: Docker Compose as documented in CLAUDE.md
- **Command**: `docker compose up -d` for database, manual startup for backend/frontend
- **Benefits**: Easy setup, isolated environment, matches team development workflow
- **Database**: PostgreSQL 17 with pgvector in Docker container

### Production Environment (Native Python)
- **Use**: Native Python virtual environment (this guide)
- **Benefits**: Better performance, easier monitoring, standard Linux service management
- **Database**: AWS RDS PostgreSQL with pgvector
- **Web Server**: Nginx + Gunicorn
- **Process Management**: systemd services

### Quick Development Setup Reminder
```bash
# For development (keep using Docker)
docker compose up -d postgres          # Start database
cd backend && python manage.py start_server  # Start backend
cd frontend && npm run dev             # Start frontend
```

**Development vs Production:**
- ✅ **Development**: Continue using Docker Compose as documented in CLAUDE.md
- ✅ **Production**: Use native Python virtual environment deployment (this guide)
