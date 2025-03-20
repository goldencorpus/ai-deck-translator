# Unified Translation Architecture

## Overview

The AI Deck Translator uses a unified architecture to provide consistent translation capabilities across different document types (Google Slides and PowerPoint files). This architecture ensures translations maintain the same quality standards, glossary usage, and cost tracking regardless of the source format.

## Key Components

### 1. Translation Interface

The core of the unified architecture is the `TranslationInterface` module, which defines the abstract interfaces implemented by all translation services:

- **TranslationService**: Abstract interface for translation operations
- **DocumentAdapter**: Interface for document-specific operations (extraction and updating)
- **TranslationRequest**: Data class encapsulating translation parameters
- **TranslationResult**: Data class containing translation results and metrics

This interface design allows the system to handle different document types with consistent behavior.

### 2. Shared Utilities

Common functionality is extracted into shared utility modules to ensure consistent behavior:

- **JSON Processing**: Functions to handle and repair JSON from API responses
- **Quality Checks**: Standardized quality assessment for translations
- **Glossary Management**: Consistent terminology across all translations
- **Cost Calculation**: Unified approach to tracking and reporting translation costs

### 3. Base Implementation

A `BaseTranslationService` provides common functionality to reduce code duplication:

- Document processing flow
- Error handling and recovery
- Quality assurance pipeline
- Cost tracking and reporting

Concrete implementations only need to provide model-specific translation logic.

### 4. Document Adapters

Format-specific adapters handle the unique requirements of each document type:

- **PPTXAdapter**: Extracts text from and updates PowerPoint files
- **GoogleSlidesAdapter**: Interfaces with Google Slides API

These adapters conform to the DocumentAdapter interface, making them interchangeable from the translation service's perspective.

## Architecture Diagram

```
┌─────────────────────────────────────────┐
│            Client Application            │
└───────────────────┬─────────────────────┘
                    │
┌───────────────────▼─────────────────────┐
│          Translation Interface           │
│                                          │
│  ┌─────────────┐      ┌───────────────┐  │
│  │Translation- │      │  Document-    │  │
│  │  Service    │      │   Adapter     │  │
│  └─────────────┘      └───────────────┘  │
└───────────────────┬─────────────────────┘
                    │
┌───────────────────▼─────────────────────┐
│       BaseTranslationService             │
└───────────┬───────────────────┬─────────┘
            │                   │
┌───────────▼────────┐  ┌───────▼─────────┐
│ EnhancedPPTX-      │  │ GoogleSlides-   │
│ TranslationService │  │TranslationService│
└────────────────────┘  └─────────────────┘
            │                   │
┌───────────▼────────┐  ┌───────▼─────────┐
│   PPTX Adapter     │  │ GoogleSlides    │
│                    │  │    Adapter      │
└────────────────────┘  └─────────────────┘
```

## Workflow

1. The client application creates a translation request specifying document type, source and target languages, and quality parameters
2. The appropriate translation service and document adapter are instantiated
3. The document adapter extracts text elements and metadata from the source document
4. The translation service processes the text, applying quality checks and glossary terms
5. Translated text is given back to the document adapter to update the document
6. The translation service returns results including metrics and the location of the translated document

## Quality Management

All translations undergo the same quality management process:

1. **Pre-Translation**: Apply glossary terms and context-aware prompting
2. **Translation**: Use appropriate models based on quality level and content type
3. **Post-Translation QA**: Check for issues with formatting, placeholders, and terminology
4. **Repair**: Automatically fix identified issues when possible

## Extending the Architecture

To add support for a new document type:

1. Create a new document adapter implementing the DocumentAdapter interface
2. Implement extraction and update methods specific to the document type
3. Optionally create a specialized translation service if needed
4. Register the new adapter in the application

To add support for a new translation model:

1. Implement the model-specific translation logic
2. Add the model to the appropriate quality levels
3. Update cost calculations for the new model

## Benefits of Unified Architecture

1. **Consistency**: Same translation quality and terminology across all document types
2. **Maintainability**: Common code is shared, reducing duplication
3. **Extensibility**: Easy to add support for new document types or translation models
4. **Reliability**: Standardized error handling and recovery mechanisms
5. **Transparency**: Uniform cost tracking and reporting

## Configuration

Translation services and adapters can be configured through the application's configuration system, allowing customization of:

- Default quality levels
- Model selection for different content types
- Batch sizes and parallelization options
- Caching behavior
- Glossary usage 