# HR News Generator

A Streamlit application that aggregates and displays the latest HR news using SerpAPI and Gemini API. This solution provides a clean, interactive dashboard for HR professionals to stay updated with industry trends.

## Features

1. **Real-time News Aggregation**:
   - Fetches latest HR news from multiple sources
   - Supports custom keyword searches
   - Configurable result limits

2. **AI-Powered Analysis**:
   - Automatic summarization of articles
   - Sentiment analysis (positive/negative/neutral)
   - Relevance scoring for HR professionals
   - Key theme extraction

3. **Interactive Dashboard**:
   - News cards with expandable details
   - Filtering by sentiment, source, and relevance
   - Visual analytics of news trends
   - Responsive design for all devices

4. **Insightful Visualizations**:
   - Sentiment distribution charts
   - Relevance score analysis
   - Popular theme tracking
   - Source credibility metrics

## Setup Instructions

1. Clone the repository:
```bash
git clone [repository-url]
cd [repository-name]
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your environment variables:
   - Create a `.env` file in the root directory
   - Add your API keys:
```env
SERPAPI_KEY=your_serpapi_key_here
GEMINI_API_KEY=your_gemini_key_here
```

4. Run the application:
```bash
streamlit run app.py
```

## Project Structure

```
📂 hr_news_dashboard/
├── 📜 app.py                 # Main Streamlit application
├── 📜 news_fetcher.py        # SerpAPI news fetcher
├── 📜 content_processor.py   # Gemini content analyzer
├── 📜 .env                   # API keys
└── 📜 requirements.txt       # Dependencies
```

## Usage

1. Start the application using `streamlit run app.py`
2. Enter your desired HR-related keywords in the sidebar
3. Adjust the maximum number of results to fetch
4. Toggle AI analysis on/off as needed
5. Click "Refresh News" to fetch and analyze the latest articles
6. Use the filters to narrow down the results
7. Explore the insights tab for data visualizations

## Dependencies

- streamlit==1.33.0
- pandas==2.2.2
- python-dotenv==1.0.1
- google-generativeai==0.8.4
- serpapi==1.7.0
- plotly==5.22.0

## API Keys Required

1. **SerpAPI Key**: Sign up at [SerpApi](https://serpapi.com/)
2. **Gemini API Key**: Get your key from [Google AI Studio](https://ai.google.dev/)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
Latest HR news using AI-powered research, content generation, and optimization."
>>>>>>> 42a61ce0e4bfdf33071d8fa738d7180b873d1fb9
