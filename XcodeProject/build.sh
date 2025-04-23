#!/bin/bash

echo "Syncing source files..."
cd ..
./sync_source_to_xcode.sh

echo "Building TranslationAssistant..."
cd XcodeProject

# Set directories
APP_NAME="TranslationAssistant"
BUILD_DIR="build"
SRC_DIR="TranslationAssistant"

# Create build directory
mkdir -p "$BUILD_DIR"

# Compile Swift files
swiftc -o "$BUILD_DIR/$APP_NAME" \
    "$SRC_DIR/TranslationAssistantApp.swift" \
    "$SRC_DIR/Views/"*.swift \
    "$SRC_DIR/ViewModels/"*.swift \
    "$SRC_DIR/Services/"*.swift

if [ $? -eq 0 ]; then
    echo "Build succeeded!"
    echo "To run the app: $BUILD_DIR/$APP_NAME"
else
    echo "Build failed!"
fi
