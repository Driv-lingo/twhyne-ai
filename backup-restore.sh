#!/bin/bash
# Backup and restore script for SNF-AI customer data

set -e

BACKUP_DIR="snf-ai-backup-$(date +%Y%m%d-%H%M%S)"

show_usage() {
    echo "SNF-AI Data Backup/Restore Tool"
    echo "================================"
    echo ""
    echo "Usage:"
    echo "  ./backup-restore.sh backup    - Create backup of all data"
    echo "  ./backup-restore.sh restore <backup-dir> - Restore from backup"
    echo "  ./backup-restore.sh list      - List all volumes and sizes"
    exit 1
}

backup_data() {
    echo "🔒 Creating backup: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
    
    # List of volumes to backup
    VOLUMES=(
        "snf_models"
        "snf_data"
        "snf_conversations"
        "snf_rag"
        "snf_uploads"
        "snf_logs"
        "snf_db"
    )
    
    # Stop container if running
    if docker ps | grep -q twhyne; then
        echo "Stopping container for safe backup..."
        docker stop twhyne
        RESTART_AFTER=true
    fi
    
    # Backup each volume
    for vol in "${VOLUMES[@]}"; do
        if docker volume ls | grep -q "$vol"; then
            echo "Backing up $vol..."
            docker run --rm \
                -v "$vol":/source:ro \
                -v "$(pwd)/$BACKUP_DIR":/backup \
                alpine tar czf "/backup/${vol}.tar.gz" -C /source .
        fi
    done
    
    # Save metadata
    echo "SNF-AI Backup" > "$BACKUP_DIR/metadata.txt"
    echo "Date: $(date)" >> "$BACKUP_DIR/metadata.txt"
    echo "Version: $(docker inspect twhyne/twhyne:latest --format='{{.Config.Labels.version}}' 2>/dev/null || echo 'unknown')" >> "$BACKUP_DIR/metadata.txt"
    docker volume ls | grep snf_ >> "$BACKUP_DIR/metadata.txt" || true
    
    # Restart if was running
    if [ "$RESTART_AFTER" = true ]; then
        echo "Restarting container..."
        docker start twhyne
    fi
    
    echo "✅ Backup complete: $BACKUP_DIR"
    echo "Size: $(du -sh "$BACKUP_DIR" | cut -f1)"
}

restore_data() {
    RESTORE_DIR="$1"
    
    if [ ! -d "$RESTORE_DIR" ]; then
        echo "❌ Backup directory not found: $RESTORE_DIR"
        exit 1
    fi
    
    echo "🔄 Restoring from: $RESTORE_DIR"
    
    # Stop container if running
    if docker ps -a | grep -q twhyne; then
        echo "Removing existing container..."
        docker rm -f twhyne
    fi
    
    # Restore each volume
    for backup_file in "$RESTORE_DIR"/*.tar.gz; do
        if [ -f "$backup_file" ]; then
            vol_name=$(basename "$backup_file" .tar.gz)
            echo "Restoring $vol_name..."
            
            # Create volume if doesn't exist
            docker volume create "$vol_name"
            
            # Restore data
            docker run --rm \
                -v "$vol_name":/target \
                -v "$(pwd)/$RESTORE_DIR":/backup:ro \
                alpine tar xzf "/backup/$(basename "$backup_file")" -C /target
        fi
    done
    
    echo "✅ Restore complete!"
    echo ""
    echo "Start container with:"
    echo "  docker run -d --name twhyne -e SNF_LICENSE_KEY=\"...\" \\"
    echo "    -p 3000:3000 -p 5002:5002 \\"
    echo "    --mount source=snf_models,target=/app/models \\"
    echo "    --mount source=snf_data,target=/app/data \\"
    echo "    --mount source=snf_conversations,target=/app/conversations \\"
    echo "    --mount source=snf_rag,target=/app/rag_storage \\"
    echo "    --mount source=snf_uploads,target=/app/uploads \\"
    echo "    --mount source=snf_logs,target=/app/logs \\"
    echo "    --mount source=snf_db,target=/app/database \\"
    echo "    twhyne/twhyne:latest"
}

list_volumes() {
    echo "📊 SNF-AI Docker Volumes:"
    echo "========================"
    echo ""
    
    docker volume ls | grep snf_ | while read -r line; do
        vol_name=$(echo "$line" | awk '{print $2}')
        if [ ! -z "$vol_name" ]; then
            size=$(docker run --rm -v "$vol_name":/data alpine du -sh /data 2>/dev/null | cut -f1)
            echo "$vol_name: $size"
        fi
    done
    
    echo ""
    echo "Total disk usage:"
    docker system df --verbose | grep -A 10 "VOLUME NAME" | grep snf_
}

# Main logic
case "$1" in
    backup)
        backup_data
        ;;
    restore)
        if [ -z "$2" ]; then
            echo "❌ Please specify backup directory"
            show_usage
        fi
        restore_data "$2"
        ;;
    list)
        list_volumes
        ;;
    *)
        show_usage
        ;;
esac
