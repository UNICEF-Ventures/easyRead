#!/bin/bash

# EasyRead Docker Startup Script
# This script helps you start the EasyRead application using Docker

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_color() {
    printf "${1}%s${NC}\n" "$2"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_color $RED "❌ Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_color $GREEN "✅ Docker is running"
}

# Function to check if .env file exists
check_env() {
    if [ ! -f .env ]; then
        print_color $YELLOW "⚠️  No .env file found. Creating from .env.example..."
        if [ -f .env.example ]; then
            cp .env.example .env
            print_color $YELLOW "📝 Please edit .env file with your actual values before continuing"
            print_color $BLUE "💡 Tip: You can run 'docker-compose up -d postgres' first to start just the database"
            exit 1
        else
            print_color $RED "❌ No .env.example file found. Please create a .env file manually."
            exit 1
        fi
    fi
    print_color $GREEN "✅ .env file found"
}

# Function to create necessary directories
create_directories() {
    print_color $BLUE "📁 Creating necessary directories..."
    mkdir -p media
    mkdir -p logs
    print_color $GREEN "✅ Directories created"
}

# Function to start development environment
start_dev() {
    print_color $BLUE "🚀 Starting EasyRead development environment..."
    
    # Build and start services
    docker compose up --build -d
    
    print_color $GREEN "✅ Development environment started!"
    print_color $BLUE "📱 Frontend: http://localhost:3000"
    print_color $BLUE "🔧 Backend API: http://localhost:8001"
    print_color $BLUE "🗄️  Database: localhost:5432"
    
    # Show logs
    print_color $YELLOW "📋 Starting to show logs (Ctrl+C to stop logs, services will keep running)..."
    sleep 2
    docker compose logs -f
}

# Function to start production environment
start_prod() {
    print_color $BLUE "🚀 Starting EasyRead production environment..."
    
    # Check for production requirements
    if [ ! -f docker-compose.prod.yml ]; then
        print_color $RED "❌ docker-compose.prod.yml not found"
        exit 1
    fi
    
    # Build and start services
    docker compose -f docker-compose.prod.yml up --build -d
    
    print_color $GREEN "✅ Production environment started!"
    print_color $BLUE "🌐 Application: http://localhost"
    
    # Show logs
    print_color $YELLOW "📋 Starting to show logs (Ctrl+C to stop logs, services will keep running)..."
    sleep 2
    docker compose -f docker-compose.prod.yml logs -f
}

# Function to stop services
stop_services() {
    print_color $YELLOW "🛑 Stopping EasyRead services..."
    docker compose down
    if [ -f docker-compose.prod.yml ]; then
        docker compose -f docker-compose.prod.yml down
    fi
    print_color $GREEN "✅ Services stopped"
}

# Function to show status
show_status() {
    print_color $BLUE "📊 Service Status:"
    docker compose ps
}

# Function to show help
show_help() {
    echo "EasyRead Docker Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  dev       Start development environment (default)"
    echo "  prod      Start production environment"
    echo "  stop      Stop all services"
    echo "  status    Show service status"
    echo "  logs      Show service logs"
    echo "  restart   Restart all services"
    echo "  clean     Stop services and remove volumes (⚠️  destructive)"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                # Start development environment"
    echo "  $0 dev            # Start development environment"
    echo "  $0 prod           # Start production environment"
    echo "  $0 stop           # Stop all services"
    echo ""
}

# Main script logic
main() {
    print_color $GREEN "🐳 EasyRead Docker Management"
    echo ""
    
    # Check prerequisites
    check_docker
    check_env
    create_directories
    
    # Handle commands
    case "${1:-dev}" in
        "dev")
            start_dev
            ;;
        "prod")
            start_prod
            ;;
        "stop")
            stop_services
            ;;
        "status")
            show_status
            ;;
        "logs")
            print_color $BLUE "📋 Showing logs..."
            docker compose logs -f
            ;;
        "restart")
            print_color $YELLOW "🔄 Restarting services..."
            docker compose restart
            print_color $GREEN "✅ Services restarted"
            ;;
        "clean")
            print_color $RED "⚠️  This will stop services and remove volumes (data will be lost)"
            read -p "Are you sure? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                docker compose down -v
                print_color $GREEN "✅ Services stopped and volumes removed"
            else
                print_color $BLUE "Operation cancelled"
            fi
            ;;
        "help")
            show_help
            ;;
        *)
            print_color $RED "❌ Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"