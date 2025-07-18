import httpx
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

# Import our Pydantic models
from app.models import Product, BrandInsights, ContactDetails, Policy

class ShopifyScraper:
    """
    A class to scrape and extract insights from a single Shopify store.
    """
    def __init__(self, url: str):
        # Ensure the URL has a scheme (e.g., https://)
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        self.base_url = url.rstrip('/')
        self.insights = BrandInsights(
            store_url=self.base_url,
            contact_details=ContactDetails() # Initialize with empty contact details
        )
        # Using a client for connection pooling and header management
        self.client = httpx.AsyncClient(
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'},
            timeout=15.0, # Add a timeout to prevent hanging
            follow_redirects=True
        )

    async def _scrape_faqs(self, faq_url: str) -> List[Dict[str, str]]:
        """
        A robust, multi-layered scraper to extract FAQs from a given URL.
        It handles single-page accordions and multi-page linked questions.
        """
        print(f"--- Starting FAQ Hunt at: {faq_url} ---")
        faq_soup = await self._get_soup(faq_url)
        if not faq_soup:
            return []
    
        faqs_list = []
    
        # --- STRATEGY 1: The Accordion Hunter ---
        # Look for common container patterns for FAQ items.
        # The <details> tag is a modern, semantic tag for accordions.
        # Otherwise, look for divs with class names containing "faq", "accordion", "item", "question".
        potential_items = faq_soup.select('details, div[class*="faq"], div[class*="accordion"], div[class*="item"]')
        
        for item in potential_items:
            question_tag = None
            answer_tag = None
    
            # Try to find a question-like element (heading, strong tag, or button)
            question_tag = item.find(['h2', 'h3', 'h4', 'strong', 'b']) or item.find(role='button')
            
            # Try to find an answer-like element (a div with "content" or "answer", or just a paragraph)
            answer_tag = item.find(['div', 'p'], class_=re.compile(r'(content|answer|body|panel)', re.I))
    
            # If we couldn't find a specific answer tag, a reasonable guess is the *next* sibling div or p
            if question_tag and not answer_tag:
                answer_tag = question_tag.find_next_sibling(['div', 'p'])
                
            if question_tag and answer_tag:
                question = question_tag.get_text(strip=True)
                answer = answer_tag.get_text(separator='\n', strip=True)
    
                # Basic validation: ensure we found non-empty text
                if question and answer and 'your-question-here' not in question.lower():
                    print(f"  [Accordion Hunter] Found Q: {question[:30]}...")
                    faqs_list.append({"question": question, "answer": answer})
    
        # If the Accordion Hunter was successful, we can return the results.
        if faqs_list:
            print(f"--- FAQ Hunt Successful: Found {len(faqs_list)} items using Accordion Strategy. ---")
            return faqs_list
    
        # --- STRATEGY 2: The Linked Questions Hunter ---
        print("--- Accordion Hunter found nothing. Trying Linked Questions Hunter. ---")
        # This strategy runs if the first one failed. It looks for a list of links.
        # We target the main content area to avoid grabbing header/footer links.
        main_area = faq_soup.main or faq_soup.body
        question_links = main_area.find_all('a', href=re.compile(r'(faq|question|/a/)'))
    
        if not question_links: # Broaden search if specific one fails
            question_links = [a for a in main_area.find_all('a', href=True) if '?' in a.get_text()]
    
        for link in question_links:
            question_text = link.get_text(strip=True)
            if question_text and len(question_text) > 5:
                linked_url = urljoin(self.base_url, link['href'])
                print(f"  [Link Hunter] Found linked question, fetching content from {linked_url}")
                # Use our existing helper to grab the content from the linked page
                answer_content = await self._fetch_and_format_page_content(linked_url)
                if answer_content:
                    faqs_list.append({"question": question_text, "answer": answer_content})
    
        if faqs_list:
            print(f"--- FAQ Hunt Successful: Found {len(faqs_list)} items using Linked Questions Strategy. ---")
            return faqs_list
    
        # --- STRATEGY 3: General Content Grab (Fallback) ---
        print("--- Both specialized hunters failed. Using fallback content grab. ---")
        fallback_content = await self._fetch_and_format_page_content(faq_url)
        if fallback_content:
            return [{"question": "General FAQ Page Content", "answer": fallback_content}]
    
        return [] # Return empty if all strategies fail

    async def _fetch_and_format_page_content(self, url: str) -> Optional[str]:
        """
        Fetches a given URL, finds the <main> content area, and extracts
        the text with preserved formatting (paragraphs and line breaks).
        """
        if not url:
            return None
    
        page_soup = await self._get_soup(url)
        if not page_soup:
            return None
    
        main_content = page_soup.main
        if not main_content:
            return None
    
        # Use .get_text() with a separator to preserve line breaks.
        # A newline character '\n' works perfectly for this.
        # The 'strip=True' removes leading/trailing whitespace from each line.
        text = main_content.get_text(separator='\n', strip=True)
        
        # Optional: Clean up excessive blank lines.
        # This regex replaces two or more newlines with just two newlines (a single blank line).
        cleaned_text = re.sub(r'\n{3,}', '\n\n', text)
        
        return cleaned_text

    async def run(self) -> BrandInsights:
        """Orchestrates the scraping process."""
        try:
            # Fetch and parse the product catalog first (most reliable)
            await self._fetch_product_catalog()

            # Fetch the homepage for links, hero products, etc.
            homepage_soup = await self._get_soup(self.base_url)
            if homepage_soup:
                self._extract_social_handles(homepage_soup)
                self._extract_contact_details(homepage_soup)
                await self._extract_links_and_policies(homepage_soup)
                self._extract_hero_products(homepage_soup)

        finally:
            # Always close the client session
            await self.client.aclose()
        
        return self.insights

    async def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """Fetches a URL and returns a BeautifulSoup object."""
        try:
            response = await self.client.get(url)
            response.raise_for_status() # Raise an exception for 4xx or 5xx status codes
            return BeautifulSoup(response.text, 'lxml')
        except httpx.RequestError as e:
            print(f"Error fetching {e.request.url}: {e}")
            return None
        except httpx.HTTPStatusError as e:
            print(f"HTTP error for {e.request.url}: {e.response.status_code}")
            return None

    async def _fetch_product_catalog(self):
        """Fetches the entire product catalog from the /products.json endpoint."""
        products_url = f"{self.base_url}/products.json"
        try:
            response = await self.client.get(products_url)
            response.raise_for_status()
            data = response.json()
    
            for product_data in data.get('products', []):
                # --- SAFER EXTRACTION LOGIC ---
                variants = product_data.get('variants', [])
                images = product_data.get('images', [])
    
                # Use .get() with default values to prevent crashes
                price = float(variants[0].get('price', 0.0)) if variants else 0.0
                sku = variants[0].get('sku') if variants else None
                image_url = images[0].get('src') if images else None
    
                # Create the Pydantic model
                product = Product(
                    id=product_data.get('id'),
                    title=product_data.get('title'),
                    handle=product_data.get('handle'),
                    vendor=product_data.get('vendor'),
                    product_type=product_data.get('product_type'),
                    created_at=product_data.get('created_at'),
                    price=price,
                    sku=sku,
                    image_url=image_url
                )
                self.insights.product_catalog.append(product)
        except (httpx.RequestError, ValueError, KeyError) as e: # Added KeyError
            print(f"Could not fetch or parse product catalog from {products_url}: {e}")

    def _extract_social_handles(self, soup: BeautifulSoup):
        """Extracts social media links from the page."""
        social_keywords = ['instagram', 'facebook', 'twitter', 'pinterest', 'youtube', 'tiktok']
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].lower()
            for keyword in social_keywords:
                if keyword in href:
                    self.insights.social_handles[keyword] = urljoin(self.base_url, a_tag['href'])
                    break # Move to the next link once a keyword is found

    def _extract_contact_details(self, soup: BeautifulSoup):
        """Extracts emails and phone numbers using regex."""
        text = soup.get_text()
        # Regex for finding emails
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        self.insights.contact_details.emails.extend(list(set(emails))) # Use set to avoid duplicates

        # Regex for finding phone numbers (basic North American/Indian format)
        phones = re.findall(r'(\+?\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?[\d\s.-]{7,10}', text)
        # Clean up and filter phone numbers
        cleaned_phones = [
            "".join(filter(str.isdigit, "".join(p))) for p in phones
            if len("".join(filter(str.isdigit, "".join(p)))) >= 10
        ]
        self.insights.contact_details.phone_numbers.extend(list(set(cleaned_phones)))

    async def _extract_links_and_policies(self, soup: BeautifulSoup):
        """
        Finds links to important pages, then visits each one to extract
        its formatted text content, storing both the URL and the content.
        """
        # ... (the link_map dictionary is the same) ...
        link_map = {
            'privacy': 'Privacy Policy', 'refund': 'Refund Policy', 'return': 'Return Policy',
            'terms': 'Terms of Service', 'shipping': 'Shipping Policy', 'faq': 'FAQs',
            'contact': 'Contact Us', 'about': 'About Us', 'track': 'Order Tracking',
            'blog': 'Blogs'
        }
        
        found_links = {}
        for keyword, name in link_map.items():
            link_tag = soup.find('a', text=re.compile(rf'\b{keyword}\b', re.IGNORECASE), href=True)
            if link_tag:
                full_url = urljoin(self.base_url, link_tag['href'])
                found_links[name] = full_url

        for name, url in found_links.items():
            print(f"Fetching content for: {name} at {url}")
            content = await self._fetch_and_format_page_content(url)

            # Categorize the extracted content and link
            if name == 'About Us':
                self.insights.brand_context = content
                # Also save the link to important_links for completeness
                self.insights.important_links[name] = url
            elif 'Policy' in name or 'Service' in name:
                # --- THIS IS THE KEY CHANGE ---
                # Create a Policy object with both URL and content
                policy_data = Policy(url=url, content=content)
                self.insights.policies[name] = policy_data
            elif name == 'FAQs':
                # Call our new, specialized FAQ hunter
                self.insights.faqs = await self._scrape_faqs(url)
                # We still save the main FAQ page link for reference
                self.insights.important_links[name] = url
            else:
                self.insights.important_links[name] = url

    def _extract_hero_products(self, soup: BeautifulSoup):
        """Extracts products featured on the homepage."""
        # This is a heuristic: look for links pointing to '/products/'
        # within common sections like 'main', 'section', or divs with 'product' in the class.
        product_links = set()
        for a_tag in soup.select('main a, section a'):
            href = a_tag.get('href', '')
            if '/products/' in href:
                # Extract the product "handle" from the URL
                handle = href.split('/products/')[-1].split('?')[0]
                if handle:
                    product_links.add(handle)
        self.insights.hero_products = list(product_links)