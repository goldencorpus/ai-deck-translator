APP_NAME = TranslationAssistant
BUILD_DIR = build

.PHONY: all clean build run

all: build

build:
	@mkdir -p $(BUILD_DIR)
	@swiftc -o $(BUILD_DIR)/$(APP_NAME) TranslationAssistant/*.swift TranslationAssistant/Views/*.swift TranslationAssistant/ViewModels/*.swift TranslationAssistant/Services/*.swift

run: build
	@$(BUILD_DIR)/$(APP_NAME)

clean:
	@rm -rf $(BUILD_DIR)
