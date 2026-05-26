#!/bin/bash

# Immich Minigames Docker Startup Script
# This script simplifies the Docker Compose workflow

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  🎮 Immich Minigames Docker Manager${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

print_section() {
    echo ""
    echo -e "${BLUE}→ $1${NC}"
}

# Check for Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed"
        exit 1
    fi
    
    print_success "Docker and Docker Compose are installed"
}

# Start services
start_services() {
    print_section "Starting services..."
    
    ENV_FILE="${1:-.env.docker}"
    
    if [ ! -f "$ENV_FILE" ]; then
        print_error "Environment file '$ENV_FILE' not found"
        print_info "Use: docker-startup.sh [env-file]"
        print_info "Example: docker-startup.sh .env.docker.local"
        exit 1
    fi
    
    print_info "Using environment file: $ENV_FILE"
    
    docker compose --env-file "$ENV_FILE" up -d
    
    print_success "Services started"
}

# Stop services
stop_services() {
    print_section "Stopping services..."
    docker compose down
    print_success "Services stopped"
}

# Show status
show_status() {
    print_section "Service Status"
    docker compose ps
}

# Show logs
show_logs() {
    SERVICE="${1:-}"
    
    if [ -z "$SERVICE" ]; then
        print_section "Showing logs from all services (Ctrl+C to exit)..."
        docker compose logs -f
    else
        print_section "Showing logs from $SERVICE (Ctrl+C to exit)..."
        docker compose logs -f "$SERVICE"
    fi
}

# Access database
access_database() {
    print_section "Accessing PostgreSQL database..."
    docker compose exec postgres psql -U postgres -d immich_minigames
}

# Access Redis
access_redis() {
    print_section "Accessing Redis..."
    docker compose exec redis redis-cli
}

# Show info
show_info() {
    print_section "Application URLs"
    echo -e "  Frontend:  ${GREEN}http://localhost:3000${NC}"
    echo -e "  Backend:   ${GREEN}http://localhost:8000${NC}"
    echo -e "  API Docs:  ${GREEN}http://localhost:8000/docs${NC}"
    echo -e "  Database:  ${GREEN}localhost:5432${NC}"
    echo -e "  Redis:     ${GREEN}localhost:6379${NC}"
    
    print_section "Next steps:"
    echo -e "  1. Go to ${GREEN}http://localhost:3000${NC}"
    echo -e "  2. Configure your Immich connection"
    echo -e "  3. Start playing!"
}

# Rebuild images
rebuild_images() {
    print_section "Rebuilding Docker images..."
    docker compose build --no-cache
    print_success "Images rebuilt"
}

# Show help
show_help() {
    cat << EOF
${BLUE}Immich Minigames Docker Manager${NC}

Usage: ./docker-startup.sh [COMMAND] [OPTIONS]

Commands:
    start [env-file]      Start services (default: .env.docker)
    stop                  Stop all services
    status                Show service status
    logs [service]        Show logs (optional: specify service)
    db                    Access PostgreSQL database
    redis                 Access Redis CLI
    rebuild               Rebuild Docker images
    info                  Show application URLs
    help                  Show this help message

Examples:
    ./docker-startup.sh start
    ./docker-startup.sh start .env.docker.local
    ./docker-startup.sh logs backend
    ./docker-startup.sh status

EOF
}

# Main
main() {
    print_header
    
    check_docker
    
    COMMAND="${1:-help}"
    
    case "$COMMAND" in
        start)
            start_services "${2:-.env.docker}"
            print_info "Waiting for services to be ready..."
            sleep 3
            show_status
            show_info
            ;;
        stop)
            stop_services
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs "$2"
            ;;
        db)
            access_database
            ;;
        redis)
            access_redis
            ;;
        rebuild)
            rebuild_images
            ;;
        info)
            show_info
            ;;
        help|"")
            show_help
            ;;
        *)
            print_error "Unknown command: $COMMAND"
            echo ""
            show_help
            exit 1
            ;;
    esac
    
    echo ""
}

# Run main function with all arguments
main "$@"
