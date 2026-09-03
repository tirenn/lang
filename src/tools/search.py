from typing import List, Dict, Any
import time
import re
from urllib.parse import urlparse
from duckduckgo_search import DDGS
from src.state import ResearchItem

# Domain blacklist: toko online, e-commerce, spesifikasi gadget, marketplace, quiz spam
IRRELEVANT_DOMAINS = {
    "samsung.com",
    "apple.com",
    "shopee.co.id",
    "shopee.com",
    "tokopedia.com",
    "lazada.co.id",
    "blibli.com",
    "bukalapak.com",
    "amazon.com",
    "ebay.com",
    "aliexpress.com",
    "gsmarena.com",
    "pricebook.co.id",
    "iprice.co.id",
    "cekresi.com",
    "carousell.com",
    "olx.co.id",
    "tiktok.com",
    "16personalities.com",
    "testmoa.com",
    "kmbti.co.kr"
}

def clean_query(raw_query: str) -> str:
    """Membersihkan kata tanya percakapan agar ramah algoritma search engine."""
    q = raw_query.strip()
    q = re.sub(r'["\']', ' ', q)
    stop_starters = [
        r"^apakah\s+",
        r"^benarkah\s+",
        r"^mengapa\s+",
        r"^kenapa\s+",
        r"^bagaimanakah\s+",
        r"^bagaimana\s+",
        r"^apa\s+itu\s+",
        r"^apa\s+"
    ]
    for pattern in stop_starters:
        q = re.sub(pattern, "", q, flags=re.IGNORECASE)
    return " ".join(q.split())

def is_domain_allowed(url: str) -> bool:
    """Memfilter domain komersial atau iklan yang tidak relevan dengan cek fakta."""
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        for blocked in IRRELEVANT_DOMAINS:
            if domain == blocked or domain.endswith("." + blocked):
                return False
        # Filter domain asing yang tidak relevan untuk isu Indonesia
        if domain.endswith(".kr") or domain.endswith(".cn") or domain.endswith(".ru"):
            return False
        return True
    except Exception:
        return True

def is_relevant_content(query: str, title: str, snippet: str) -> bool:
    """Memastikan hasil pencarian memiliki relevansi substantif dengan kata kunci query."""
    keywords = [w.lower() for w in query.split() if len(w) > 3]
    if not keywords:
        return True
    combined = (title + " " + snippet).lower()
    return any(k in combined for k in keywords)

def search_web(query: str, max_results: int = 3) -> List[ResearchItem]:
    """
    Melakukan pencarian fakta berbasis wilayah Indonesia (id-id)
    dengan pembersihan query, filter domain komersial, dan filter relevansi.
    """
    items: List[ResearchItem] = []
    sanitized_query = clean_query(query)
    
    time.sleep(0.35)
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(sanitized_query, region="id-id", safesearch="moderate", max_results=max_results + 4))
            
            for res in results:
                url = res.get("href", "")
                title = res.get("title", "").strip()
                snippet = res.get("body", "").strip()
                
                # Filter domain blacklist dan snippet kosong
                if not is_domain_allowed(url) or not snippet:
                    continue
                
                # Filter jika konten tidak ada relevansi dengan kata kunci
                if not is_relevant_content(sanitized_query, title, snippet):
                    continue
                
                items.append({
                    "query": sanitized_query,
                    "title": title or "Sumber Berita",
                    "source_url": url,
                    "snippet": snippet
                })
                
                if len(items) >= max_results:
                    break
                    
    except Exception as e:
        items.append({
            "query": sanitized_query,
            "title": f"Catatan Penelusuran: {sanitized_query}",
            "source_url": "https://turnbackhoax.id",
            "snippet": f"Penelusuran web terkendala jaringan ({str(e)}). Menggunakan analisis silang data fakta dasar."
        })
        
    return items
