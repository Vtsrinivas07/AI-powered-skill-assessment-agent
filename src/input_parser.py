"""
Input parser for the Skill Assessment Agent.

This module handles parsing and validation of job descriptions and resumes
in both text and PDF formats.

Validates Requirements: 1.1, 1.2, 1.5, 1.6
"""

import re
from pathlib import Path
from typing import Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from src.models import ParsedDocument
from src.exceptions import InvalidFileError, UnsupportedFormatError, ValidationError


class InputParser:
    """
    Parser for job descriptions and resumes in text or PDF format.
    
    This class handles document parsing, text extraction from PDFs,
    content validation, and text normalization.
    """
    
    def __init__(self):
        """Initialize the InputParser."""
        if pdfplumber is None:
            raise ImportError(
                "pdfplumber is required for PDF parsing. "
                "Install it with: pip install pdfplumber"
            )
    
    def parse_document(self, file_path: str) -> ParsedDocument:
        """
        Parse a document from file path.
        
        Args:
            file_path: Path to text or PDF file
            
        Returns:
            ParsedDocument with extracted text and metadata
            
        Raises:
            InvalidFileError: If file is corrupted or unreadable
            UnsupportedFormatError: If file format is not supported
            ValidationError: If content fails validation
        """
        path = Path(file_path)
        
        # Check if file exists
        if not path.exists():
            raise InvalidFileError(f"File not found: {file_path}")
        
        # Check if file is readable
        if not path.is_file():
            raise InvalidFileError(f"Path is not a file: {file_path}")
        
        # Determine file type and extract content
        file_extension = path.suffix.lower()
        
        if file_extension == '.pdf':
            content, page_count = self._extract_pdf_text(str(path))
            file_type = "pdf"
        elif file_extension in ['.txt', '.text']:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                page_count = None
                file_type = "text"
            except UnicodeDecodeError:
                # Try with different encoding
                try:
                    with open(path, 'r', encoding='latin-1') as f:
                        content = f.read()
                    page_count = None
                    file_type = "text"
                except Exception as e:
                    raise InvalidFileError(f"Unable to read text file: {e}")
            except Exception as e:
                raise InvalidFileError(f"Error reading file: {e}")
        else:
            raise UnsupportedFormatError(
                f"Unsupported file format: {file_extension}. "
                "Supported formats: .pdf, .txt, .text"
            )
        
        # Clean the extracted text
        content = self._clean_text(content)
        
        # Validate content
        if not self.validate_content(content):
            raise ValidationError(
                "Document content is empty or contains no parseable text"
            )
        
        # Create metadata
        metadata = {
            "file_name": path.name,
            "file_size": str(path.stat().st_size),
            "file_extension": file_extension
        }
        
        return ParsedDocument(
            content=content,
            file_path=str(path),
            file_type=file_type,
            page_count=page_count,
            metadata=metadata
        )
    
    def validate_content(self, content: str) -> bool:
        """
        Validate that content contains parseable text.
        
        Args:
            content: Text content to validate
            
        Returns:
            True if content is valid, False otherwise
        """
        if not content:
            return False
        
        # Check if content is only whitespace
        if not content.strip():
            return False
        
        # Check if content has at least some readable characters
        # (at least 10 alphanumeric characters)
        alphanumeric_count = sum(c.isalnum() for c in content)
        if alphanumeric_count < 10:
            return False
        
        return True
    
    def _extract_pdf_text(self, file_path: str) -> tuple[str, int]:
        """
        Extract text from PDF file using pdfplumber.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Tuple of (extracted_text, page_count)
            
        Raises:
            InvalidFileError: If PDF is corrupted or unreadable
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                
                if page_count == 0:
                    raise InvalidFileError("PDF file contains no pages")
                
                # Extract text from all pages
                text_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                
                # Combine all pages
                full_text = "\n\n".join(text_parts)
                
                if not full_text.strip():
                    raise InvalidFileError(
                        "PDF file contains no extractable text. "
                        "It may be an image-based PDF or corrupted."
                    )
                
                return full_text, page_count
                
        except pdfplumber.pdfminer.pdfparser.PDFSyntaxError as e:
            raise InvalidFileError(f"Corrupted PDF file: {e}")
        except Exception as e:
            raise InvalidFileError(f"Error reading PDF file: {e}")
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text content.
        
        This method removes artifacts, normalizes whitespace, and ensures
        consistent formatting.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned and normalized text
        """
        if not text:
            return ""
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Normalize line endings to \n FIRST (before removing control chars)
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove other control characters except newlines and tabs
        text = ''.join(char for char in text if char.isprintable() or char in '\n\t')
        
        # Remove excessive blank lines (more than 2 consecutive newlines)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Normalize whitespace within lines (but preserve line breaks)
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            # Replace multiple spaces/tabs with single space
            cleaned_line = re.sub(r'[ \t]+', ' ', line)
            # Strip leading/trailing whitespace from each line
            cleaned_line = cleaned_line.strip()
            cleaned_lines.append(cleaned_line)
        
        text = '\n'.join(cleaned_lines)
        
        # Remove leading/trailing whitespace from entire text
        text = text.strip()
        
        return text
