# BibTeX Reference Verification Tool

A Python tool to verify the authenticity of bibliographic references in BibTeX files by checking DOI links, arXiv IDs, and other identifiers.

## Features

- **DOI Verification**: Checks if DOI links resolve correctly via Crossref API
- **arXiv Verification**: Validates arXiv preprint IDs
- **Alternative Search**: Automatically searches for similar articles when references are invalid
- **Browser Automation**: Uses your system Chrome browser with anti-detection features
- **Anti-Crawling Protection**:
  - Random delays between requests (1-3 seconds by default)
  - User-agent rotation with human-like fingerprints
  - Automatic retry with exponential backoff
  - Handles 403, 429, and 5xx errors gracefully
- **Comprehensive Reporting**:
  - Summary statistics
  - Detailed verification results with verbose logging
  - List of potentially fake references
  - Alternative references in BibTeX format
  - JSON export option
- **GUI Mode**: User-friendly Tkinter interface

## Installation

### Prerequisites

- Python 3.7 or higher
- pip package manager

### Install Dependencies

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install requests urllib3
```

## Usage

### Basic Usage

```bash
python main.py refs.bib
```

This will:
1. Parse the BibTeX file
2. Verify all DOI and arXiv identifiers
3. Generate a report saved to `verification_report.txt`

### Advanced Options

```bash
python verify_references.py refs.bib -o my_report.txt --json --timeout 15 --delay-min 2 --delay-max 5
```

#### Command-line Arguments

- `bibfile`: Path to the .bib file to verify (required)
- `-o, --output`: Output report file (default: `verification_report.txt`)
- `-j, --json`: Also save results as JSON
- `--timeout`: Request timeout in seconds (default: 10)
- `--delay-min`: Minimum delay between requests in seconds (default: 1.0)
- `--delay-max`: Maximum delay between requests in seconds (default: 3.0)

### Example

```bash
# Verify refs.bib with custom settings
python verify_references.py refs.bib -o report.txt --json --timeout 20 --delay-min 1.5 --delay-max 4
```

## How It Works

### 1. Parsing

The tool parses the BibTeX file and extracts:
- Citation keys
- DOI identifiers
- arXiv IDs
- URLs
- Titles, years, journals

### 2. Verification

For each reference:

**DOI Verification:**
- Attempts to resolve DOI via `https://doi.org/` and `https://dx.doi.org/`
- Uses HEAD requests first (faster), falls back to GET if needed
- Checks HTTP status codes (200 = valid, 404 = not found, 403 = forbidden)

**arXiv Verification:**
- Checks if arXiv ID exists at `https://arxiv.org/abs/`
- Validates format and accessibility

### 3. Anti-Crawling Measures

To avoid being blocked:
- Random delays between requests (configurable)
- Rotates between multiple user-agent strings
- Implements retry logic with exponential backoff
- Handles rate limiting (429) and server errors (5xx)

### 4. Reporting

Generates a comprehensive report with:
- Summary statistics (total, valid, invalid, no identifier)
- Detailed results for each reference
- Special section highlighting potentially fake references

## Understanding Results

### Status Codes

- **VALID**: Reference verified successfully
- **INVALID**: Reference could not be verified (potentially fake)
- **NO_IDENTIFIER**: No DOI or arXiv ID found (cannot verify)

### HTTP Status Codes

- **200**: Success - reference exists
- **404**: Not found - likely fake or incorrect DOI
- **403**: Forbidden - publisher blocking access (may still be valid)
- **0**: Timeout or connection error

## Troubleshooting

### Issue: Too many 403 errors

**Solution**: Increase delays between requests
```bash
python main.py refs.bib --delay-min 3 --delay-max 6
```

### Issue: Timeout errors

**Solution**: Increase timeout value
```bash
python main.py refs.bib --timeout 30
```

### Issue: Connection errors

**Solution**: Check your internet connection and try again. Some publishers may temporarily block requests.

## Best Practices

1. **Run during off-peak hours** to reduce chance of being blocked
2. **Use longer delays** (3-5 seconds) for large reference lists
3. **Manually verify** any references marked as invalid
4. **Check JSON output** for detailed status codes and messages
5. **Re-run failed checks** after some time if you suspect network issues

## Example Workflow

```bash
# 1. Install dependencies
pip install -r requirements.txt
```
```bash
# 2. Run verification with tkinter GUI
python main.py --gui
```
```bash
# 3. Review the report
nano report.txt
```

## License

This tool is provided as-is for academic and research purposes.

## Disclaimer

This tool is designed for legitimate verification of bibliographic references. Please respect publisher terms of service and rate limits.
