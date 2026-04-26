# Configuration Guide

## Overview

The Skill Assessment Agent uses environment variables for configuration management. This approach keeps sensitive information like API keys out of the codebase and allows for easy configuration across different environments.

## Setup

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit the `.env` file and add your configuration:**
   ```bash
   # Required: Your Google Gemini API key
   GEMINI_API_KEY=your_actual_api_key_here
   
   # Optional: API timeout in seconds (default: 30)
   API_TIMEOUT=30
   
   # Optional: Maximum retry attempts for API calls (default: 3)
   MAX_RETRIES=3
   
   # Optional: Output directory for reports (default: outputs)
   OUTPUT_DIR=outputs
   ```

3. **Get a Gemini API Key:**
   - Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Sign in with your Google account
   - Create a new API key
   - Copy the key to your `.env` file

## Configuration Options

### Required Variables

#### `GEMINI_API_KEY`
- **Description:** Your Google Gemini API key for LLM operations
- **Required:** Yes
- **Default:** None
- **Example:** `GEMINI_API_KEY=AIzaSyD...`

### Optional Variables

#### `API_TIMEOUT`
- **Description:** Timeout for API requests in seconds
- **Required:** No
- **Default:** 30
- **Valid Values:** Positive integers
- **Example:** `API_TIMEOUT=60`

#### `MAX_RETRIES`
- **Description:** Maximum number of retry attempts for failed API calls
- **Required:** No
- **Default:** 3
- **Valid Values:** Non-negative integers (0 to disable retries)
- **Example:** `MAX_RETRIES=5`

#### `OUTPUT_DIR`
- **Description:** Directory where generated reports will be saved
- **Required:** No
- **Default:** `outputs`
- **Example:** `OUTPUT_DIR=custom_reports`

## Usage in Code

### Basic Usage

```python
from config import Config

# Get API key
api_key = Config.get_gemini_api_key()

# Get timeout
timeout = Config.get_api_timeout()

# Get max retries
max_retries = Config.get_max_retries()

# Get output directory
output_dir = Config.get_output_directory()
```

### Validation

Validate all required environment variables at application startup:

```python
from config import Config

try:
    Config.validate_required_env_vars()
    print("✓ Configuration validated successfully")
except ValueError as e:
    print(f"✗ Configuration error: {e}")
    exit(1)
```

## Error Handling

The Config class provides helpful error messages:

### Missing API Key
```
ValueError: GEMINI_API_KEY environment variable not set. 
Please set it before running the application. 
You can copy .env.example to .env and add your API key.
```

### Placeholder API Key
```
ValueError: GEMINI_API_KEY is set to the placeholder value. 
Please replace it with your actual API key.
```

### Invalid Timeout
If `API_TIMEOUT` is set to an invalid value (non-numeric, negative, or zero), the default value of 30 seconds will be used automatically.

### Invalid Max Retries
If `MAX_RETRIES` is set to an invalid value (non-numeric or negative), the default value of 3 will be used automatically.

## Security Best Practices

1. **Never commit `.env` files:** The `.env` file is in `.gitignore` to prevent accidental commits
2. **Use environment-specific files:** Create separate `.env.development`, `.env.production` files if needed
3. **Rotate API keys regularly:** Change your API keys periodically for security
4. **Limit API key permissions:** Use API keys with minimal required permissions
5. **Monitor API usage:** Keep track of your API usage to detect unauthorized access

## Troubleshooting

### "GEMINI_API_KEY environment variable not set"
- Ensure you've created a `.env` file in the project root
- Verify the file contains `GEMINI_API_KEY=your_key`
- Check that you're running the application from the project root directory

### "GEMINI_API_KEY is set to the placeholder value"
- Replace `your_api_key_here` with your actual API key from Google AI Studio

### API calls timing out
- Increase `API_TIMEOUT` value in your `.env` file
- Check your internet connection
- Verify the Gemini API service is operational

### API rate limits
- Adjust `MAX_RETRIES` to allow more retry attempts
- Implement exponential backoff in your code
- Consider upgrading your API tier if needed

## Testing

The configuration module includes comprehensive unit tests. Run them with:

```bash
pytest tests/test_config.py -v
```

All tests use `monkeypatch` to safely test environment variable handling without affecting your actual environment.

## Related Documentation

- [Google Gemini API Documentation](https://ai.google.dev/docs)
- [Environment Variables Best Practices](https://12factor.net/config)
- [Python-dotenv Documentation](https://github.com/theskumar/python-dotenv)
