"""
Configuration management for the Skill Assessment Agent.

This module handles all environment variable configuration including API keys,
timeouts, and other application settings. It provides validation for required
environment variables and sensible defaults for optional ones.

Validates Requirements: 7.2, 8.6
"""

import os
from typing import Optional


class Config:
    """
    Application configuration manager.
    
    This class provides static methods to access configuration values from
    environment variables with proper validation and default values.
    """
    
    @staticmethod
    def get_gemini_api_key() -> str:
        """
        Get Gemini API key from environment.
        
        Returns:
            str: The Gemini API key
            
        Raises:
            ValueError: If GEMINI_API_KEY environment variable is not set
            
        Example:
            >>> api_key = Config.get_gemini_api_key()
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable not set. "
                "Please set it before running the application. "
                "You can copy .env.example to .env and add your API key."
            )
        
        # Validate that the API key is not the placeholder value
        if api_key.strip() == "your_api_key_here":
            raise ValueError(
                "GEMINI_API_KEY is set to the placeholder value. "
                "Please replace it with your actual API key."
            )
        
        return api_key.strip()
    
    @staticmethod
    def get_api_timeout() -> int:
        """
        Get API timeout in seconds.
        
        Returns:
            int: API timeout in seconds (default: 30)
            
        Example:
            >>> timeout = Config.get_api_timeout()
            >>> print(timeout)
            30
        """
        timeout_str = os.getenv("API_TIMEOUT", "30")
        
        try:
            timeout = int(timeout_str)
            if timeout <= 0:
                raise ValueError("API_TIMEOUT must be a positive integer")
            return timeout
        except ValueError as e:
            # If conversion fails or value is invalid, return default
            return 30
    
    @staticmethod
    def validate_required_env_vars() -> None:
        """
        Validate that all required environment variables are set.
        
        This method should be called at application startup to ensure
        all necessary configuration is present before proceeding.
        
        Raises:
            ValueError: If any required environment variable is missing or invalid
            
        Example:
            >>> Config.validate_required_env_vars()
        """
        # Validate API key (this will raise ValueError if not set)
        Config.get_gemini_api_key()
        
        # Validate timeout (this will use default if not set, but we check it's valid)
        Config.get_api_timeout()
    
    @staticmethod
    def get_max_retries() -> int:
        """
        Get maximum number of API retry attempts.
        
        Returns:
            int: Maximum retry attempts (default: 3)
            
        Example:
            >>> retries = Config.get_max_retries()
            >>> print(retries)
            3
        """
        retries_str = os.getenv("MAX_RETRIES", "3")
        
        try:
            retries = int(retries_str)
            if retries < 0:
                return 3
            return retries
        except ValueError:
            return 3
    
    @staticmethod
    def get_output_directory() -> str:
        """
        Get output directory for generated reports.
        
        Returns:
            str: Path to output directory (default: "outputs")
            
        Example:
            >>> output_dir = Config.get_output_directory()
            >>> print(output_dir)
            outputs
        """
        return os.getenv("OUTPUT_DIR", "outputs")
