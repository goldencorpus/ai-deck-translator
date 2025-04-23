# TranslationAssistant - Clean Build

This is a clean build of the TranslationAssistant project created to avoid duplicate file issues.

## Opening in Xcode

1. Double-click the TranslationAssistant.xcodeproj file to open in Xcode
2. Click on the project in the navigator to configure build settings
3. Make sure the target is set as a macOS application

## Project Structure

- Sources/
  - TranslationAssistantApp.swift (main app file)
  - Views/ (all view files)
  - ViewModels/ (view model files)
  - Services/ (service files)
- Resources/
  - Assets.xcassets (including Colors)

## If you still have issues

- Check for any duplicate file references in Xcode
- Clean the build folder (Product > Clean Build Folder)
- Delete derived data (~/Library/Developer/Xcode/DerivedData)
- Restart Xcode

