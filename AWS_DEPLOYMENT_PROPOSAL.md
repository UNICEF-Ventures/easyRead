# EasyRead AWS Deployment Proposal

A step-by-step guide to deploy the EasyRead application to AWS with proper data migration.

## 🏗️ Target Architecture

```
CloudFront (Frontend) → ALB → ECS/EC2 (Backend) → RDS PostgreSQL
                                     ↓
                               S3 (Media Storage)
```

## 📋 Prerequisites

- AWS CLI configured with appropriate permissions
- Docker installed locally
- Access to current PostgreSQL database
- Domain name (optional)

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

### 3.3 Create Production Dockerfile
- Build optimized production container

---

## Step 4: Frontend Configuration

### 4.1 Production Environment Setup
- Create production environment variables
- Configure API and media base URLs
- Set Global Symbols base URL for S3

### 4.2 Build Production Assets
- Install dependencies and build frontend

---

## Step 5: Container Orchestration

### 5.1 Production Docker Compose
- Configure backend service with production settings
- Set up nginx reverse proxy
- Configure SSL termination
- Add health checks and restart policies

### 5.2 Container Registry Setup
- Create ECR repository (if using ECS)
- Build and push backend image
- Tag appropriately for deployment

---

## Step 6: Application Deployment

### 6.1 Environment Variables
- Set all required production environment variables
- Configure database connection parameters
- Set AWS credentials and region
- Configure Django and frontend settings

### 6.2 Database Migration
- Run Django migrations on production database
- Create superuser account (if needed)
- Load initial data and configurations

---

## Step 7: Populate the database

- **Step A**: Keep local `images/globalsymbols_data/` temporarily for processing
- **Step B**: Run `load_images_from_csv globalsymbols_images.csv` with local paths
- **Step C**: Update paths in the database to S3 URLs after database is populated
- **Step D**: Clean up local images once verification is complete
