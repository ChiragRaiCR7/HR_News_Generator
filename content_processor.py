import google.generativeai as genai
import os
from dotenv import load_dotenv
import streamlit as st
import json
import re

load_dotenv()

class ContentProcessor:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            st.error("GEMINI_API_KEY not found in environment variables")
            return
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.prompt_template = """
        Analyze the following HR news article and provide:
        1. A concise 1-sentence summary
        2. 3-5 key themes/topics (as a JSON list)
        3. Sentiment analysis (positive/negative/neutral)
        4. Relevance score to HR professionals (1-10 integer)
        
        Article content: 
        Title: {title}
        {snippet}
        
        Respond in strict JSON format only:
        {{
            "summary": "...",
            "key_themes": ["theme1", "theme2", ...],
            "sentiment": "...",
            "relevance_score": ...
        }}
        """

    def process_news_item(self, news_item):
        """Enhance news item with Gemini analysis"""
        if not hasattr(self, 'model'):
            return news_item  # Skip if initialization failed
            
        try:
            prompt = self.prompt_template.format(
                title=news_item['title'],
                snippet=news_item['snippet']
            )
            
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                return news_item
                
            json_str = json_match.group(0)
            analysis = json.loads(json_str)
            
            # Merge with news item
            return {
                **news_item,
                'summary': analysis.get('summary', ''),
                'key_themes': analysis.get('key_themes', []),
                'sentiment': analysis.get('sentiment', 'neutral').lower(),
                'relevance_score': analysis.get('relevance_score', 5)
            }
            
        except Exception as e:
            st.error(f"Error processing news item: {str(e)}")
            return news_item
