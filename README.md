# Reddit Subreddit Scraper

A Playwright-based scraper to extract weekly visitors and weekly contributors from Reddit subreddits.

## Features

- Scrapes "weekly visitors" (members, subscribers, etc.) and "weekly contributors" (active users, online now, etc.)
- Handles different label variations across subreddits
- Supports multiple URLs from command line or file
- Exports results to JSON and CSV formats

## Installation

The required packages are already installed in the `.venv` in the parent Frane folder.

### Using the Existing .venv

1. **Activate the virtual environment:**
   ```bash
   # Windows (PowerShell)
   ..\.venv\Scripts\Activate.ps1
   
   # Windows (Command Prompt)
   ..\.venv\Scripts\activate.bat
   
   # Linux/Mac
   source ../.venv/bin/activate
   ```

2. **Verify Playwright is installed:**
   ```bash
   playwright --version
   ```

### Fresh Installation (if needed)

If you need to install packages separately:

```bash
# Activate virtual environment first (see above)
pip install -r requirements.txt
playwright install chromium
```

## Usage

### Activate Virtual Environment First

Before running the scraper, make sure to activate the `.venv`:

```bash
# Windows (PowerShell)
cd RedditScraper
..\.venv\Scripts\Activate.ps1

# Windows (Command Prompt)
cd RedditScraper
..\.venv\Scripts\activate.bat

# Linux/Mac
cd RedditScraper
source ../.venv/bin/activate
```

### Command Line Arguments

```bash
python reddit_scraper.py [options]
```

### Options

- `--urls URL1 URL2 ...` - List of subreddit URLs to scrape
- `--file FILE` - File containing URLs (one per line or JSON array)
- `--output FILE` - Output JSON file path (default: `reddit_results.json`)
- `--csv FILE` - Also save results as CSV
- `--headless` - Run browser in headless mode (default - no browser window)
- `--headful` or `--visible` - Run browser in visible/headful mode (shows browser window for debugging)
- `--no-headless` - [Alias for --headful] Run browser in visible mode

### Examples

```bash
# Scrape a single subreddit
python reddit_scraper.py --urls https://www.reddit.com/r/gambling/

# Scrape multiple subreddits
python reddit_scraper.py --urls https://www.reddit.com/r/gambling/ https://www.reddit.com/r/poker/

# Scrape from a file
python reddit_scraper.py --file urls.txt --output results.json --csv results.csv

# Run with visible browser (for debugging)
python reddit_scraper.py --urls https://www.reddit.com/r/gambling/ --headful
# Or use --visible or --no-headless (all do the same thing)
python reddit_scraper.py --urls https://www.reddit.com/r/gambling/ --visible
```

### Input File Format

You can provide URLs in a text file (one per line) or as a JSON array:

**urls.txt:**
```
https://www.reddit.com/r/gambling/
https://www.reddit.com/r/poker/
https://www.reddit.com/r/casino/
```

**urls.json:**
```json
[
  "https://www.reddit.com/r/gambling/",
  "https://www.reddit.com/r/poker/",
  "https://www.reddit.com/r/casino/"
]
```

## Output Format

### JSON Output
```json
[
  {
    "url": "https://www.reddit.com/r/gambling/",
    "weekly_visitors": "170K",
    "weekly_contributors": "2.7K"
  }
]
```

### CSV Output
```csv
url,weekly_visitors,weekly_contributors
https://www.reddit.com/r/gambling/,170K,2.7K
```

## Notes

- **Results are saved incrementally**: After each URL is scraped, results are automatically saved to the output files. This means if the scraper is interrupted, you won't lose data from URLs already processed.
- **Browser reuse**: The scraper reuses the same browser page for all URLs, making it faster and more efficient.
- **Viewport size**: Uses 1536x816 viewport to match browser tool dimensions.
- The scraper looks for various label variations (members, subscribers, gamblers, etc. for visitors; here now, online, active, etc. for contributors)
- Some subreddits may have different label names, and the scraper attempts to handle these variations
- If a metric is not found, it will be `null` in the output
- The scraper includes a 1-second delay between requests to be respectful to Reddit's servers
