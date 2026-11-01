#!/usr/bin/env python3
"""
Unit tests for VPR components:
- clean_url
- safe_href
- is_safe_url (reject localhost, 127.0.0.1, private IPs)
- PDF validation simulation
"""
import io
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add parent path to allow imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, "vpr"))
sys.path.insert(0, os.path.join(PROJECT_DIR, "vpr", "scripts"))

from render_kanban import safe_href
from sandbox_worker import clean_url, validate_and_extract
from mcp_server import is_safe_url


class TestVprUrls(unittest.TestCase):
    def test_clean_url_arxiv_id(self):
        self.assertEqual(clean_url("2301.12345"), "https://arxiv.org/pdf/2301.12345.pdf")
        self.assertEqual(clean_url("2301.12345v2"), "https://arxiv.org/pdf/2301.12345v2.pdf")

    def test_clean_url_arxiv_link(self):
        self.assertEqual(
            clean_url("https://arxiv.org/abs/2301.12345"),
            "https://arxiv.org/pdf/2301.12345.pdf"
        )
        self.assertEqual(
            clean_url("https://arxiv.org/pdf/2301.12345.pdf"),
            "https://arxiv.org/pdf/2301.12345.pdf"
        )

    def test_clean_url_general_http(self):
        url = "https://example.com/paper.pdf"
        self.assertEqual(clean_url(url), url)
        self.assertEqual(clean_url(""), "")

    def test_safe_href(self):
        self.assertEqual(safe_href("http://example.com"), "http://example.com")
        self.assertEqual(safe_href("https://example.com/paper"), "https://example.com/paper")
        # Block dangerous or non-http(s) schemes
        self.assertEqual(safe_href("javascript:alert(1)"), "#")
        self.assertEqual(safe_href("data:text/html;base64,PHNjcmlwdD4="), "#")
        self.assertEqual(safe_href("file:///etc/passwd"), "#")
        self.assertEqual(safe_href(""), "#")
        self.assertEqual(safe_href(None), "#")


class TestIsSafeUrl(unittest.TestCase):
    def test_reject_localhost_and_loopback(self):
        self.assertFalse(is_safe_url("http://localhost:8080/test"))
        self.assertFalse(is_safe_url("http://127.0.0.1:8000/api"))
        self.assertFalse(is_safe_url("https://127.0.0.1/"))

    def test_reject_private_ips(self):
        self.assertFalse(is_safe_url("http://10.0.0.1/doc.pdf"))
        self.assertFalse(is_safe_url("http://192.168.1.1/secret"))
        self.assertFalse(is_safe_url("http://172.16.0.5:5000/"))

    def test_reject_non_http_or_unlisted_hosts(self):
        self.assertFalse(is_safe_url("ftp://example.com/doc.pdf"))
        self.assertFalse(is_safe_url("javascript:alert(1)"))
        # Non-allowed host
        self.assertFalse(is_safe_url("https://malicious-site.org/file.pdf"))

    @patch("socket.getaddrinfo")
    def test_allow_valid_public_domain(self, mock_addrinfo):
        mock_addrinfo.return_value = [
            (2, 1, 6, "", ("128.84.21.199", 443))
        ]
        self.assertTrue(is_safe_url("https://arxiv.org/pdf/2301.12345.pdf"))


class TestPdfValidation(unittest.TestCase):
    def test_missing_file(self):
        valid, reason, title, pages, score = validate_and_extract("/nonexistent/file.pdf")
        self.assertFalse(valid)
        self.assertIn("missing", reason.lower())

    def test_invalid_magic_bytes_or_small_file(self):
        test_file = "/tmp/test_invalid.pdf"
        try:
            with open(test_file, "wb") as f:
                f.write(b"NOT_A_PDF_FILE")
            valid, reason, title, pages, score = validate_and_extract(test_file)
            self.assertFalse(valid)
            self.assertTrue("small" in reason.lower() or "magic" in reason.lower())
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    @patch("sandbox_worker.PdfReader")
    def test_simulated_valid_pdf(self, mock_pdf_reader):
        test_file = "/tmp/test_simulated_valid.pdf"
        try:
            with open(test_file, "wb") as f:
                f.write(b"%PDF" + b"A" * 35000)

            # Mock PdfReader extracted text
            mock_page_1 = MagicMock()
            mock_page_1.extract_text.return_value = "Attention Is All You Need\nAshish Vaswani et al.\n" + ("Text content " * 300)
            mock_page_2 = MagicMock()
            mock_page_2.extract_text.return_value = "Second page text...\n" + ("More content " * 200)

            mock_reader_inst = MagicMock()
            mock_reader_inst.pages = [mock_page_1, mock_page_2]
            mock_pdf_reader.return_value = mock_reader_inst

            valid, reason, det_title, pages_text, score = validate_and_extract(
                test_file,
                expected_title="Attention Is All You Need"
            )
            self.assertTrue(valid)
            self.assertEqual(reason, "OK")
            self.assertEqual(det_title, "Attention Is All You Need")
            self.assertEqual(len(pages_text), 2)
            self.assertGreaterEqual(score, 0.6)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    @patch("sandbox_worker.PdfReader")
    def test_simulated_title_mismatch(self, mock_pdf_reader):
        test_file = "/tmp/test_simulated_mismatch.pdf"
        try:
            with open(test_file, "wb") as f:
                f.write(b"%PDF" + b"B" * 35000)

            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Quantum Computing Foundations\nAuthor Name\n" + ("Detailed text " * 300)
            mock_reader_inst = MagicMock()
            mock_reader_inst.pages = [mock_page]
            mock_pdf_reader.return_value = mock_reader_inst

            valid, reason, det_title, pages_text, score = validate_and_extract(
                test_file,
                expected_title="Deep Residual Learning for Image Recognition"
            )
            self.assertFalse(valid)
            self.assertIn("Title mismatch", reason)
            self.assertLess(score, 0.6)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)


if __name__ == "__main__":
    unittest.main()
