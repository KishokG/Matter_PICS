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

# Navigate to the Scripts folder
cd "$(dirname "$0")/Scripts" || {
    log "❌ Failed to find Scripts folder. Aborting."
    exit 1
}

# Step 1: Run pics_xml_datas.py
log "🔧 Pulling XML datas from HTML file..."
if python3 pics_xml_datas.py 2>&1 | tee -a "../$LOG_FILE"; then
    log "✅ pics_xml_datas.py completed successfully."

    # Step 2: Run conformance.py
    log "🔧 Creating JSON mapping file..."
    if python3 conformance.py 2>&1 | tee -a "../$LOG_FILE"; then
        log "✅ conformance.py completed successfully."

        # Step 3: Run generate_pics_xml.py
        log "🔧 Generating XML PICS files..."
        if python3 generate_pics_xml.py 2>&1 | tee -a "../$LOG_FILE"; then
            log "✅ generate_pics_xml.py completed successfully."
            log "🎉 All scripts finished without errors."
        else
            log "❌ generate_pics_xml.py failed."
            exit 3
        fi

    else
        log "❌ conformance.py failed."
        exit 2
    fi

else
    log "❌ pics_xml_datas.py failed. Aborting."
    exit 1
fi
