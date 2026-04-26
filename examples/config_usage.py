"""
Example script demonstrating Config class usage.

This script shows how to use the Config class to access
environment variables and validate configuration.
"""

import sys
import os

# Add parent directory to path to import config
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import Config


def main():
    """Demonstrate Config class usage."""
    
    print("=" * 60)
    print("Configuration Management Example")
    print("=" * 60)
    print()
    
    # Step 1: Validate required environment variables
    print("Step 1: Validating required environment variables...")
    try:
        Config.validate_required_env_vars()
        print("✓ All required environment variables are set")
    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        print("\nPlease set up your .env file:")
        print("  1. Copy .env.example to .env")
        print("  2. Add your GEMINI_API_KEY")
        print("  3. Run this script again")
        return 1
    
    print()
    
    # Step 2: Access configuration values
    print("Step 2: Accessing configuration values...")
    print()
    
    # Get API key (masked for security)
    api_key = Config.get_gemini_api_key()
    masked_key = api_key[:10] + "..." + api_key[-4:] if len(api_key) > 14 else "***"
    print(f"  GEMINI_API_KEY: {masked_key}")
    
    # Get API timeout
    timeout = Config.get_api_timeout()
    print(f"  API_TIMEOUT: {timeout} seconds")
    
    # Get max retries
    max_retries = Config.get_max_retries()
    print(f"  MAX_RETRIES: {max_retries}")
    
    # Get output directory
    output_dir = Config.get_output_directory()
    print(f"  OUTPUT_DIR: {output_dir}")
    
    print()
    
    # Step 3: Demonstrate usage in application code
    print("Step 3: Example usage in application code...")
    print()
    
    print("  # Initialize API client")
    print(f"  api_client = GeminiClient(")
    print(f"      api_key=Config.get_gemini_api_key(),")
    print(f"      timeout=Config.get_api_timeout()")
    print(f"  )")
    print()
    
    print("  # Configure retry logic")
    print(f"  max_retries = Config.get_max_retries()")
    print(f"  for attempt in range(max_retries):")
    print(f"      try:")
    print(f"          result = api_client.call()")
    print(f"          break")
    print(f"      except APIError:")
    print(f"          if attempt == max_retries - 1:")
    print(f"              raise")
    print()
    
    print("  # Save output to configured directory")
    print(f"  output_path = os.path.join(")
    print(f"      Config.get_output_directory(),")
    print(f"      'report.json'")
    print(f"  )")
    print(f"  save_report(output_path)")
    
    print()
    print("=" * 60)
    print("Configuration example completed successfully!")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
