#!/bin/bash

echo "Syncing source files to XcodeProject directory..."

# Ensure the script exits if any command fails
set -e

# Define source and destination directories
SOURCE_DIR="Sources"
XCODE_DIR="XcodeProject/TranslationAssistant"

# Copy TranslationAssistantApp.swift
cp -v "$SOURCE_DIR/TranslationAssistantApp.swift" "$XCODE_DIR/"

# Ensure destination directories exist
mkdir -p "$XCODE_DIR/Services"
mkdir -p "$XCODE_DIR/ViewModels"
mkdir -p "$XCODE_DIR/Views"

# Copy Service files
cp -v "$SOURCE_DIR/Services/"*.swift "$XCODE_DIR/Services/"

# Copy ViewModel files
cp -v "$SOURCE_DIR/ViewModels/"*.swift "$XCODE_DIR/ViewModels/"

# Copy View files
cp -v "$SOURCE_DIR/Views/"*.swift "$XCODE_DIR/Views/"

echo "Sync completed successfully!"