# Creating Xcode Project for TranslationAssistant

Follow these steps to create a new Xcode project and import the files:

## Step 1: Create New Xcode Project

1. Open Xcode
2. Select "Create a new Xcode project"
3. Choose "macOS" and "App"
4. Set "Product Name" to "TranslationAssistant"
5. Make sure "SwiftUI" is selected for Interface
6. Set "Life Cycle" to "App"
7. Select your Team (if applicable)
8. Save the project in: `/Users/eprouveze/Documents/Dev/App/TranslationAssistantFinal/XcodeProject`

## Step 2: Set Up Project Structure

1. In Xcode's Project Navigator, delete the auto-generated:
   - ContentView.swift
   
2. Create folder groups:
   - Right-click on the project > New Group > "Views"
   - Right-click on the project > New Group > "ViewModels"  
   - Right-click on the project > New Group > "Services"

## Step 3: Add Source Files

1. Add Main App File:
   - Right-click on the project > "Add Files to TranslationAssistant"
   - Navigate to: `/Users/eprouveze/Documents/Dev/App/TranslationAssistantFinal/Sources`
   - Select "TranslationAssistantApp.swift"
   - Ensure "Copy items if needed" is checked
   - Click "Add"

2. Add View Files:
   - Right-click on the "Views" group > "Add Files to TranslationAssistant"
   - Navigate to: `/Users/eprouveze/Documents/Dev/App/TranslationAssistantFinal/Sources/Views`
   - Select all .swift files
   - Ensure "Copy items if needed" is checked
   - Click "Add"

3. Add ViewModel Files:
   - Right-click on the "ViewModels" group > "Add Files to TranslationAssistant"
   - Navigate to: `/Users/eprouveze/Documents/Dev/App/TranslationAssistantFinal/Sources/ViewModels`
   - Select all .swift files
   - Ensure "Copy items if needed" is checked
   - Click "Add"

4. Add Service Files:
   - Right-click on the "Services" group > "Add Files to TranslationAssistant"
   - Navigate to: `/Users/eprouveze/Documents/Dev/App/TranslationAssistantFinal/Sources/Services`
   - Select all .swift files
   - Ensure "Copy items if needed" is checked
   - Click "Add"

## Step 4: Add Assets

1. In the Assets.xcassets folder:
   - Right-click and select "New Folder"
   - Name it "Colors"
   - Right-click on "Colors" and select "New Color Set"
   - Name it "Background"
   - For Light Mode: Set color to #F5F5F5 (approximately)
   - For Dark Mode: Click the "+" next to Appearances, select "Dark Appearance", set color to #262626 (approximately)

## Step 5: Build and Run

1. Select "Product" > "Clean Build Folder" (Shift+Command+K)
2. Click the Run button (▶️) or press Command+R

## Troubleshooting

If you encounter any errors:
1. Check the Console (View > Debug Area > Activate Console)
2. Make sure there are no duplicate files in the project
3. Verify the file paths in import statements match your project structure