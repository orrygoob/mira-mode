#!/bin/bash
# used during development to copy the latest version of the custom component to HA config folder

TARGET_DIR="/Users/orrygooberman/Desktop/ha-core/config/custom_components/miramode"
SOURCE_DIR="/Users/orrygooberman/Documents/Projects/bath hacking stuff/mira-mode/ha-integration/custom_components/miramode"

# Check source exists
if [ ! -d "$SOURCE_DIR" ]; then
  echo "Error: source directory '$SOURCE_DIR' does not exist."
  exit 1
fi

# Delete target if it exists
if [ -d "$TARGET_DIR" ]; then
  echo "Deleting existing target directory: $TARGET_DIR"
  rm -rf "$TARGET_DIR"
fi

# Copy source to target
echo "Copying $SOURCE_DIR to $TARGET_DIR"
cp -r "$SOURCE_DIR" "$TARGET_DIR"

echo "Replacement complete."
