import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
import httpx
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

# Load the environment variables (like your API key) from the .env file
load_dotenv()

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

    async def _scrape_faqs_with_gemini(self, faq_url: str) -> List[Dict[str, str]]:
        """
        Uses Google's Gemini Pro to extract FAQs from the raw HTML of a page.
        """
        print(f"--- Starting AI-Powered FAQ Hunt at: {faq_url} ---")
        faq_soup = await self._get_soup(faq_url)
        if not faq_soup:
            return []

        # 1. Clean the HTML for the LLM
        # Remove script and style tags as they are noise for the LLM
        for tag in faq_soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        
        html_content = str(faq_soup.body) # Get the content of the body

        # 2. Configure the Gemini API
        try:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                print("ERROR: GOOGLE_API_KEY not found in .env file.")
                return []
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-pro')
        except Exception as e:
            print(f"Error configuring Gemini: {e}")
            return []
            
        # 3. Craft the Prompt
        prompt = f"""
        You are an expert web scraper and data extractor. Your task is to analyze the following raw HTML content from a website's FAQ page and extract all the Question and Answer pairs.

        Please adhere to these rules:
        1. Identify every distinct question and its corresponding answer.
        2. Format your response as a valid JSON array of objects.
        3. Each object in the array must have two keys: "question" and "answer".
        4. The "question" key's value should be the full question text.
        5. The "answer" key's value should be the full answer text, preserving line breaks.
        6. If you cannot find any FAQs in the provided HTML, you MUST return an empty JSON array: [].
        7. Do not include any text, explanation, or markdown formatting outside of the final JSON array.

        Here is the HTML content to analyze:
        ```html
        {html_content}
        ```
        """

        # 4. Make the API Call and Parse the Response
        try:
            print("  Sending HTML content to Gemini for analysis...")
            response = model.generate_content(prompt)
            
            # Clean up the response from Gemini, which might be wrapped in markdown
            cleaned_response = response.text.strip().replace('```json', '').replace('```', '').strip()
            
            print("  Received response from Gemini. Parsing JSON...")
            faqs_list = json.loads(cleaned_response)
            
            # Final validation to ensure it's a list of dicts
            if isinstance(faqs_list, list):
                print(f"--- AI Hunt Successful: Extracted {len(faqs_list)} FAQs. ---")
                return faqs_list
            else:
                print("--- AI Hunt Warning: Gemini did not return a valid list. ---")
                return []

        except json.JSONDecodeError:
            print("--- AI Hunt FAILED: Gemini returned invalid JSON. ---")
            print("Gemini's raw response:", response.text)
            return []
        except Exception as e:
            print(f"--- AI Hunt FAILED: An unexpected error occurred: {e} ---")
            return []

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
                self.insights.faqs = await self._scrape_faqs_with_gemini(url)
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
