#!/usr/bin/env python3
"""
BibTeX Reference Verification Tool
Verifies the authenticity of references by checking DOI links and other identifiers.
"""

import re
import time
import json
import random
import os
import sys
import threading
import queue
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from urllib.parse import urlparse
from html import unescape
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox

class ReferenceVerifier:
    """Verifies the authenticity of bibliographic references."""

    def __init__(self, timeout=10, delay_range=(1, 3)):
        """
        Initialize the verifier.

        Args:
            timeout: Request timeout in seconds
            delay_range: Tuple of (min, max) delay between requests in seconds
        """
        self.timeout = timeout
        self.delay_range = delay_range
        self.session = self._create_session()
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        self.crossref_base_url = "https://api.crossref.org/works"
        self.chrome_path = self._find_chrome_path()

    def _find_chrome_path(self):
        """Find Chrome browser executable path."""
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
        ]
        for path in paths:
            if os.path.exists(path):
                return path
        return None

    def _create_session(self):
        """Create a requests session with retry logic."""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _get_random_user_agent(self):
        """Get a random user agent string."""
        return random.choice(self.user_agents)

    def _delay(self):
        """Add a random delay between requests."""
        time.sleep(random.uniform(*self.delay_range))

    def parse_bib_file(self, filepath: str) -> List[Dict]:
        """
        Parse a BibTeX file and extract reference information.

        Args:
            filepath: Path to the .bib file

        Returns:
            List of dictionaries containing reference information
        """
        references = []

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split by entry type (@article, @inproceedings, etc.)
        entries = re.findall(r'@(\w+)\{([^@]+)', content, re.DOTALL)

        for entry_type, entry_content in entries:
            ref = {
                'type': entry_type,
                'raw': entry_content[:200]  # Store first 200 chars for reference
            }

            # Extract citation key
            key_match = re.match(r'([^,]+),', entry_content)
            if key_match:
                ref['key'] = key_match.group(1).strip()

            # Extract DOI
            doi_match = re.search(r'doi\s*=\s*\{([^}]+)\}', entry_content, re.IGNORECASE)
            if doi_match:
                doi = doi_match.group(1).strip()
                # Clean up DOI
                doi = doi.replace('https://doi.org/', '')
                doi = doi.replace('http://dx.doi.org/', '')
                ref['doi'] = doi

            # Extract URL
            url_match = re.search(r'url\s*=\s*\{([^}]+)\}', entry_content, re.IGNORECASE)
            if url_match:
                ref['url'] = url_match.group(1).strip()

            # Extract arXiv ID
            arxiv_match = re.search(r'arXiv[:\s]+(\d+\.\d+)', entry_content, re.IGNORECASE)
            if arxiv_match:
                ref['arxiv'] = arxiv_match.group(1)

            # Extract title
            title_match = re.search(r'title\s*=\s*\{([^}]+)\}', entry_content, re.IGNORECASE)
            if title_match:
                ref['title'] = title_match.group(1).strip()[:100]  # First 100 chars

            # Extract year
            year_match = re.search(r'year\s*=\s*\{([^}]+)\}', entry_content, re.IGNORECASE)
            if year_match:
                ref['year'] = year_match.group(1).strip()

            # Extract journal
            journal_match = re.search(r'journal\s*=\s*\{([^}]+)\}', entry_content, re.IGNORECASE)
            if journal_match:
                ref['journal'] = journal_match.group(1).strip()[:80]

            references.append(ref)

        return references

    def _crossref_headers(self):
        return {
            'User-Agent': self._get_random_user_agent(),
            'Accept': 'application/json',
        }

    def verify_doi_crossref(self, doi: str, log_callback=None) -> Tuple[bool, str, Dict]:
        def log(msg):
            if log_callback:
                log_callback(msg)

        if not doi:
            return False, "No DOI provided", {}

        normalized = doi.strip().replace('https://doi.org/', '').replace('http://dx.doi.org/', '')
        normalized = normalized.strip()
        if not normalized:
            return False, "No DOI provided", {}

        url = f"{self.crossref_base_url}/{normalized.lower()}"
        log(f"Verifying DOI via Crossref: {normalized}")
        try:
            response = self.session.get(url, headers=self._crossref_headers(), timeout=self.timeout)
            if response.status_code == 200:
                payload = response.json()
                message = payload.get('message', {})
                log(f"✓ DOI valid in Crossref")
                return True, "Valid (Crossref)", message
            if response.status_code == 404:
                log(f"✗ DOI not found in Crossref (404)")
                return False, "DOI not found in Crossref (404)", {}
            log(f"✗ Crossref error (HTTP {response.status_code})")
            return False, f"Crossref error (HTTP {response.status_code})", {}
        except requests.exceptions.Timeout:
            log(f"✗ Crossref timeout")
            return False, "Crossref timeout", {}
        except requests.exceptions.ConnectionError:
            log(f"✗ Crossref connection error")
            return False, "Crossref connection error", {}
        except Exception as e:
            log(f"✗ Crossref error: {str(e)[:50]}")
            return False, f"Crossref error: {str(e)[:50]}", {}

    def search_crossref_by_bibliographic(self, query: str, rows: int = 3, log_callback=None) -> List[Dict]:
        def log(msg):
            if log_callback:
                log_callback(msg)

        if not query:
            return []
        log(f"Searching Crossref for similar articles: {query[:80]}")
        try:
            response = self.session.get(
                self.crossref_base_url,
                headers=self._crossref_headers(),
                params={"query.bibliographic": query, "rows": rows},
                timeout=self.timeout,
            )
            if response.status_code != 200:
                log(f"Search failed with status {response.status_code}")
                return []
            payload = response.json()
            items = payload.get('message', {}).get('items', []) or []
            log(f"Found {len(items)} similar articles")
            return items
        except Exception as e:
            log(f"Search error: {str(e)[:50]}")
            return []

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""
        t = unescape(text)
        t = re.sub(r"\s+", " ", t)
        return t.strip().lower()

    def _extract_crossref_year(self, message: Dict) -> str:
        for k in ("published-print", "published-online", "issued"):
            dp = message.get(k, {}).get("date-parts")
            if isinstance(dp, list) and dp and isinstance(dp[0], list) and dp[0]:
                return str(dp[0][0])
        return ""

    def _extract_crossref_title(self, message: Dict) -> str:
        title = message.get("title")
        if isinstance(title, list) and title:
            return str(title[0])
        if isinstance(title, str):
            return title
        return ""

    def _extract_crossref_journal(self, message: Dict) -> str:
        ct = message.get("container-title")
        if isinstance(ct, list) and ct:
            return str(ct[0])
        if isinstance(ct, str):
            return ct
        return ""

    def crossref_to_bibtex(self, message: Dict, original_key: str = None) -> str:
        """Convert Crossref metadata to BibTeX format."""
        entry_type = message.get('type', 'article')
        if entry_type == 'journal-article':
            entry_type = 'article'
        elif entry_type in ['proceedings-article', 'conference-paper']:
            entry_type = 'inproceedings'

        # Generate citation key
        authors = message.get('author', [])
        first_author = ''
        if authors and len(authors) > 0:
            first_author = authors[0].get('family', 'Unknown')
        year = self._extract_crossref_year(message) or 'YEAR'
        title_words = self._extract_crossref_title(message).split()
        first_word = title_words[0] if title_words else 'Title'
        cite_key = original_key or f"{first_author}{year}{first_word}"

        # Build BibTeX entry
        lines = [f"@{entry_type}{{{cite_key},"]

        # Title
        title = self._extract_crossref_title(message)
        if title:
            lines.append(f"  title = {{{title}}},")

        # Authors
        if authors:
            author_str = ' and '.join([
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in authors if a.get('family')
            ])
            if author_str:
                lines.append(f"  author = {{{author_str}}},")

        # Journal
        journal = self._extract_crossref_journal(message)
        if journal:
            lines.append(f"  journal = {{{journal}}},")

        # Year
        if year:
            lines.append(f"  year = {{{year}}},")

        # Volume, issue, pages
        if message.get('volume'):
            lines.append(f"  volume = {{{message['volume']}}},")
        if message.get('issue'):
            lines.append(f"  number = {{{message['issue']}}},")
        if message.get('page'):
            lines.append(f"  pages = {{{message['page']}}},")

        # DOI
        if message.get('DOI'):
            lines.append(f"  doi = {{{message['DOI']}}},")

        # URL
        if message.get('URL'):
            lines.append(f"  url = {{{message['URL']}}},")

        lines.append("}")
        return '\n'.join(lines)

    def _strip_html(self, html_text: str) -> str:
        if not html_text:
            return ""
        t = re.sub(r"<[^>]+>", " ", html_text)
        t = unescape(t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def fetch_abstract_via_browser(self, url: str, browser_timeout_ms: int = 20000, headless: bool = True, log_callback=None) -> Tuple[bool, str]:
        if not url:
            return False, ""

        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            return False, ""

        def log(msg):
            if log_callback:
                log_callback(msg)

        try:
            with sync_playwright() as p:
                if self.chrome_path:
                    log(f"Using Chrome at: {self.chrome_path}")
                else:
                    log("Chrome not found, using Playwright's Chromium")

                log(f"Launching browser (headless={headless}) for {url}")
                # Anti-detection: use realistic browser args
                browser = p.chromium.launch(
                    executable_path=self.chrome_path,
                    headless=headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                    ]
                )
                # Anti-detection: realistic viewport and user agent
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=self._get_random_user_agent(),
                    locale='en-US',
                    timezone_id='America/New_York',
                    permissions=['geolocation'],
                    geolocation={'longitude': -74.006, 'latitude': 40.7128},
                    color_scheme='light',
                    device_scale_factor=1,
                    has_touch=False,
                    is_mobile=False,
                )
                page = context.new_page()

                # Anti-detection: override navigator properties
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                    window.chrome = {runtime: {}};
                """)

                page.set_default_timeout(browser_timeout_ms)
                log(f"Navigating to {url}")
                page.goto(url, wait_until="domcontentloaded")
                # Random human-like delay
                delay = random.randint(1200, 2500)
                log(f"Waiting {delay}ms (simulating human behavior)")
                page.wait_for_timeout(delay)

                selectors = [
                    "meta[name='citation_abstract']",
                    "meta[name='dc.Description']",
                    "meta[name='description']",
                    "meta[property='og:description']",
                ]
                log("Searching for abstract in meta tags")
                for sel in selectors:
                    el = page.query_selector(sel)
                    if el:
                        content = el.get_attribute("content")
                        if content and content.strip():
                            txt = self._strip_html(content)
                            if txt:
                                log(f"Found abstract in meta tag: {sel}")
                                context.close()
                                browser.close()
                                return True, txt

                log("Searching for abstract in page content")
                candidates = page.query_selector_all("article, main, #main, .content, .article")
                for root in candidates:
                    for inner_sel in (".abstract", "#abstract", "section.abstract", "div.abstract"):
                        inner = root.query_selector(inner_sel)
                        if inner:
                            txt = self._strip_html(inner.inner_text() or "")
                            if txt and len(txt) >= 40:
                                log(f"Found abstract in page element: {inner_sel}")
                                context.close()
                                browser.close()
                                return True, txt

                log("No abstract found on page")
                context.close()
                browser.close()
                return False, ""
        except Exception as e:
            log(f"Browser error: {str(e)}")
            return False, ""

    def verify_doi(self, doi: str) -> Tuple[bool, str, int]:
        """
        Verify a DOI by checking if it resolves.

        Args:
            doi: The DOI to verify

        Returns:
            Tuple of (is_valid, message, status_code)
        """
        if not doi:
            return False, "No DOI provided", 0

        # Try multiple DOI resolution services
        doi_urls = [
            f"https://doi.org/{doi}",
            f"https://dx.doi.org/{doi}",
        ]

        headers = {
            'User-Agent': self._get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

        for url in doi_urls:
            try:
                # Use HEAD request first (faster)
                response = self.session.head(
                    url,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True
                )

                if response.status_code == 200:
                    return True, f"Valid (resolved to {response.url[:80]})", response.status_code
                elif response.status_code == 404:
                    return False, "DOI not found (404)", response.status_code
                elif response.status_code == 403:
                    # Try with GET request
                    response = self.session.get(
                        url,
                        headers=headers,
                        timeout=self.timeout,
                        allow_redirects=True
                    )
                    if response.status_code == 200:
                        return True, f"Valid (resolved with GET)", response.status_code
                    return False, f"Access forbidden (403)", response.status_code
                else:
                    continue

            except requests.exceptions.Timeout:
                return False, "Timeout", 0
            except requests.exceptions.ConnectionError:
                return False, "Connection error", 0
            except Exception as e:
                return False, f"Error: {str(e)[:50]}", 0

        return False, "Could not verify", 0

    def verify_arxiv(self, arxiv_id: str) -> Tuple[bool, str]:
        """
        Verify an arXiv ID.

        Args:
            arxiv_id: The arXiv ID to verify

        Returns:
            Tuple of (is_valid, message)
        """
        if not arxiv_id:
            return False, "No arXiv ID provided"

        url = f"https://arxiv.org/abs/{arxiv_id}"
        headers = {'User-Agent': self._get_random_user_agent()}

        try:
            response = self.session.head(url, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                return True, "Valid arXiv ID"
            else:
                return False, f"arXiv ID not found ({response.status_code})"
        except Exception as e:
            return False, f"Error: {str(e)[:50]}"

    def verify_references(self, references: List[Dict], progress_callback=None, log_callback=None) -> List[Dict]:
        """
        Verify a list of references.

        Args:
            references: List of reference dictionaries
            progress_callback: Optional callback function for progress updates
            log_callback: Optional callback function for detailed logging

        Returns:
            List of references with verification results
        """
        def log(msg):
            if log_callback:
                log_callback(msg)

        results = []
        total = len(references)

        for idx, ref in enumerate(references, 1):
            result = ref.copy()
            result['verification'] = {}

            # Progress update
            if progress_callback:
                progress_callback(idx, total, ref.get('key', 'Unknown'))

            log(f"\n[{idx}/{total}] Verifying: {ref.get('key', 'Unknown')}")
            if 'title' in ref:
                log(f"  Title: {ref['title'][:80]}")

            if 'doi' in ref:
                log(f"  Checking DOI: {ref['doi']}")
                doi_resolve_valid, doi_resolve_msg, doi_resolve_code = self.verify_doi(ref['doi'])
                result['verification']['doi_resolve'] = {
                    'valid': doi_resolve_valid,
                    'message': doi_resolve_msg,
                    'status_code': doi_resolve_code
                }
                log(f"    DOI resolve: {doi_resolve_msg}")
                self._delay()

                crossref_valid, crossref_msg, crossref_message = self.verify_doi_crossref(ref['doi'], log_callback)
                result['verification']['doi_crossref'] = {
                    'valid': crossref_valid,
                    'message': crossref_msg,
                }
                if crossref_message:
                    result['verification']['crossref'] = {
                        'doi': crossref_message.get('DOI', ''),
                        'title': self._extract_crossref_title(crossref_message)[:200],
                        'journal': self._extract_crossref_journal(crossref_message)[:120],
                        'year': self._extract_crossref_year(crossref_message),
                    }
                    if 'abstract' not in result and crossref_message.get('abstract'):
                        result['abstract'] = self._strip_html(crossref_message.get('abstract'))
                self._delay()

            # Verify arXiv
            if 'arxiv' in ref:
                log(f"  Checking arXiv: {ref['arxiv']}")
                is_valid, message = self.verify_arxiv(ref['arxiv'])
                result['verification']['arxiv'] = {
                    'valid': is_valid,
                    'message': message
                }
                log(f"    arXiv: {message}")
                self._delay()

            status = 'NO_IDENTIFIER'
            if 'doi_crossref' in result['verification']:
                status = 'VALID' if result['verification']['doi_crossref']['valid'] else 'INVALID'
            elif 'arxiv' in result['verification']:
                status = 'VALID' if result['verification']['arxiv']['valid'] else 'INVALID'
            result['status'] = status

            log(f"  Status: {status}")
            results.append(result)

        return results

    def search_alternatives_for_invalid(self, results: List[Dict], output_bib: str, log_callback=None):
        """
        Search for alternative articles for invalid references and save to BibTeX file.

        Args:
            results: List of verification results
            output_bib: Output BibTeX file path
            log_callback: Optional callback function for logging
        """
        def log(msg):
            if log_callback:
                log_callback(msg)

        invalid_refs = [r for r in results if r['status'] == 'INVALID']
        if not invalid_refs:
            log("No invalid references found, skipping alternative search")
            return

        log(f"\nSearching for alternatives to {len(invalid_refs)} invalid references...")

        bib_lines = []
        bib_lines.append("% Alternative references for potentially invalid citations")
        bib_lines.append(f"% Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        bib_lines.append("% Please review these suggestions and decide which to use\n")

        for ref in invalid_refs:
            original_key = ref.get('key', 'Unknown')
            title = ref.get('title', '')
            journal = ref.get('journal', '')
            year = ref.get('year', '')

            log(f"\n  Searching alternatives for: {original_key}")

            # Build search query
            query_parts = []
            if title:
                query_parts.append(title[:100])
            if journal:
                query_parts.append(journal[:50])
            if year:
                query_parts.append(year)

            query = ' '.join(query_parts)
            if not query:
                log(f"    No searchable metadata, skipping")
                continue

            # Search Crossref
            alternatives = self.search_crossref_by_bibliographic(query, rows=3, log_callback=log_callback)

            if alternatives:
                bib_lines.append(f"\n% ========================================")
                bib_lines.append(f"% Original (INVALID): {original_key}")
                if title:
                    bib_lines.append(f"% Original title: {title[:80]}")
                if ref.get('doi'):
                    bib_lines.append(f"% Original DOI: {ref['doi']} (NOT FOUND)")
                bib_lines.append(f"% Found {len(alternatives)} similar articles:")
                bib_lines.append(f"% ========================================\n")

                for idx, alt in enumerate(alternatives, 1):
                    alt_title = self._extract_crossref_title(alt)
                    alt_journal = self._extract_crossref_journal(alt)
                    alt_year = self._extract_crossref_year(alt)
                    alt_doi = alt.get('DOI', '')

                    log(f"    Alternative {idx}: {alt_title[:60]}... ({alt_year})")

                    bib_lines.append(f"% Alternative {idx} for {original_key}:")
                    bib_lines.append(f"% Title: {alt_title[:100]}")
                    bib_lines.append(f"% Journal: {alt_journal[:80]}")
                    bib_lines.append(f"% Year: {alt_year}")
                    bib_lines.append(f"% DOI: {alt_doi}")
                    bib_lines.append(f"% Source: Crossref API search")

                    # Generate BibTeX entry
                    new_key = f"{original_key}_alt{idx}"
                    bibtex = self.crossref_to_bibtex(alt, new_key)
                    bib_lines.append(bibtex)
                    bib_lines.append("")

                self._delay()
            else:
                log(f"    No alternatives found")

        # Write to file
        if bib_lines:
            with open(output_bib, 'w', encoding='utf-8') as f:
                f.write('\n'.join(bib_lines))
            log(f"\nAlternative references saved to: {output_bib}")
        else:
            log("\nNo alternatives found to save")

    def generate_report(self, results: List[Dict], output_file: str = None):
        """
        Generate a verification report.

        Args:
            results: List of verification results
            output_file: Optional output file path
        """
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("BIBLIOGRAPHY VERIFICATION REPORT")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 80)
        report_lines.append("")

        # Summary statistics
        total = len(results)
        valid = sum(1 for r in results if r['status'] == 'VALID')
        invalid = sum(1 for r in results if r['status'] == 'INVALID')
        no_id = sum(1 for r in results if r['status'] == 'NO_IDENTIFIER')

        report_lines.append("SUMMARY")
        report_lines.append("-" * 80)
        report_lines.append(f"Total references: {total}")
        report_lines.append(f"Valid: {valid} ({valid/total*100:.1f}%)")
        report_lines.append(f"Invalid: {invalid} ({invalid/total*100:.1f}%)")
        report_lines.append(f"No identifier: {no_id} ({no_id/total*100:.1f}%)")
        report_lines.append("")

        # Detailed results
        report_lines.append("DETAILED RESULTS")
        report_lines.append("-" * 80)

        for idx, result in enumerate(results, 1):
            report_lines.append(f"\n[{idx}] {result.get('key', 'Unknown')}")
            report_lines.append(f"    Type: {result.get('type', 'N/A')}")
            report_lines.append(f"    Status: {result['status']}")

            if 'title' in result:
                report_lines.append(f"    Title: {result['title']}")
            if 'year' in result:
                report_lines.append(f"    Year: {result['year']}")
            if 'journal' in result:
                report_lines.append(f"    Journal: {result['journal']}")

            if 'doi' in result:
                report_lines.append(f"    DOI: {result['doi']}")
                if 'doi_crossref' in result['verification']:
                    v = result['verification']['doi_crossref']
                    report_lines.append(f"        → {v['message']}")
                if 'doi_resolve' in result['verification']:
                    v = result['verification']['doi_resolve']
                    report_lines.append(f"        → Resolve: {v['message']} (HTTP {v['status_code']})")
                if 'crossref' in result['verification']:
                    c = result['verification']['crossref']
                    if c.get('title'):
                        report_lines.append(f"        → Crossref title: {c.get('title','')[:80]}")
                    if c.get('journal'):
                        report_lines.append(f"        → Crossref journal: {c.get('journal','')[:80]}")
                    if c.get('year'):
                        report_lines.append(f"        → Crossref year: {c.get('year','')}")

            if 'arxiv' in result:
                report_lines.append(f"    arXiv: {result['arxiv']}")
                if 'arxiv' in result['verification']:
                    v = result['verification']['arxiv']
                    report_lines.append(f"        → {v['message']}")

            if result.get('abstract'):
                report_lines.append(f"    Abstract: {str(result.get('abstract'))[:160]}")

        # Invalid references section
        invalid_refs = [r for r in results if r['status'] == 'INVALID']
        if invalid_refs:
            report_lines.append("\n" + "=" * 80)
            report_lines.append("POTENTIALLY FAKE REFERENCES")
            report_lines.append("=" * 80)
            for result in invalid_refs:
                report_lines.append(f"\n⚠ {result.get('key', 'Unknown')}")
                if 'title' in result:
                    report_lines.append(f"  Title: {result['title']}")
                if 'doi' in result:
                    report_lines.append(f"  DOI: {result['doi']}")
                    if 'doi_crossref' in result['verification']:
                        report_lines.append(f"  Issue: {result['verification']['doi_crossref']['message']}")
                    if 'doi_resolve' in result['verification']:
                        report_lines.append(f"  Resolve: {result['verification']['doi_resolve']['message']}")

        report_text = "\n".join(report_lines)

def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Verify the authenticity of references in a BibTeX file'
    )
    parser.add_argument(
        'bibfile',
        nargs='?',
        help='Path to the .bib file to verify'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output report file (default: verification_report.txt)',
        default='verification_report.txt'
    )
    parser.add_argument(
        '-j', '--json',
        help='Also save results as JSON',
        action='store_true'
    )
    parser.add_argument(
        '--gui',
        action='store_true',
        help='Launch a Tkinter GUI'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=10,
        help='Request timeout in seconds (default: 10)'
    )
    parser.add_argument(
        '--delay-min',
        type=float,
        default=1.0,
        help='Minimum delay between requests in seconds (default: 1.0)'
    )
    parser.add_argument(
        '--delay-max',
        type=float,
        default=3.0,
        help='Maximum delay between requests in seconds (default: 3.0)'
    )
    parser.add_argument(
        '--fetch-abstract',
        action='store_true',
        help='Attempt to fetch abstract (Crossref first, then optional browser mode)'
    )
    parser.add_argument(
        '--use-browser',
        action='store_true',
        help='Use Playwright + local Chrome (headless) as a fallback to extract abstract from the DOI/URL page'
    )
    parser.add_argument(
        '--show-browser',
        action='store_true',
        help='Show the Chrome window when using --use-browser (headful mode)'
    )
    parser.add_argument(
        '--browser-timeout-ms',
        type=int,
        default=20000,
        help='Timeout for browser navigation/extraction in milliseconds (default: 20000)'
    )
    parser.add_argument(
        '--search-alternatives',
        action='store_true',
        help='Search for alternative articles for invalid references and save to BibTeX file'
    )
    parser.add_argument(
        '--alternatives-output',
        default='alternatives.bib',
        help='Output file for alternative references (default: alternatives.bib)'
    )

    args = parser.parse_args()

    if args.gui:
        return gui_main()

    if not args.bibfile:
        parser.error('bibfile is required unless --gui is used')

    print("BibTeX Reference Verification Tool")
    print("=" * 80)
    print(f"Input file: {args.bibfile}")
    print(f"Output report: {args.output}")
    print(f"Timeout: {args.timeout}s")
    print(f"Delay range: {args.delay_min}-{args.delay_max}s")
    if args.search_alternatives:
        print(f"Alternative references output: {args.alternatives_output}")
    print("=" * 80)
    print()

    # Initialize verifier
    verifier = ReferenceVerifier(
        timeout=args.timeout,
        delay_range=(args.delay_min, args.delay_max)
    )

    # Parse BibTeX file
    print("Parsing BibTeX file...")
    references = verifier.parse_bib_file(args.bibfile)
    print(f"Found {len(references)} references\n")

    # Verify references
    print("Verifying references (this may take a while)...")
    print("-" * 80)

    def progress_callback(current, total, key):
        print(f"[{current}/{total}] Verifying: {key}")

    def log_callback(msg):
        print(msg)

    results = verifier.verify_references(references, progress_callback, log_callback)

    if args.fetch_abstract:
        print("\n" + "-" * 80)
        print("Fetching abstracts...")
        print("-" * 80)
        for r in results:
            if r.get('abstract'):
                continue
            target_url = None
            if r.get('doi'):
                doi = str(r.get('doi')).strip().replace('https://doi.org/', '')
                if doi:
                    target_url = f"https://doi.org/{doi}"
            if not target_url and r.get('url'):
                target_url = r.get('url')

            if args.use_browser and target_url:
                ok, abstract = verifier.fetch_abstract_via_browser(
                    target_url,
                    browser_timeout_ms=args.browser_timeout_ms,
                    headless=(not args.show_browser),
                    log_callback=log_callback,
                )
                if ok and abstract:
                    r['abstract'] = abstract
            verifier._delay()

    # Search for alternatives if requested
    if args.search_alternatives:
        print("\n" + "-" * 80)
        print("Searching for alternative references...")
        print("-" * 80)
        verifier.search_alternatives_for_invalid(results, args.alternatives_output, log_callback)

    print("\n" + "=" * 80)
    print("Verification complete!")
    print("=" * 80)
    print()

    # Generate report
    verifier.generate_report(results, args.output)

    # Save JSON if requested
    if args.json:
        json_file = args.output.replace('.txt', '.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"JSON results saved to: {json_file}")


def gui_main():
    root = tk.Tk()
    root.title('BibTeX Reference Verification Tool')
    root.geometry('900x650')

    state = {
        'running': False,
        'queue': queue.Queue(),
    }

    bib_path = tk.StringVar(value='')
    out_path = tk.StringVar(value=os.path.join(os.getcwd(), 'verification_report.txt'))
    timeout_s = tk.StringVar(value='10')
    delay_min = tk.StringVar(value='1.0')
    delay_max = tk.StringVar(value='3.0')
    export_json = tk.BooleanVar(value=True)
    fetch_abstract = tk.BooleanVar(value=False)
    use_browser = tk.BooleanVar(value=False)
    show_browser = tk.BooleanVar(value=False)
    browser_timeout_ms = tk.StringVar(value='20000')
    search_alternatives = tk.BooleanVar(value=False)
    alternatives_path = tk.StringVar(value=os.path.join(os.getcwd(), 'alternatives.bib'))

    progress_var = tk.StringVar(value='Idle')

    def append_log(line: str):
        log_text.configure(state='normal')
        log_text.insert('end', line + '\n')
        log_text.see('end')
        log_text.configure(state='disabled')

    def set_controls_enabled(enabled: bool):
        widgets = [
            bib_entry, out_entry,
            btn_browse_bib, btn_browse_out,
            timeout_entry, delay_min_entry, delay_max_entry,
            json_chk, abstract_chk, browser_chk, show_browser_chk,
            browser_timeout_entry, alternatives_chk, alternatives_entry,
            btn_browse_alternatives,
            btn_run,
        ]
        for w in widgets:
            try:
                w.configure(state=('normal' if enabled else 'disabled'))
            except Exception:
                pass

    def pick_bib():
        path = filedialog.askopenfilename(
            title='Select .bib file',
            filetypes=[('BibTeX files', '*.bib'), ('All files', '*.*')],
        )
        if path:
            bib_path.set(path)

    def pick_out():
        path = filedialog.asksaveasfilename(
            title='Save report as',
            defaultextension='.txt',
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
        )
        if path:
            out_path.set(path)

    def pick_alternatives():
        path = filedialog.asksaveasfilename(
            title='Save alternatives as',
            defaultextension='.bib',
            filetypes=[('BibTeX files', '*.bib'), ('All files', '*.*')],
        )
        if path:
            alternatives_path.set(path)

    def validate_inputs() -> Tuple[bool, str]:
        if not bib_path.get().strip():
            return False, 'Please select a .bib file.'
        if not os.path.isfile(bib_path.get().strip()):
            return False, 'Selected .bib file does not exist.'
        try:
            t = int(timeout_s.get())
            if t <= 0:
                return False, 'Timeout must be a positive integer.'
        except Exception:
            return False, 'Timeout must be an integer.'
        try:
            dmin = float(delay_min.get())
            dmax = float(delay_max.get())
            if dmin < 0 or dmax < 0 or dmin > dmax:
                return False, 'Delay range is invalid.'
        except Exception:
            return False, 'Delay min/max must be numbers.'
        try:
            bto = int(browser_timeout_ms.get())
            if bto <= 0:
                return False, 'Browser timeout must be a positive integer.'
        except Exception:
            return False, 'Browser timeout must be an integer.'
        return True, ''

    def worker_run(options: Dict):
        q = state['queue']
        try:
            def log_callback(msg):
                q.put(('log', msg))

            verifier = ReferenceVerifier(timeout=options['timeout'], delay_range=(options['delay_min'], options['delay_max']))
            q.put(('log', 'Parsing BibTeX file...'))
            refs = verifier.parse_bib_file(options['bibfile'])
            q.put(('log', f"Found {len(refs)} references"))

            def progress_callback(current, total, key):
                q.put(('progress', f"[{current}/{total}] Verifying: {key}"))

            q.put(('log', 'Verifying references...'))
            results = verifier.verify_references(refs, progress_callback, log_callback)

            if options['fetch_abstract']:
                q.put(('log', 'Fetching abstracts (Crossref first, optional browser)...'))
                for idx, r in enumerate(results, 1):
                    q.put(('progress', f"[Abstract {idx}/{len(results)}] {r.get('key','Unknown')}"))
                    if r.get('abstract'):
                        continue
                    target_url = None
                    if r.get('doi'):
                        doi = str(r.get('doi')).strip().replace('https://doi.org/', '')
                        if doi:
                            target_url = f"https://doi.org/{doi}"
                    if not target_url and r.get('url'):
                        target_url = r.get('url')
                    if options['use_browser'] and target_url:
                        ok, abstract = verifier.fetch_abstract_via_browser(
                            target_url,
                            browser_timeout_ms=options['browser_timeout_ms'],
                            headless=(not options['show_browser']),
                            log_callback=log_callback,
                        )
                        if ok and abstract:
                            r['abstract'] = abstract
                    verifier._delay()

            if options['search_alternatives']:
                q.put(('log', 'Searching for alternative references...'))
                verifier.search_alternatives_for_invalid(results, options['alternatives_output'], log_callback)

            q.put(('log', 'Generating report...'))
            verifier.generate_report(results, options['output'])
            if options['export_json']:
                json_file = options['output'].replace('.txt', '.json')
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                q.put(('log', f"JSON results saved to: {json_file}"))

            q.put(('done', 'Done'))
        except Exception as e:
            q.put(('error', str(e)))

    def run_clicked():
        if state['running']:
            return
        ok, msg = validate_inputs()
        if not ok:
            messagebox.showerror('Invalid input', msg)
            return
        log_text.configure(state='normal')
        log_text.delete('1.0', 'end')
        log_text.configure(state='disabled')

        options = {
            'bibfile': bib_path.get().strip(),
            'output': out_path.get().strip(),
            'timeout': int(timeout_s.get()),
            'delay_min': float(delay_min.get()),
            'delay_max': float(delay_max.get()),
            'export_json': bool(export_json.get()),
            'fetch_abstract': bool(fetch_abstract.get()),
            'use_browser': bool(use_browser.get()),
            'show_browser': bool(show_browser.get()),
            'browser_timeout_ms': int(browser_timeout_ms.get()),
            'search_alternatives': bool(search_alternatives.get()),
            'alternatives_output': alternatives_path.get().strip(),
        }

        state['running'] = True
        set_controls_enabled(False)
        progress_var.set('Starting...')
        t = threading.Thread(target=worker_run, args=(options,), daemon=True)
        t.start()

    def on_tick():
        q = state['queue']
        try:
            while True:
                kind, payload = q.get_nowait()
                if kind == 'log':
                    append_log(payload)
                elif kind == 'progress':
                    progress_var.set(payload)
                elif kind == 'done':
                    append_log('Completed.')
                    progress_var.set('Completed')
                    state['running'] = False
                    set_controls_enabled(True)
                    messagebox.showinfo('Finished', 'Verification completed.')
                elif kind == 'error':
                    append_log('Error: ' + payload)
                    progress_var.set('Error')
                    state['running'] = False
                    set_controls_enabled(True)
                    messagebox.showerror('Error', payload)
        except queue.Empty:
            pass
        root.after(150, on_tick)

    frm_top = tk.Frame(root)
    frm_top.pack(fill='x', padx=12, pady=10)

    tk.Label(frm_top, text='BibTeX file:').grid(row=0, column=0, sticky='w')
    bib_entry = tk.Entry(frm_top, textvariable=bib_path)
    bib_entry.grid(row=0, column=1, sticky='we', padx=8)
    btn_browse_bib = tk.Button(frm_top, text='Browse...', command=pick_bib)
    btn_browse_bib.grid(row=0, column=2)

    tk.Label(frm_top, text='Report output:').grid(row=1, column=0, sticky='w', pady=(8, 0))
    out_entry = tk.Entry(frm_top, textvariable=out_path)
    out_entry.grid(row=1, column=1, sticky='we', padx=8, pady=(8, 0))
    btn_browse_out = tk.Button(frm_top, text='Browse...', command=pick_out)
    btn_browse_out.grid(row=1, column=2, pady=(8, 0))

    frm_top.columnconfigure(1, weight=1)

    frm_opts = tk.LabelFrame(root, text='Options')
    frm_opts.pack(fill='x', padx=12, pady=(0, 10))

    tk.Label(frm_opts, text='Timeout (s):').grid(row=0, column=0, sticky='w', padx=8, pady=8)
    timeout_entry = tk.Entry(frm_opts, width=10, textvariable=timeout_s)
    timeout_entry.grid(row=0, column=1, sticky='w', pady=8)

    tk.Label(frm_opts, text='Delay min (s):').grid(row=0, column=2, sticky='w', padx=8, pady=8)
    delay_min_entry = tk.Entry(frm_opts, width=10, textvariable=delay_min)
    delay_min_entry.grid(row=0, column=3, sticky='w', pady=8)

    tk.Label(frm_opts, text='Delay max (s):').grid(row=0, column=4, sticky='w', padx=8, pady=8)
    delay_max_entry = tk.Entry(frm_opts, width=10, textvariable=delay_max)
    delay_max_entry.grid(row=0, column=5, sticky='w', pady=8)

    json_chk = tk.Checkbutton(frm_opts, text='Export JSON', variable=export_json)
    json_chk.grid(row=1, column=0, sticky='w', padx=8, pady=(0, 8))

    abstract_chk = tk.Checkbutton(frm_opts, text='Fetch abstract', variable=fetch_abstract)
    abstract_chk.grid(row=1, column=1, sticky='w', padx=8, pady=(0, 8))

    browser_chk = tk.Checkbutton(frm_opts, text='Use browser fallback', variable=use_browser)
    browser_chk.grid(row=1, column=2, sticky='w', padx=8, pady=(0, 8))

    show_browser_chk = tk.Checkbutton(frm_opts, text='Show browser window', variable=show_browser)
    show_browser_chk.grid(row=1, column=3, sticky='w', padx=8, pady=(0, 8))

    tk.Label(frm_opts, text='Browser timeout (ms):').grid(row=1, column=4, sticky='w', padx=8, pady=(0, 8))
    browser_timeout_entry = tk.Entry(frm_opts, width=10, textvariable=browser_timeout_ms)
    browser_timeout_entry.grid(row=1, column=5, sticky='w', pady=(0, 8))

    alternatives_chk = tk.Checkbutton(frm_opts, text='Search alternatives for invalid refs', variable=search_alternatives)
    alternatives_chk.grid(row=2, column=0, columnspan=2, sticky='w', padx=8, pady=(0, 8))

    frm_alternatives = tk.Frame(root)
    frm_alternatives.pack(fill='x', padx=12, pady=(0, 10))
    tk.Label(frm_alternatives, text='Alternatives output:').pack(side='left')
    alternatives_entry = tk.Entry(frm_alternatives, textvariable=alternatives_path)
    alternatives_entry.pack(side='left', fill='x', expand=True, padx=8)
    btn_browse_alternatives = tk.Button(frm_alternatives, text='Browse...', command=pick_alternatives)
    btn_browse_alternatives.pack(side='left')

    frm_run = tk.Frame(root)
    frm_run.pack(fill='x', padx=12, pady=(0, 10))
    btn_run = tk.Button(frm_run, text='Run verification', command=run_clicked)
    btn_run.pack(side='left')
    tk.Label(frm_run, textvariable=progress_var).pack(side='left', padx=12)

    frm_log = tk.LabelFrame(root, text='Log')
    frm_log.pack(fill='both', expand=True, padx=12, pady=(0, 12))
    log_text = tk.Text(frm_log, wrap='word', state='disabled')
    log_text.pack(fill='both', expand=True, padx=8, pady=8)

    root.after(150, on_tick)
    root.mainloop()


if __name__ == '__main__':
    main()
