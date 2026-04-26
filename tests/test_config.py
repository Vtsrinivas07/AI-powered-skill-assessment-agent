"""
Unit tests for configuration management.

Tests the Config class methods for reading environment variables,
validation, and default values.

Validates Requirements: 7.2, 8.6
"""

import os
import pytest
from config import Config


class TestConfigGetGeminiApiKey:
    """Tests for Config.get_gemini_api_key()"""
    
    def test_get_gemini_api_key_success(self, monkeypatch):
        """Test successful retrieval of API key."""
        monkeypatch.setenv("GEMINI_API_KEY", "test_api_key_12345")
        
        api_key = Config.get_gemini_api_key()
        
        assert api_key == "test_api_key_12345"
    
    def test_get_gemini_api_key_strips_whitespace(self, monkeypatch):
        """Test that API key is stripped of whitespace."""
        monkeypatch.setenv("GEMINI_API_KEY", "  test_api_key_12345  ")
        
        api_key = Config.get_gemini_api_key()
        
        assert api_key == "test_api_key_12345"
    
    def test_get_gemini_api_key_not_set(self, monkeypatch):
        """Test that ValueError is raised when API key is not set."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        
        with pytest.raises(ValueError) as exc_info:
            Config.get_gemini_api_key()
        
        assert "GEMINI_API_KEY environment variable not set" in str(exc_info.value)
    
    def test_get_gemini_api_key_placeholder_value(self, monkeypatch):
        """Test that ValueError is raised when API key is the placeholder."""
        monkeypatch.setenv("GEMINI_API_KEY", "your_api_key_here")
        
        with pytest.raises(ValueError) as exc_info:
            Config.get_gemini_api_key()
        
        assert "placeholder value" in str(exc_info.value)


class TestConfigGetApiTimeout:
    """Tests for Config.get_api_timeout()"""
    
    def test_get_api_timeout_default(self, monkeypatch):
        """Test default timeout value when not set."""
        monkeypatch.delenv("API_TIMEOUT", raising=False)
        
        timeout = Config.get_api_timeout()
        
        assert timeout == 30
    
    def test_get_api_timeout_custom_value(self, monkeypatch):
        """Test custom timeout value."""
        monkeypatch.setenv("API_TIMEOUT", "60")
        
        timeout = Config.get_api_timeout()
        
        assert timeout == 60
    
    def test_get_api_timeout_invalid_string(self, monkeypatch):
        """Test that invalid string returns default value."""
        monkeypatch.setenv("API_TIMEOUT", "not_a_number")
        
        timeout = Config.get_api_timeout()
        
        assert timeout == 30
    
    def test_get_api_timeout_negative_value(self, monkeypatch):
        """Test that negative value returns default."""
        monkeypatch.setenv("API_TIMEOUT", "-10")
        
        timeout = Config.get_api_timeout()
        
        assert timeout == 30
    
    def test_get_api_timeout_zero_value(self, monkeypatch):
        """Test that zero value returns default."""
        monkeypatch.setenv("API_TIMEOUT", "0")
        
        timeout = Config.get_api_timeout()
        
        assert timeout == 30


class TestConfigValidateRequiredEnvVars:
    """Tests for Config.validate_required_env_vars()"""
    
    def test_validate_required_env_vars_success(self, monkeypatch):
        """Test successful validation when all required vars are set."""
        monkeypatch.setenv("GEMINI_API_KEY", "test_api_key_12345")
        
        # Should not raise any exception
        Config.validate_required_env_vars()
    
    def test_validate_required_env_vars_missing_api_key(self, monkeypatch):
        """Test validation fails when API key is missing."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        
        with pytest.raises(ValueError) as exc_info:
            Config.validate_required_env_vars()
        
        assert "GEMINI_API_KEY" in str(exc_info.value)


class TestConfigGetMaxRetries:
    """Tests for Config.get_max_retries()"""
    
    def test_get_max_retries_default(self, monkeypatch):
        """Test default max retries value."""
        monkeypatch.delenv("MAX_RETRIES", raising=False)
        
        retries = Config.get_max_retries()
        
        assert retries == 3
    
    def test_get_max_retries_custom_value(self, monkeypatch):
        """Test custom max retries value."""
        monkeypatch.setenv("MAX_RETRIES", "5")
        
        retries = Config.get_max_retries()
        
        assert retries == 5
    
    def test_get_max_retries_invalid_string(self, monkeypatch):
        """Test that invalid string returns default."""
        monkeypatch.setenv("MAX_RETRIES", "invalid")
        
        retries = Config.get_max_retries()
        
        assert retries == 3
    
    def test_get_max_retries_negative_value(self, monkeypatch):
        """Test that negative value returns default."""
        monkeypatch.setenv("MAX_RETRIES", "-1")
        
        retries = Config.get_max_retries()
        
        assert retries == 3
    
    def test_get_max_retries_zero_value(self, monkeypatch):
        """Test that zero value is accepted."""
        monkeypatch.setenv("MAX_RETRIES", "0")
        
        retries = Config.get_max_retries()
        
        assert retries == 0


class TestConfigGetOutputDirectory:
    """Tests for Config.get_output_directory()"""
    
    def test_get_output_directory_default(self, monkeypatch):
        """Test default output directory."""
        monkeypatch.delenv("OUTPUT_DIR", raising=False)
        
        output_dir = Config.get_output_directory()
        
        assert output_dir == "outputs"
    
    def test_get_output_directory_custom_value(self, monkeypatch):
        """Test custom output directory."""
        monkeypatch.setenv("OUTPUT_DIR", "custom_outputs")
        
        output_dir = Config.get_output_directory()
        
        assert output_dir == "custom_outputs"
