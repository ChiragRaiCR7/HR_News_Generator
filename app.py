import streamlit as st
from news_fetcher import HRNewsFetcher
from content_processor import ContentProcessor
import pandas as pd
import time
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="HR News Intelligence Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'news_data' not in st.session_state:
    st.session_state.news_data = pd.DataFrame()
if 'last_updated' not in st.session_state:
    st.session_state.last_updated = None

# Initialize classes
fetcher = HRNewsFetcher()
processor = ContentProcessor()

# UI Elements
st.title("📰 HR News Intelligence Dashboard")
st.caption("Stay updated with the latest HR trends, insights, and industry news")

# Sidebar controls
with st.sidebar:
    st.header("Configuration")
    keywords = st.text_input("HR Keywords", "HR trends, talent acquisition, employee engagement")
    max_results = st.slider("Max Results", 5, 50, 15)
    analyze_with_ai = st.toggle("AI Analysis", True)
    st.divider()
    
    if st.button("🔄 Refresh News", use_container_width=True):
        with st.spinner("Fetching latest news..."):
            # Fetch raw news
            raw_news = fetcher.fetch_latest_news(keywords.split(','), max_results)
            
            # Process with Gemini if enabled
            if analyze_with_ai:
                processed_news = []
                progress_bar = st.progress(0)
                for i, item in enumerate(raw_news):
                    processed_news.append(processor.process_news_item(item))
                    progress_bar.progress((i + 1) / len(raw_news))
            else:
                processed_news = raw_news
            
            # Create DataFrame
            df = pd.DataFrame(processed_news)
            
            # Add sentiment emoji
            df['sentiment'] = df['sentiment'].map({
                'positive': '😊 Positive',
                'negative': '😞 Negative',
                'neutral': '😐 Neutral'
            })
            
            # Store in session state
            st.session_state.news_data = df
            st.session_state.last_updated = datetime.now()
            
        st.success("News updated successfully!")
    
    st.divider()
    st.caption(f"Last updated: {st.session_state.last_updated or 'Never'}")

# Main content area
if st.session_state.news_data.empty:
    st.info("Click 'Refresh News' to load the latest HR news")
else:
    # Create tabs
    tab1, tab2 = st.tabs(["📰 News Feed", "📊 Insights"])
    
    with tab1:
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            sentiment_filter = st.multiselect(
                "Filter by sentiment",
                options=st.session_state.news_data['sentiment'].unique(),
                default=st.session_state.news_data['sentiment'].unique()
            )
        with col2:
            min_score = st.slider(
                "Min relevance score", 
                1, 10, 
                value=5
            )
        with col3:
            source_filter = st.multiselect(
                "Filter by source",
                options=st.session_state.news_data['source'].unique(),
                default=st.session_state.news_data['source'].unique()
            )
        
        # Apply filters
        filtered_df = st.session_state.news_data[
            (st.session_state.news_data['sentiment'].isin(sentiment_filter)) &
            (st.session_state.news_data['relevance_score'] >= min_score) &
            (st.session_state.news_data['source'].isin(source_filter))
        ]
        
        # Display news cards
        for _, row in filtered_df.iterrows():
            with st.expander(f"{row['title']} - **{row['source']}**"):
                col_left, col_right = st.columns([3, 1])
                with col_left:
                    st.markdown(f"**Summary**: {row['summary']}")
                    st.markdown(f"**Key Themes**: {', '.join(row['key_themes'])}")
                    st.markdown(f"**Sentiment**: {row['sentiment']}")
                    st.markdown(f"**Relevance Score**: {row['relevance_score']}/10")
                with col_right:
                    st.markdown(f"**Published**: {row['date']}")
                    st.link_button("Read Full Article", row['link'])
    
    with tab2:
        st.subheader("News Analysis")
        
        # Sentiment distribution
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Sentiment Distribution")
            sentiment_counts = st.session_state.news_data['sentiment'].value_counts()
            st.bar_chart(sentiment_counts)
        
        # Relevance scores
        with col2:
            st.markdown("### Relevance Scores")
            avg_score = st.session_state.news_data['relevance_score'].mean()
            st.metric("Average Relevance", f"{avg_score:.1f}/10")
            st.bar_chart(st.session_state.news_data['relevance_score'])
        
        # Theme word cloud
        st.markdown("### Popular Themes")
        all_themes = [theme for themes in st.session_state.news_data['key_themes'] for theme in themes]
        theme_counts = pd.Series(all_themes).value_counts().head(15)
        st.bar_chart(theme_counts)
        
        # Source analysis
        st.markdown("### Top Sources")
        source_counts = st.session_state.news_data['source'].value_counts().head(10)
        st.dataframe(source_counts)

# Footer
st.divider()
st.caption("Powered by SerpAPI and Google Gemini AI | Updated every 6 hours")
