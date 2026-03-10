# test amazon scraper to ensure it can extract product information correctly
import asyncio
from scrapers.amazon_scraper import AmazonScraper

async def test_amazon_scraper():
    scraper = AmazonScraper()
    products = await scraper.scrape(categories=["Shoes"],limit=2)
    print(f"Scraped {len(products)} products from Amazon.")
    for product in products[:5]:  # Print first 5 products
        print(product)

if __name__ == "__main__":
    asyncio.run(test_amazon_scraper())

    # # test ollama integration
    # from scrapers.base_scraper import BaseScraper, OllamaClient,ProductExtractor
    # scraper = ProductExtractor()  # Create an instance of ProductExtractor to use its methods
    # prompt = "On a scale of 0 to 10, how stylish is a red leather jacket with silver zippers?. just return the number, no explanation."
    # response = asyncio.run(scraper.calculate_style_score("Red Leather Jacket", "A stylish red leather jacket with silver zippers."))


    # print(f"Ollama response: {response}")

    # ollama_client = OllamaClient()
    # response = ollama_client.get_response(prompt)
    # print(f"OllamaClient response: {response}")