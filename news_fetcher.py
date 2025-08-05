from serpapi import GoogleSearch
import os
from dotenv import load_dotenv
import streamlit as st
import re

load_dotenv()

class HRNewsFetcher:
    def __init__(self):
        self.api_key = os.getenv("SERPAPI_KEY")
        
    def fetch_latest_news(self, keywords, max_results=15):
        """Fetch latest HR-related news from SerpAPI"""
        if not self.api_key:
            st.error("SERPAPI_KEY not found in environment variables")
            return []
        
        news_items = []
        unique_urls = set()
        
        for keyword in keywords:
            keyword = keyword.strip()
            if not keyword:
                continue
                
            try:
                params = {
                    "q": keyword,
                    "tbm": "nws",
                    "api_key": self.api_key,
                    "num": max(3, max_results // len(keywords)),
                    "hl": "en",
                    "gl": "us"
                }
                
                search = GoogleSearch(params)
                results = search.get_dict().get('news_results', [])
                
                for item in results:
                    # Basic validation
                    if not item.get('link') or item['link'] in unique_urls:
                        continue
                    
                    # Clean date format
                    date = item.get('date', '')
                    if 'ago' in date:
                        date = self._convert_relative_date(date)
                    
                    news_items.append({
                        'title': item.get('title', 'Untitled'),
                        'source': self._clean_source(item.get('source', {}).get('name', 'Unknown')),
                        'link': item['link'],
                        'snippet': item.get('snippet', ''),
                        'date': date
                    })
                    unique_urls.add(item['link'])
                    
                    if len(news_items) >= max_results:
                        break
                        
            except Exception as e:
                st.error(f"Error fetching news for '{keyword}': {str(e)}")
        
        return news_items[:max_results]
    
    def _clean_source(self, source):
        """Clean source name"""
        return re.sub(r'·|\||-', '', source).strip()
    
    def _convert_relative_date(self, relative_date):
        """Convert relative dates to absolute dates"""
        if 'hour' in relative_date:
            return "Today"
        if 'day' in relative_date:
            return "Yesterday" if '1 day' in relative_date else "This week"
        return relative_date
