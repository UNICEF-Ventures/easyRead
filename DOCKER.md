# EasyRead Docker Setup

This document provides comprehensive instructions for running EasyRead using Docker containers.

## 🏗️ Architecture Overview

The containerized EasyRead application consists of:

- **PostgreSQL + pgvector**: Database with vector similarity search
- **Django Backend**: REST API service
- **React Frontend**: User interface (served by Nginx in production)
- **Nginx**: Reverse proxy and static file server (production only)
- **Redis**: Caching layer (production only)

## 🚀 Quick Start

### Prerequisites

- Docker Desktop installed and running
- Docker Compose v2.0+
- 8GB+ RAM recommended
- 10GB+ free disk space

### 1. Clone and Setup

```bash
git clone <your-repo>
cd easyRead

# Copy environment file
cp .env.example .env

# Edit .env with your API keys and settings
nano .env
```

### 2. Start Development Environment

```bash
# Using the helper script (recommended)
./start-docker.sh dev

# OR using docker-compose directly
docker-compose up --build -d
```

### 3. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Database**: localhost:5432

## 📁 Container Structure

### Backend Container (`easyread_backend`)
- **Base**: Python 3.11 slim
- **Port**: 8000
- **Volumes**: 
  - `./backend:/app` (development)
  - `media_files:/app/media`
  - `./clipart_images:/app/clipart_images:ro`

### Frontend Container (`easyread_frontend`)
- **Base**: Node 18 Alpine + Nginx Alpine
- **Port**: 3000 (mapped to 80 internally)
- **Build**: Multi-stage build for optimization

### Database Container (`easyread_postgres`)
- **Base**: pgvector/pgvector:pg17
- **Port**: 5432
- **Volume**: `postgres_data:/var/lib/postgresql/data`

## 🛠️ Development Workflow

### Starting Services

```bash
# Start all services
./start-docker.sh dev

# Start specific service
docker-compose up postgres -d

# View logs
docker-compose logs -f backend
```

### Running Commands

```bash
# Django management commands
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser
docker-compose exec backend python manage.py collectstatic

# Frontend commands
docker-compose exec frontend npm install
docker-compose exec frontend npm run build

# Database access
docker-compose exec postgres psql -U easyread_user -d easyread
```

### Code Changes

- **Backend**: Code changes are reflected immediately (volume mounted)
- **Frontend**: Vite dev server provides hot reload
- **Configuration**: Restart containers after environment changes

## 🔧 Environment Configuration

### Required Environment Variables

```bash
# Security
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_ENGINE=django.db.backends.postgresql
DB_NAME=easyread
DB_USER=easyread_user
DB_PASSWORD=easyread_password
DB_HOST=postgres
DB_PORT=5432

# AI Services
OPENAI_API_KEY=your-openai-key
GEMINI_API_KEY=your-gemini-key
COHERE_API_KEY=your-cohere-key
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_REGION_NAME=us-east-1
```

### Frontend Environment Variables

```bash
VITE_API_BASE_URL=http://localhost:8000/api
VITE_MEDIA_BASE_URL=http://localhost:8000
```

## 🚀 Production Deployment

### 1. Production Environment File

Create `.env.prod`:

```bash
# Security (IMPORTANT: Use strong values in production)
SECRET_KEY=your-very-secure-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database (Use strong passwords)
DB_NAME=easyread_prod
DB_USER=easyread_prod_user
DB_PASSWORD=very-secure-password

# CORS
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# AI Service Keys (same as development)
OPENAI_API_KEY=your-openai-key
# ... other API keys
```

### 2. Start Production Environment

```bash
# Using helper script
./start-docker.sh prod

# OR manually
docker-compose -f docker-compose.prod.yml up --build -d
```

### 3. Production Features

- **Nginx Reverse Proxy**: Handles static files and SSL termination
- **Gunicorn**: Production WSGI server for Django
- **Redis Caching**: Improves performance
- **Security Headers**: XSS protection, CSP, etc.
- **Rate Limiting**: API request throttling
- **SSL Ready**: HTTPS configuration available

## 🔍 Monitoring and Debugging

### Container Health Checks

```bash
# Check container status
docker-compose ps

# View health check status
docker inspect easyread_backend --format='{{.State.Health.Status}}'
```

### Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres

# Last 100 lines
docker-compose logs --tail=100 backend
```

### Performance Monitoring

```bash
# Container resource usage
docker stats

# Database connections
docker-compose exec postgres psql -U easyread_user -d easyread -c "SELECT count(*) FROM pg_stat_activity;"
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. Port Already in Use
```bash
# Check what's using the port
lsof -i :8000
lsof -i :3000
lsof -i :5432

# Stop conflicting services
docker-compose down
```

#### 2. Database Connection Errors
```bash
# Check database health
docker-compose exec postgres pg_isready -U easyread_user

# Reset database
docker-compose down -v
docker-compose up postgres -d
```

#### 3. Frontend Build Failures
```bash
# Clear node modules and rebuild
docker-compose down frontend
docker-compose build --no-cache frontend
docker-compose up frontend -d
```

#### 4. Permission Issues
```bash
# Fix media directory permissions
sudo chown -R $USER:$USER media/
```

### Container Debugging

```bash
# Access container shell
docker-compose exec backend bash
docker-compose exec frontend sh
docker-compose exec postgres bash

# Check container filesystem
docker-compose exec backend ls -la /app
docker-compose exec backend ps aux
```

## 🧹 Maintenance

### Cleanup Commands

```bash
# Stop and remove containers
docker-compose down

# Remove containers and volumes (⚠️ destroys data)
docker-compose down -v

# Remove unused Docker resources
docker system prune -f

# Remove all EasyRead containers and images
docker-compose down --rmi all
```

### Backup and Restore

```bash
# Backup database
docker-compose exec postgres pg_dump -U easyread_user easyread > backup.sql

# Restore database
docker-compose exec -T postgres psql -U easyread_user easyread < backup.sql

# Backup media files
docker run --rm -v easyread_media_files:/data -v $(pwd):/backup alpine tar czf /backup/media-backup.tar.gz -C /data .

# Restore media files
docker run --rm -v easyread_media_files:/data -v $(pwd):/backup alpine tar xzf /backup/media-backup.tar.gz -C /data
```

## 🔧 Customization

### Adding New Services

1. Add service to `docker-compose.yml`
2. Configure networking and volumes
3. Add environment variables
4. Update nginx configuration if needed

### Scaling Services

```bash
# Scale backend to 3 instances
docker-compose up --scale backend=3 -d

# Scale with load balancer configuration needed
```

### SSL/HTTPS Setup

1. Obtain SSL certificates (Let's Encrypt recommended)
2. Place certificates in `nginx/ssl/`
3. Uncomment HTTPS server block in `nginx/default.conf`
4. Update environment variables for HTTPS URLs

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Django Docker Best Practices](https://docs.docker.com/samples/django/)
- [React Docker Deployment](https://create-react-app.dev/docs/deployment/)
- [Nginx Configuration Guide](https://nginx.org/en/docs/)

## 🆘 Getting Help

If you encounter issues:

1. Check the logs: `docker-compose logs -f`
2. Verify environment variables in `.env`
3. Ensure Docker has sufficient resources
4. Check the troubleshooting section above
5. Create an issue in the project repository

---

**Happy Dockerizing! 🐳**