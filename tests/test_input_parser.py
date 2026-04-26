"""
Unit tests for the InputParser class.

Tests cover text and PDF parsing, validation, error handling,
and text cleaning functionality.

Validates Requirements: 1.1, 1.2, 1.5, 1.6
"""

import pytest
from pathlib import Path
import tempfile
import os

from src.input_parser import InputParser
from src.models import ParsedDocument
from src.exceptions import InvalidFileError, UnsupportedFormatError, ValidationError


class TestInputParser:
    """Test suite for InputParser class."""
    
    @pytest.fixture
    def parser(self):
        """Create an InputParser instance for testing."""
        return InputParser()
    
    @pytest.fixture
    def temp_text_file(self):
        """Create a temporary text file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("Job Title: Software Engineer\n")
            f.write("Required Skills: Python, FastAPI, PostgreSQL\n")
            f.write("Experience: 3+ years\n")
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def temp_empty_file(self):
        """Create a temporary empty text file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def temp_whitespace_file(self):
        """Create a temporary file with only whitespace."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("   \n\t\n   ")
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    # ========================================================================
    # Test parse_document() with text files
    # ========================================================================
    
    def test_parse_text_file_success(self, parser, temp_text_file):
        """Test successful parsing of a text file."""
        result = parser.parse_document(temp_text_file)
        
        assert isinstance(result, ParsedDocument)
        assert result.file_type == "text"
        assert "Software Engineer" in result.content
        assert "Python" in result.content
        assert result.page_count is None
        assert result.metadata is not None
        assert "file_name" in result.metadata
    
    def test_parse_nonexistent_file(self, parser):
        """Test parsing a file that doesn't exist."""
        with pytest.raises(InvalidFileError, match="File not found"):
            parser.parse_document("nonexistent_file.txt")
    
    def test_parse_unsupported_format(self, parser):
        """Test parsing a file with unsupported format."""
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
            temp_path = f.name
        
        try:
            with pytest.raises(UnsupportedFormatError, match="Unsupported file format"):
                parser.parse_document(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_parse_empty_file_raises_validation_error(self, parser, temp_empty_file):
        """Test that parsing an empty file raises ValidationError."""
        with pytest.raises(ValidationError, match="empty or contains no parseable text"):
            parser.parse_document(temp_empty_file)
    
    def test_parse_whitespace_only_file_raises_validation_error(self, parser, temp_whitespace_file):
        """Test that parsing a whitespace-only file raises ValidationError."""
        with pytest.raises(ValidationError, match="empty or contains no parseable text"):
            parser.parse_document(temp_whitespace_file)
    
    # ========================================================================
    # Test validate_content()
    # ========================================================================
    
    def test_validate_content_empty_string(self, parser):
        """Test that empty strings fail validation."""
        assert not parser.validate_content("")
    
    def test_validate_content_whitespace_only(self, parser):
        """Test that whitespace-only strings fail validation."""
        assert not parser.validate_content("   ")
        assert not parser.validate_content("\n\t  \n")
        assert not parser.validate_content("\t\t\t")
    
    def test_validate_content_too_few_characters(self, parser):
        """Test that strings with too few alphanumeric characters fail validation."""
        assert not parser.validate_content("abc")  # Only 3 characters
        assert not parser.validate_content("!@#$%^&*()")  # No alphanumeric
    
    def test_validate_content_valid_content(self, parser):
        """Test that valid content passes validation."""
        assert parser.validate_content("This is valid content")
        assert parser.validate_content("Job Title: Software Engineer")
        assert parser.validate_content("Python Developer with 5 years experience")
    
    def test_validate_content_minimum_threshold(self, parser):
        """Test content at the minimum threshold (10 alphanumeric characters)."""
        assert parser.validate_content("1234567890")  # Exactly 10
        assert parser.validate_content("abcdefghij")  # Exactly 10
        assert parser.validate_content("Test 123456")  # Exactly 10 (space doesn't count)
        assert not parser.validate_content("Test 1234")  # Only 9
    
    # ========================================================================
    # Test _clean_text()
    # ========================================================================
    
    def test_clean_text_empty_string(self, parser):
        """Test cleaning an empty string."""
        assert parser._clean_text("") == ""
    
    def test_clean_text_removes_null_bytes(self, parser):
        """Test that null bytes are removed."""
        text = "Hello\x00World"
        cleaned = parser._clean_text(text)
        assert "\x00" not in cleaned
        assert "HelloWorld" in cleaned
    
    def test_clean_text_normalizes_line_endings(self, parser):
        """Test that line endings are normalized to \\n."""
        text = "Line1\r\nLine2\rLine3\nLine4"
        cleaned = parser._clean_text(text)
        assert "\r\n" not in cleaned
        assert "\r" not in cleaned
        assert cleaned == "Line1\nLine2\nLine3\nLine4"
    
    def test_clean_text_removes_excessive_blank_lines(self, parser):
        """Test that excessive blank lines are reduced."""
        text = "Line1\n\n\n\n\nLine2"
        cleaned = parser._clean_text(text)
        assert cleaned == "Line1\n\nLine2"
    
    def test_clean_text_normalizes_whitespace(self, parser):
        """Test that multiple spaces/tabs are normalized."""
        text = "Hello    World\t\tTest"
        cleaned = parser._clean_text(text)
        assert cleaned == "Hello World Test"
    
    def test_clean_text_strips_leading_trailing_whitespace(self, parser):
        """Test that leading/trailing whitespace is removed."""
        text = "  \n  Hello World  \n  "
        cleaned = parser._clean_text(text)
        assert cleaned == "Hello World"
    
    def test_clean_text_preserves_line_breaks(self, parser):
        """Test that intentional line breaks are preserved."""
        text = "Line 1\nLine 2\nLine 3"
        cleaned = parser._clean_text(text)
        assert cleaned == "Line 1\nLine 2\nLine 3"
    
    def test_clean_text_complex_example(self, parser):
        """Test cleaning a complex text with multiple issues."""
        text = "  \n\n  Job Title:   Software Engineer  \n\n\n\n  Skills: Python,    FastAPI  \n  "
        cleaned = parser._clean_text(text)
        expected = "Job Title: Software Engineer\n\nSkills: Python, FastAPI"
        assert cleaned == expected
    
    # ========================================================================
    # Test PDF parsing (using sample files if available)
    # ========================================================================
    
    def test_parse_pdf_file_not_found(self, parser):
        """Test parsing a PDF file that doesn't exist."""
        with pytest.raises(InvalidFileError, match="File not found"):
            parser.parse_document("nonexistent.pdf")
    
    # Note: Testing actual PDF parsing requires sample PDF files
    # These tests would be added once sample PDFs are available
    
    # ========================================================================
    # Test metadata extraction
    # ========================================================================
    
    def test_metadata_contains_required_fields(self, parser, temp_text_file):
        """Test that metadata contains all required fields."""
        result = parser.parse_document(temp_text_file)
        
        assert result.metadata is not None
        assert "file_name" in result.metadata
        assert "file_size" in result.metadata
        assert "file_extension" in result.metadata
        assert result.metadata["file_extension"] == ".txt"
    
    # ========================================================================
    # Test edge cases
    # ========================================================================
    
    def test_parse_file_with_special_characters(self, parser):
        """Test parsing a file with special characters in content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("Skills: Python, C++, C#, Node.js\n")
            f.write("Email: test@example.com\n")
            f.write("Salary: $100,000-$150,000\n")
            temp_path = f.name
        
        try:
            result = parser.parse_document(temp_path)
            assert "Python" in result.content
            assert "C++" in result.content
            assert "@" in result.content
            assert "$" in result.content
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_parse_file_with_unicode_characters(self, parser):
        """Test parsing a file with Unicode characters."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("Name: José García\n")
            f.write("Skills: Python, 日本語, Русский\n")
            temp_path = f.name
        
        try:
            result = parser.parse_document(temp_path)
            assert "José" in result.content
            assert "García" in result.content
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestInputParserWithSampleFiles:
    """Test InputParser with actual sample files from the project."""
    
    @pytest.fixture
    def parser(self):
        """Create an InputParser instance for testing."""
        return InputParser()
    
    def test_parse_sample_job_description(self, parser):
        """Test parsing the sample job description file."""
        sample_path = "samples/test_jd.txt"
        
        if not os.path.exists(sample_path):
            pytest.skip("Sample job description file not found")
        
        result = parser.parse_document(sample_path)
        
        assert isinstance(result, ParsedDocument)
        assert result.file_type == "text"
        assert len(result.content) > 0
        assert result.metadata is not None
    
    def test_parse_sample_resume(self, parser):
        """Test parsing the sample resume file."""
        sample_path = "samples/test_resume.txt"
        
        if not os.path.exists(sample_path):
            pytest.skip("Sample resume file not found")
        
        result = parser.parse_document(sample_path)
        
        assert isinstance(result, ParsedDocument)
        assert result.file_type == "text"
        assert len(result.content) > 0
        assert result.metadata is not None
