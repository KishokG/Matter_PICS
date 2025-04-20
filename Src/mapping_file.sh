#!/bin/bash

# Exit if any command in a pipeline fails
set -o pipefail

# Log file
LOG_FILE="run_log.txt"

# Function to log with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Clear previous log
echo "===== Run started at $(date '+%Y-%m-%d %H:%M:%S') =====" > "$LOG_FILE"

# Run script1.py
log "🔧 Pulling_mapping_datas from HTML file..."
if python3 Mapping_datas_pull.py 2>&1 | tee -a "$LOG_FILE"; then
    log "✅ Mapping_datas_pull.py completed successfully."
    
    # Run script2.py only if script1.py was successful
    log "🔧 Creating Json mapping file..."
    if python3 Json_mapping.py 2>&1 | tee -a "$LOG_FILE"; then
        log "✅ Json_mapping.py completed successfully."
        log "🎉 All scripts finished without errors."
    else
        log "❌ Json_mapping.py failed."
        exit 2
    fi
else
    log "❌ Mapping_datas_pull.py failed. Aborting."
    exit 1
fi
