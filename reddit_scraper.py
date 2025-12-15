import asyncio
import json
import csv
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import re

class RedditScraper:
    """Scraper for Reddit subreddit metrics using Playwright"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.results = []
        
    async def setup_browser(self):
        """Setup browser with stealth configuration"""
        playwright = await async_playwright().start()
        
        browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-extensions',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1536, 'height': 816},  # Match browser tool window size
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            }
        )
        
        # Add stealth scripts
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
        """)
        
        return playwright, browser, context
    
    def parse_number(self, text: str) -> Optional[str]:
        """Parse number from text (handles K, M suffixes)"""
        if not text:
            return None
        
        # Remove any non-numeric characters except K, M, and decimal point
        text = text.strip().upper()
        
        # Extract number and suffix
        match = re.search(r'([\d.]+)\s*([KM]?)', text)
        if match:
            number = match.group(1)
            suffix = match.group(2)
            return f"{number}{suffix}" if suffix else number
        
        # Try to extract just numbers
        numbers = re.findall(r'[\d.]+', text)
        if numbers:
            return numbers[0]
        
        return None
    
    def find_metric_value(self, text: str, keywords: List[str]) -> Optional[str]:
        """Find metric value that matches any of the keywords"""
        text_lower = text.lower()
        for keyword in keywords:
            if keyword.lower() in text_lower:
                # Try to extract the number
                return self.parse_number(text)
        return None
    
    async def scrape_subreddit(self, url: str, page) -> Dict[str, Optional[str]]:
        """Scrape metrics from a single subreddit using the provided page"""
        result = {
            'url': url,
            'weekly_visitors': None,
            'weekly_contributors': None
        }
        
        try:
            # Navigate to the subreddit (pages load quickly)
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            # Wait for the metric divs or slot elements to appear (pages load quickly)
            try:
                await page.wait_for_selector('div.flex.flex-col.items-start.flex-grow, [slot="weekly-active-users-count"]', timeout=10000)
            except:
                # If selectors don't appear, short wait for React to render
                await page.wait_for_timeout(1000)
            
            # Brief wait for any dynamic content
            await page.wait_for_timeout(500)
            
            # Use JavaScript evaluation to find metrics based on the actual Reddit structure
            # Reddit uses slot names: weekly-active-users-count and weekly-contributions-count
            try:
                metrics = await page.evaluate("""
                    () => {
                        const results = { visitors: null, contributors: null };
                        
                        // Method 1: Look for elements with specific slot names (works for r/automation, r/n8n, r/casino, etc.)
                        // This is the most reliable method as it targets the exact slot names
                        // Weekly active users count (visitors)
                        const visitorSlot = document.querySelector('[slot="weekly-active-users-count"]');
                        if (visitorSlot && !results.visitors) {
                            // Case 1: Slot element has direct text (r/automation, r/n8n style)
                            const slotText = visitorSlot.textContent?.trim() || visitorSlot.innerText?.trim() || '';
                            if (slotText && /\\d/.test(slotText)) {
                                const visitorMatch = slotText.match(/(\\d+(?:[.,]\\d+)?[KM]?)/);
                                if (visitorMatch) {
                                    results.visitors = visitorMatch[1].replace(/,/g, '');
                                }
                            } else {
                                // Case 2: Slot is empty, check parent container for faceplate-number or strong tag (r/casino style)
                                const parentContainer = visitorSlot.closest('div.flex.flex-col.items-start.flex-grow') || 
                                                       visitorSlot.parentElement;
                                if (parentContainer) {
                                    const visitorFaceplate = parentContainer.querySelector('faceplate-number');
                                    if (visitorFaceplate) {
                                        const number = visitorFaceplate.textContent?.trim() || visitorFaceplate.getAttribute('number');
                                        if (number) {
                                            results.visitors = number.replace(/,/g, '');
                                        }
                                    } else {
                                        const strongTag = parentContainer.querySelector('strong');
                                        if (strongTag) {
                                            const visitorText = strongTag.textContent || strongTag.innerText || '';
                                            const visitorMatch = visitorText.match(/(\\d+(?:[.,]\\d+)?[KM]?)/);
                                            if (visitorMatch) {
                                                results.visitors = visitorMatch[1].replace(/,/g, '');
                                            }
                                        } else {
                                            const visitorText = parentContainer.textContent || parentContainer.innerText || '';
                                            const visitorMatch = visitorText.match(/(\\d+(?:[.,]\\d+)?[KM]?)/);
                                            if (visitorMatch) {
                                                results.visitors = visitorMatch[1].replace(/,/g, '');
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        
                        // Weekly contributions count (contributors)
                        const contributorSlot = document.querySelector('[slot="weekly-contributions-count"]');
                        if (contributorSlot && !results.contributors) {
                            // Case 1: Slot element has direct text (r/automation, r/n8n style)
                            const slotText = contributorSlot.textContent?.trim() || contributorSlot.innerText?.trim() || '';
                            if (slotText && /\\d/.test(slotText)) {
                                const contributorMatch = slotText.match(/(\\d+(?:[.,]\\d+)?[KM]?)/);
                                if (contributorMatch) {
                                    results.contributors = contributorMatch[1].replace(/,/g, '');
                                }
                            } else {
                                // Case 2: Slot is empty, check parent container for faceplate-number or strong tag (r/casino style)
                                const parentContainer = contributorSlot.closest('div.flex.flex-col.items-start.flex-grow') || 
                                                       contributorSlot.parentElement;
                                if (parentContainer) {
                                    const contributorFaceplate = parentContainer.querySelector('faceplate-number');
                                    if (contributorFaceplate) {
                                        const number = contributorFaceplate.textContent?.trim() || contributorFaceplate.getAttribute('number');
                                        if (number) {
                                            results.contributors = number.replace(/,/g, '');
                                        }
                                    } else {
                                        const strongTag = parentContainer.querySelector('strong');
                                        if (strongTag) {
                                            const contributorText = strongTag.textContent || strongTag.innerText || '';
                                            const contributorMatch = contributorText.match(/(\\d+(?:[.,]\\d+)?[KM]?)/);
                                            if (contributorMatch) {
                                                results.contributors = contributorMatch[1].replace(/,/g, '');
                                            }
                                        } else {
                                            const contributorText = parentContainer.textContent || parentContainer.innerText || '';
                                            const contributorMatch = contributorText.match(/(\\d+(?:[.,]\\d+)?[KM]?)/);
                                            if (contributorMatch) {
                                                results.contributors = contributorMatch[1].replace(/,/g, '');
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        
                        // Method 2: Look for the div structure (fallback for subreddits without slot elements)
                        // Find divs with class "flex flex-col items-start flex-grow"
                        // First div = visitors, second div = contributors
                        const metricDivs = Array.from(document.querySelectorAll('div.flex.flex-col.items-start.flex-grow'));
                        if (metricDivs.length >= 2) {
                            // First div contains visitors
                            if (!results.visitors && metricDivs[0]) {
                                // Try to find faceplate-number first (most reliable)
                                const visitorFaceplate = metricDivs[0].querySelector('faceplate-number');
                                if (visitorFaceplate) {
                                    const number = visitorFaceplate.textContent?.trim() || visitorFaceplate.getAttribute('number');
                                    if (number) {
                                        results.visitors = number.replace(/,/g, '');
                                    }
                                }
                                
                                // If no faceplate-number, try to extract from strong tag or text content
                                if (!results.visitors) {
                                    const strongTag = metricDivs[0].querySelector('strong');
                                    if (strongTag) {
                                        const visitorText = strongTag.textContent || strongTag.innerText || '';
                                        const visitorMatch = visitorText.match(/(\\d+(?:[.,]\\d+)?[KM]?)/);
                                        if (visitorMatch) {
                                            results.visitors = visitorMatch[1].replace(/,/g, '');
                                        }
                                    }
                                }
                                
                                // Fallback: extract from entire div text
                                if (!results.visitors) {
                                    const visitorText = metricDivs[0].textContent || metricDivs[0].innerText || '';
                                    const visitorMatch = visitorText.match(/(\\d+(?:[.,]\\d+)?[KM]?)/);
                                    if (visitorMatch) {
                                        results.visitors = visitorMatch[1].replace(/,/g, '');
                                    }
                                }
                            }
                            
                            // Second div contains contributors
                            if (!results.contributors && metricDivs[1]) {
                                // Try to find faceplate-number first (most reliable)
                                const contributorFaceplate = metricDivs[1].querySelector('faceplate-number');
                                if (contributorFaceplate) {
                                    const number = contributorFaceplate.textContent?.trim() || contributorFaceplate.getAttribute('number');
                                    if (number) {
                                        results.contributors = number.replace(/,/g, '');
                                    }
                                }
                                
                                // If no faceplate-number, try to extract from strong tag or text content
                                if (!results.contributors) {
                                    const strongTag = metricDivs[1].querySelector('strong');
                                    if (strongTag) {
                                        const contributorText = strongTag.textContent || strongTag.innerText || '';
                                        const contributorMatch = contributorText.match(/(\\d+(?:[.,]\\d+)?[KM]?)/);
                                        if (contributorMatch) {
                                            results.contributors = contributorMatch[1].replace(/,/g, '');
                                        }
                                    }
                                }
                                
                                // Fallback: extract from entire div text
                                if (!results.contributors) {
                                    const contributorText = metricDivs[1].textContent || metricDivs[1].innerText || '';
                                    const contributorMatch = contributorText.match(/(\\d+(?:[.,]\\d+)?[KM]?)/);
                                    if (contributorMatch) {
                                        results.contributors = contributorMatch[1].replace(/,/g, '');
                                    }
                                }
                            }
                        }
                        
                        
                        return results;
                    }
                """)
                
                if metrics.get('visitors'):
                    result['weekly_visitors'] = metrics['visitors']
                if metrics.get('contributors'):
                    result['weekly_contributors'] = metrics['contributors']
                    
            except Exception as e:
                # Fallback: try text-based search
                try:
                    body_text = await page.evaluate("() => document.body.textContent || ''")
                    
                    # Keywords for weekly visitors (members, subscribers, gamblers, etc.)
                    visitor_keywords = [
                        'weekly visitors', 'visitors', 'members', 'subscribers', 
                        'gamblers', 'users', 'community members', 'joined'
                    ]
                    
                    # Keywords for weekly contributors (active, here now, online, contributors, etc.)
                    contributor_keywords = [
                        'weekly contributors', 'contributors', 'here now', 'online',
                        'active', 'active users', 'currently online', 'online now'
                    ]
                    
                    # Look for visitor metric
                    if not result['weekly_visitors']:
                        visitor_value = self.find_metric_value(body_text, visitor_keywords)
                        if visitor_value:
                            result['weekly_visitors'] = visitor_value
                    
                    # Look for contributor metric
                    if not result['weekly_contributors']:
                        contributor_value = self.find_metric_value(body_text, contributor_keywords)
                        if contributor_value:
                            result['weekly_contributors'] = contributor_value
                except:
                    pass
            
        except PlaywrightTimeoutError:
            pass  # Timeout occurred, metrics will be None
        except Exception as e:
            pass  # Error occurred, metrics will be None
        # Don't close the page - reuse it for next URL
        
        return result
    
    async def scrape_subreddits(self, urls: List[str], output_file: str = None, csv_file: str = None) -> List[Dict]:
        """Scrape multiple subreddits using the same browser/page continuously"""
        playwright, browser, context = await self.setup_browser()
        results = []
        page = None
        
        try:
            # Create a single page to reuse for all URLs
            page = await context.new_page()
            
            for url in urls:
                print(f"Scraping: {url}")
                result = await self.scrape_subreddit(url, page)
                results.append(result)
                
                # Print result
                print(f"  Visitors: {result['weekly_visitors'] or 'Not found'}")
                print(f"  Contributors: {result['weekly_contributors'] or 'Not found'}")
                print()
                
                # Save results after each URL (incremental saving)
                if output_file:
                    self.save_results(results, output_file)
                if csv_file:
                    self.save_results_csv(results, csv_file)
                
                # Small delay between requests
                await asyncio.sleep(1)
        
        finally:
            # Close page and browser only at the end
            if page:
                await page.close()
            await browser.close()
            await playwright.stop()
        
        return results
    
    def save_results(self, results: List[Dict], output_file: str = 'reddit_results.json'):
        """Save results to JSON file (overwrites file each time)"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        # Don't print every time to avoid spam, only print on final save
    
    def save_results_csv(self, results: List[Dict], output_file: str = 'reddit_results.csv'):
        """Save results to CSV file (overwrites file each time)"""
        if not results:
            return
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['url', 'weekly_visitors', 'weekly_contributors'])
            writer.writeheader()
            for result in results:
                writer.writerow(result)
        # Don't print every time to avoid spam, only print on final save


async def main():
    """Main function to run the scraper"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape Reddit subreddit metrics')
    parser.add_argument('--urls', type=str, nargs='+', help='List of subreddit URLs')
    parser.add_argument('--file', type=str, help='File containing URLs (one per line or JSON array)')
    parser.add_argument('--output', type=str, default='reddit_results.json', help='Output file path')
    parser.add_argument('--csv', type=str, help='Also save as CSV with this filename')
    
    # Browser mode options (default: headless)
    browser_mode = parser.add_mutually_exclusive_group()
    browser_mode.add_argument('--headless', action='store_true', default=True,
                             help='Run browser in headless mode (default - no browser window)')
    browser_mode.add_argument('--headful', '--visible', dest='headless', action='store_false',
                             help='Run browser in visible/headful mode (shows browser window)')
    # Alias for backward compatibility
    parser.add_argument('--no-headless', dest='headless', action='store_false',
                       help='[Alias for --headful] Run browser in visible mode')
    
    args = parser.parse_args()
    
    urls = []
    
    # Get URLs from command line or file
    if args.urls:
        urls = args.urls
    elif args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            # Try JSON first
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    urls = data
                else:
                    urls = [data]
            except:
                # Otherwise treat as line-separated URLs
                urls = [line.strip() for line in content.split('\n') if line.strip()]
    else:
        # Default: use example URL
        urls = ['https://www.reddit.com/r/gambling/']
    
    if not urls:
        print("No URLs provided. Use --urls or --file to specify subreddit URLs.")
        return
    
    # Create scraper and run
    scraper = RedditScraper(headless=args.headless)
    results = await scraper.scrape_subreddits(urls, output_file=args.output, csv_file=args.csv)
    
    # Print final save confirmation
    if results:
        print(f"\nFinal results: {len(results)} subreddits scraped")
        print(f"Results saved to {args.output}")
        if args.csv:
            print(f"Results saved to {args.csv}")


if __name__ == '__main__':
    asyncio.run(main())
