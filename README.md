# AI Deck Translator

This tool automatically translates presentations (Google Slides and PowerPoint) between different languages while preserving formatting, images, and slide structure.

## Features

- Translate entire Google Slides presentations with a single command
- Translate PowerPoint (.pptx) files while preserving formatting
- Preserve all formatting, images, and slide structure
- Support for translating text in tables and SmartArt
- Efficient content deduplication to reduce translation costs
- Progress bar with percentage completion
- Support for both CLI and Web UI interfaces
- Created copy of the original presentation rather than overwriting
- Automatic browser opening when translation completes

## Prerequisites

1. Python 3.6 or higher
2. For Google Slides: Google Cloud project with the Google Slides API and Google Drive API enabled
3. For Google Slides: OAuth 2.0 credentials for accessing Google APIs
4. Anthropic API key for Claude translation

## Installation

1. Clone this repository or download the scripts
2. Install required packages:

```bash
pip install --upgrade google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client anthropic tqdm flask python-pptx
```

3. For Google Slides, set up your Google Cloud credentials:
   - Create a project in the Google Cloud Console
   - Enable the Google Slides API and Google Drive API
   - Create OAuth 2.0 credentials and download as `credentials.json`
   - Place `credentials.json` in the same directory as the script

4. Set your Anthropic API key:
```bash
export CLAUDE_API_KEY=your_api_key_here
```

## Usage

### Command Line Interface

Run the tool with:

```bash
python run.py
```

You will be prompted to choose between translating a Google Slides presentation or a PowerPoint file.

#### For Google Slides:

```bash
python run.py --presentation-id YOUR_PRESENTATION_ID --source-lang en --target-lang ja
```

The first time you run the script, it will open a browser window for OAuth authentication with Google.

#### For PowerPoint:

```bash
python run.py --input-file your_presentation.pptx --source-lang en --target-lang ja
```

### Web Interface

To use the web interface instead:

```bash
python run.py --web
```

Then visit http://127.0.0.1:5000 in your browser.

The web interface provides:
- A form to enter your presentation details and language settings
- Real-time progress updates
- Console output display
- A direct link to the translated presentation when complete

### Additional Options

```bash
python run.py --web --port 8080 --host 0.0.0.0
```

- `--port`: Change the web server port (default: 5000)
- `--host`: Change the web server host (default: 127.0.0.1)

## How It Works

1. **Authentication**: For Google Slides, authenticates with Google using OAuth 2.0
2. **Extraction**: Extracts all text elements from the presentation
3. **Deduplication**: Identifies and groups duplicate content to reduce costs
4. **Translation**: Translates unique content in batches using Claude AI
5. **Creation/Update**: Creates a new copy of the presentation or saves to a new file
6. **Update**: Updates with translated text
7. **Open**: For Google Slides, opens the new presentation in your browser

## Optimization

- Content deduplication reduces token usage by identifying and translating unique content only
- Batched translation to efficiently manage API requests
- Progress bar for visibility into the translation process

## Privacy and Security

- Uses `anonymous_user` identifier with the Anthropic API
- Privacy notice included in the system prompt
- Custom API headers and parameters for optimal translation
- For Google Slides, credentials are stored locally in `token.json` after authentication

## Troubleshooting

- **API errors**: Make sure your Google Cloud project has the necessary APIs enabled
- **Authentication issues**: Delete `token.json` and re-authenticate
- **Translation problems**: Check your Anthropic API key is valid
- **Web UI not loading**: Ensure Flask is installed and the port is available

## License

MIT License