# Examples

This directory contains example scripts demonstrating how to use various components of the Skill Assessment Agent.

## Available Examples

### config_usage.py

Demonstrates how to use the `Config` class for configuration management.

**Usage:**
```bash
# Set up your environment first
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Run the example
python examples/config_usage.py
```

**What it demonstrates:**
- Validating required environment variables
- Accessing configuration values
- Using Config in application code
- Error handling for missing configuration

## Running Examples

All examples can be run from the project root directory:

```bash
python examples/<example_name>.py
```

Make sure you have:
1. Installed all dependencies: `pip install -r requirements.txt`
2. Set up your `.env` file with required configuration
3. Activated your virtual environment (if using one)

## Adding New Examples

When adding new examples:
1. Create a new `.py` file in this directory
2. Add comprehensive docstrings
3. Include error handling
4. Update this README with usage instructions
5. Test the example thoroughly
