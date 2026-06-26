#!/bin/bash
# dumper.sh - URL Extraction Utility for EDM Pipeline
# Extracts unique YouTube IDs/Links from raw text (including Google-wrapped links)

OUTPUT_FILE="links.txt"

if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    echo "Usage: ./dumper.sh [input_file] or echo '...' | ./dumper.sh"
    echo "Extracts YouTube links and appends them to $OUTPUT_FILE"
    exit 0
fi

# Handle input from file or stdin
if [ -z "$1" ]; then
    INPUT="/dev/stdin"
else
    INPUT="$1"
fi

echo "🔍 Scanning input for YouTube telemetry..."

# Regex to find YouTube IDs (v= or v%3D followed by 11 chars)
# and Playlist IDs (list= or list%3D followed by 18-34 chars)
grep -oE "(v=|v%3D)[a-zA-Z0-9_-]{11}|(list=|list%3D)[a-zA-Z0-9_-]{18,34}" "$INPUT" | \
sed -E 's/v%3D/v=/g; s/list%3D/list=/g' | \
while read -r match; do
    if [[ $match == v=* ]]; then
        echo "https://www.youtube.com/watch?$match" >> "$OUTPUT_FILE"
    elif [[ $match == list=* ]]; then
        echo "https://www.youtube.com/playlist?$match" >> "$OUTPUT_FILE"
    fi
done

# Cleanup: remove duplicates and empty lines
if [ -f "$OUTPUT_FILE" ]; then
    sort -u "$OUTPUT_FILE" -o "$OUTPUT_FILE"
    COUNT=$(wc -l < "$OUTPUT_FILE")
    echo "✅ Secured $COUNT unique links in $OUTPUT_FILE"
else
    echo "❌ No links found."
fi
