import requests
import json
import os
import time
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from tenacity import retry, stop_after_attempt, wait_exponential

# Load environment variables for API Key
load_dotenv()
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY")
RAINFOREST_API_KEY = os.environ.get("RAINFOREST_API_KEY")

if not MINIMAX_API_KEY:
    raise ValueError("MINIMAX_API_KEY is not set in .env file")

# Initialize MiniMax LLM
llm = ChatOpenAI(
    temperature=0.3,
    model_name="abab6.5s-chat",
    openai_api_key=MINIMAX_API_KEY,
    openai_api_base="https://api.minimax.chat/v1",
    max_tokens=1024
)

# Prompt template for AI Analysis
analysis_prompt = PromptTemplate(
    input_variables=["title", "copy"],
    template="""
    你是一个资深的跨境电商（亚马逊）营销专家。请分析以下产品的标题和描述文案，并提取关键信息。
    
    产品标题: {title}
    产品文案: {copy}
    
    请严格按照以下JSON格式输出，不要包含任何其他说明文字：
    {{
        "ai_tags": ["标签1", "标签2", "标签3", "标签4", "标签5"],
        "ai_analysis": "用一段话分析该素材的核心卖点、目标人群和文案策略技巧。"
    }}
    """
)

def discover_asins_by_search(search_term, max_results=2):
    """
    Use Rainforest Search API to dynamically find the top ASINs for a given keyword.
    """
    if not RAINFOREST_API_KEY or RAINFOREST_API_KEY == "your_rainforest_api_key_here":
        return []
        
    print(f"  🔍 Searching Amazon US for: '{search_term}'...")
    params = {
        "api_key": RAINFOREST_API_KEY,
        "type": "search",
        "amazon_domain": "amazon.com",
        "search_term": search_term,
        "sort_by": "featured" # Get the most relevant/featured products
    }
    
    try:
        response = requests.get("https://api.rainforestapi.com/request", params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if data.get("request_info", {}).get("success"):
            search_results = data.get("search_results", [])
            # Extract ASINs from the top organic results
            asins = [item.get("asin") for item in search_results if item.get("asin")][:max_results]
            print(f"  🎯 Found ASINs for '{search_term}': {asins}")
            return asins
        else:
            print(f"  ❌ Search API error: {data.get('request_info', {}).get('message')}")
            return []
    except Exception as e:
        print(f"  ❌ Search Network/API error: {e}")
        return []

def fetch_amazon_product_data(custom_asins=None, custom_queries=None):
    """
    Fetch real Amazon product data using Rainforest API.
    Dynamically discovers ASINs based on business requirements before fetching details.
    Can be overridden with custom_asins or custom_queries.
    """
    print("[Step 1] Starting data scraping pipeline (Dynamic Discovery via Rainforest API)...")
    
    # MVP Core Requirements
    search_queries = custom_queries if custom_queries else [
        "TCL Smart TV",
        "Samsung Refrigerator",
        "LG Washing Machine"
    ]
    
    asins_to_fetch = set(custom_asins) if custom_asins else set()
    
    # Phase 1: Discovery (Only if we don't have explicit ASINs to fetch)
    if not custom_asins and RAINFOREST_API_KEY and RAINFOREST_API_KEY != "your_rainforest_api_key_here":
        for query in search_queries:
            # Get top 2 ASINs per category to save API credits during MVP
            discovered = discover_asins_by_search(query, max_results=2)
            asins_to_fetch.update(discovered)
            time.sleep(1) # Be nice to the API
            
    asins_to_fetch = list(asins_to_fetch)
    
    if not asins_to_fetch:
        print("  ⚠️ No ASINs discovered dynamically. Falling back to default list.")
        asins_to_fetch = ["B0DXMT6YD4", "B0C73HSQ8T"] # Fallback ASINs
        
    print(f"  📋 Final list of ASINs to fetch details for: {asins_to_fetch}")
    
    scraped_data = []
    
    # Phase 2: Fetch Details
    if RAINFOREST_API_KEY and RAINFOREST_API_KEY != "your_rainforest_api_key_here":
        for asin in asins_to_fetch:
            print(f"  -> Fetching real data for ASIN: {asin}...")
            params = {
                "api_key": RAINFOREST_API_KEY,
                "type": "product",
                "amazon_domain": "amazon.com",
                "asin": asin
            }
            try:
                response = requests.get("https://api.rainforestapi.com/request", params=params, timeout=15)
                response.raise_for_status()
                data = response.json()
                
                if data.get("request_info", {}).get("success"):
                    product = data.get("product", {})
                    title = product.get("title", "No Title")
                    
                    # 动态推断品类
                    inferred_category = "Electronics"
                    title_lower = title.lower()
                    if "tv" in title_lower or "television" in title_lower:
                        inferred_category = "TV"
                    elif "refrigerator" in title_lower or "fridge" in title_lower:
                        inferred_category = "Refrigerator"
                    elif "washer" in title_lower or "washing machine" in title_lower:
                        inferred_category = "Washing Machine"
                    elif "dryer" in title_lower:
                        inferred_category = "Dryer"
                    elif "air conditioner" in title_lower:
                        inferred_category = "Air Conditioner"
                    elif "air fryer" in title_lower:
                        inferred_category = "Air Fryer"
                    
                    # Format into our expected schema
                    item = {
                        "id": f"{product.get('brand', 'unknown').lower()}_{asin.lower()}_{int(time.time())}",
                        "channel": "Amazon US",
                        "brand": product.get("brand", "Unknown"),
                        "title": title,
                        "original_copy": " ".join(product.get("feature_bullets", [])),
                        "image_url": product.get("main_image", {}).get("link", "https://via.placeholder.com/800"),
                        "source_url": product.get("link", f"https://www.amazon.com/dp/{asin}"),
                        "metadata": {
                            "rating": product.get("rating", 0.0),
                            "reviews": product.get("ratings_total", 0),
                            "price": product.get("buybox_winner", {}).get("price", {}).get("raw", "N/A"),
                            "category": inferred_category
                        }
                    }
                    scraped_data.append(item)
                    print(f"  ✅ Successfully scraped {item['brand']} - {item['title'][:20]}...")
                else:
                    print(f"  ❌ Rainforest API error for {asin}: {data.get('request_info', {}).get('message')}")
            except Exception as e:
                print(f"  ❌ Network/API error for {asin}: {e}")
                
            # Sleep to avoid hitting API rate limits too fast
            time.sleep(2)
            
    # If we successfully scraped real data, return it
    if scraped_data:
        print(f"  -> Successfully fetched {len(scraped_data)} real items.")
        return scraped_data
        
    # --- FALLBACK TO MOCK DATA ---
    print("  -> Falling back to structured mock data due to API failure or missing key.")
    
    # Ensure all fields are present: id, channel, brand, title, original_copy, image_url, source_url, metadata
    structured_mock_data = [
        {
            "id": "hisense_tv_001",
            "channel": "Amazon US",
            "brand": "Hisense",
            "title": "Hisense 65-Inch Class U8 Series Mini-LED ULED 4K UHD Google Smart TV",
            "original_copy": "The Hisense U8 series is our best all-around TV. Mini-LED Pro with Full Array Local Dimming creates brighter, more detailed images. QLED Quantum Dot Color produces over a billion shades of color. 144Hz Game Mode Pro for ultra-smooth gaming.",
            "image_url": "https://images.unsplash.com/photo-1593784991095-a205069470b6?auto=format&fit=crop&w=800&q=80",
            "source_url": "https://www.amazon.com/dp/B0C73HSQ8T",
            "metadata": {"rating": 4.5, "reviews": 3200, "price": "$899.99", "category": "TV"}
        },
        {
            "id": "lg_fridge_001",
            "channel": "Amazon US",
            "brand": "LG",
            "title": "LG 28 cu. ft. Smart Wi-Fi Enabled InstaView Door-in-Door Refrigerator",
            "original_copy": "Knock twice and see inside. The LG InstaView Door-in-Door brings a sleek glass panel that illuminates with two quick knocks. Craft Ice Maker creates slow-melting round ice. Linear Cooling keeps temperatures within 1°F of the setting.",
            "image_url": "https://images.unsplash.com/photo-1571175443880-49e1d25b2bc5?auto=format&fit=crop&w=800&q=80",
            "source_url": "https://www.amazon.com/dp/B08V5H5QZB",
            "metadata": {"rating": 4.3, "reviews": 1850, "price": "$1,999.00", "category": "Refrigerator"}
        }
    ]
    
    return structured_mock_data

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def analyze_with_llm(chain, title, copy):
    """Call LLM with automatic retries if it fails."""
    response = chain.invoke({"title": title, "copy": copy})
    ai_output_str = response.content.strip()
    
    # Clean up potential markdown formatting from LLM (e.g., ```json ... ```)
    if "```json" in ai_output_str:
        ai_output_str = ai_output_str.split("```json")[1].split("```")[0].strip()
    elif "```" in ai_output_str:
        ai_output_str = ai_output_str.split("```")[1].split("```")[0].strip()
        
    import re
    # Try to extract just the JSON dictionary if there's surrounding text
    match = re.search(r'\{[\s\S]*\}', ai_output_str)
    if match:
        ai_output_str = match.group(0)
        
    return json.loads(ai_output_str)

def process_with_ai(raw_data):
    """Passes raw scraped data through MiniMax LLM to generate tags and analysis."""
    print(f"[Step 2] Processing {len(raw_data)} items with MiniMax AI...")
    
    processed_data = []
    chain = analysis_prompt | llm
    
    for i, item in enumerate(raw_data):
        print(f"  -> Analyzing item {i+1}: {item['brand']}...")
        try:
            # Call LLM with tenacity retry mechanism
            ai_result = analyze_with_llm(chain, item["title"], item["original_copy"])
            
            # Merge AI results into the item
            item["ai_tags"] = ai_result.get("ai_tags", [])
            item["ai_analysis"] = ai_result.get("ai_analysis", "分析生成失败")
            
        except Exception as e:
            print(f"  [Error] Failed to process item {item['id']} after multiple attempts: {e}")
            item["ai_tags"] = []
            item["ai_analysis"] = "分析生成失败 (API 错误或解析失败)"
            
        processed_data.append(item)
        
        # Respect rate limits
        time.sleep(1)
            
    return processed_data

def save_to_json(data, filename="scraped_data.json"):
    """Saves the final processed data to a JSON file atomically, appending to existing data."""
    print(f"[Step 3] Saving {len(data)} new items to {filename}...")
    temp_filename = f"{filename}.tmp"
    
    # Load existing data to append rather than overwrite
    existing_data = []
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"[Warning] Could not load existing data: {e}. Starting fresh.")
            
    # Simple deduplication by ID
    existing_ids = {item["id"] for item in existing_data if "id" in item}
    new_items_added = 0
    
    for new_item in data:
        # In a real scenario you might want to update existing items, but here we'll just append new ones
        # For demonstration purposes, we'll append a timestamp to the ID if it already exists to force an addition
        # so you can see the count increase in the UI when clicking the button multiple times.
        if new_item["id"] in existing_ids:
            new_item["id"] = f"{new_item['id']}_{int(time.time())}"
            
        existing_data.append(new_item)
        new_items_added += 1

    try:
        # Write to a temporary file first to avoid corruption if interrupted
        with open(temp_filename, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        
        # Replace the original file with the temporary one
        os.replace(temp_filename, filename)
        print(f"[Success] Successfully saved {new_items_added} new items (Total: {len(existing_data)}) to {filename}")
    except Exception as e:
        print(f"[Error] Failed to save JSON data: {e}")
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

def sync_to_chromadb(data, collection_name="competitor_products"):
    """Syncs processed data to ChromaDB for vector search capabilities.
    Note: Disabled here because app.py handles it with MiniMaxEmbeddings.
    Importing chromadb here causes OpenBLAS memory issues in constrained environments.
    """
    print(f"[Step 4] Skipping ChromaDB sync (handled by app.py automatically on next run).")
    pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Competitor Analysis Pipeline")
    parser.add_argument("--asin", type=str, help="Comma-separated list of specific ASINs to fetch")
    parser.add_argument("--query", type=str, help="Comma-separated list of search queries to fetch")
    args = parser.parse_args()

    custom_asins = args.asin.split(",") if args.asin else None
    custom_queries = args.query.split(",") if args.query else None

    # Run the full pipeline
    print("[Start] Starting Competitor Analysis Pipeline...")
    raw_items = fetch_amazon_product_data(custom_asins=custom_asins, custom_queries=custom_queries)
    enriched_items = process_with_ai(raw_items)
    save_to_json(enriched_items, "mock_data.json")
    # Note: ChromaDB sync is handled by app.py automatically upon reload,
    # so we avoid default Chroma client embeddings here to prevent memory issues.
    print("[End] Pipeline completed successfully!")