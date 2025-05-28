# Google Cloud Text-to-Speech Setup Guide

This guide will help you set up Google Cloud Text-to-Speech for European Portuguese in your language learning app.

## Prerequisites

1. A Google Cloud Platform (GCP) account
2. A GCP project with billing enabled
3. The language learning app already running
4. Poetry installed for dependency management (for local development)

## Installation

If you haven't already installed the TTS dependencies:

### For Local Development (Poetry)
```bash
poetry add google-cloud-texttospeech
# or if you've already updated pyproject.toml:
poetry install
```

### For Production (Railway)
The `requirements.txt` file already includes the necessary dependency.

## Step 1: Enable the Text-to-Speech API

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (or create a new one)
3. Navigate to **APIs & Services** > **Library**
4. Search for "Cloud Text-to-Speech API"
5. Click on it and press **Enable**

## Step 2: Create a Service Account

1. Go to **IAM & Admin** > **Service Accounts**
2. Click **Create Service Account**
3. Fill in the details:
   - **Service account name**: `langtut-tts`
   - **Description**: `Text-to-Speech service for language learning app`
4. Click **Create and Continue**
5. Grant the role: **Cloud Text-to-Speech User**
6. Click **Continue** and then **Done**

## Step 3: Generate Service Account Key

1. Find your newly created service account in the list
2. Click on it to open the details
3. Go to the **Keys** tab
4. Click **Add Key** > **Create new key**
5. Choose **JSON** format
6. Click **Create**
7. The key file will be downloaded automatically

## Step 4: Configure Your Application

### For Local Development

1. Rename the downloaded JSON file to `google-cloud-service-account.json`
2. Place it in the root directory of your project (same level as `app.py`)
3. Make sure this file is listed in your `.gitignore` (it should be already)

### For Production (Railway/Heroku)

1. Open the downloaded JSON file in a text editor
2. Copy the entire JSON content
3. In your deployment platform, set the environment variable:
   - **Variable name**: `LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON`
   - **Value**: The entire JSON content (as a single line)

## Step 5: Test the Setup

1. Start your application
2. Navigate to a feedback page after answering a card
3. You should see TTS controls (Listen, Word, Example buttons)
4. Click any of these buttons to test the audio generation

## Available Portuguese Voices

The app is configured to use European Portuguese (`pt-PT`) with these available voices:

- `pt-PT-Standard-A` (Female) - Default
- `pt-PT-Standard-B` (Male)
- `pt-PT-Standard-C` (Male)
- `pt-PT-Standard-D` (Female)
- `pt-PT-Wavenet-A` (Female) - Higher quality, more expensive
- `pt-PT-Wavenet-B` (Male) - Higher quality, more expensive
- `pt-PT-Wavenet-C` (Female) - Higher quality, more expensive
- `pt-PT-Wavenet-D` (Male) - Higher quality, more expensive

## Configuration Options

You can customize the TTS behavior in `settings.toml`:

```toml
# Enable/disable TTS functionality
TTS_ENABLED = true

# Language code for European Portuguese
TTS_LANGUAGE_CODE = "pt-PT"

# Voice name (see available voices above)
TTS_VOICE_NAME = "pt-PT-Standard-A"

# Audio format (MP3, LINEAR16, OGG_OPUS)
TTS_AUDIO_ENCODING = "MP3"
```

## Pricing Information

Google Cloud Text-to-Speech pricing (as of 2024):

- **Standard voices**: $4.00 per 1 million characters
- **WaveNet voices**: $16.00 per 1 million characters
- **First 1 million characters per month are free**

For a typical language learning session:
- Average word: ~6 characters
- Average example: ~30 characters
- Cost per card: ~$0.000144 (with standard voices)
- 1000 cards: ~$0.14

## Troubleshooting

### TTS buttons don't appear
- Check browser console for errors
- Verify the service account has the correct permissions
- Ensure the Text-to-Speech API is enabled

### "TTS service is not available" error
- Check that the service account JSON is correctly configured
- Verify your GCP project has billing enabled
- Check the application logs for detailed error messages

### Audio doesn't play
- Check browser permissions for audio playback
- Try a different browser
- Verify the audio format is supported

## Security Notes

1. **Never commit service account keys to version control**
2. **Use environment variables for production deployments**
3. **Regularly rotate service account keys**
4. **Monitor usage to avoid unexpected charges**

## API Endpoints

The app provides these TTS endpoints:

- `GET /api/tts/status` - Check TTS availability and voices
- `POST /api/tts/speak` - Generate speech for arbitrary text
- `POST /api/tts/speak-card` - Generate speech for card content

## Features

- **Automatic caching**: Audio is cached to reduce API calls
- **Autoplay**: Audio plays automatically when feedback is shown
- **Manual controls**: Separate buttons for word and example
- **Graceful degradation**: App works without TTS if not configured
- **Loading states**: Visual feedback during audio generation 