from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import requests
from bs4 import BeautifulSoup
import re
import os

app = Flask(__name__)
DB_FILE = "nexus_engine.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS web_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            content TEXT
        )
    ''')
    conn.commit()
    conn.close()

def scrape_and_index_url(target_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 NexusCrawler/1.0'}
        response = requests.get(target_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return False, f"Failed. Status code: {response.status_code}"
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup(["script", "style", "nav", "footer"]):
            element.decompose()
        title = soup.title.string.strip() if soup.title else target_url
        raw_text = soup.get_text(separator=' ')
        clean_content = re.sub(r'\s+', ' ', raw_text).strip()
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO web_pages (url, title, content)
            VALUES (?, ?, ?)
        ''', (target_url, title, clean_content))
        conn.commit()
        conn.close()
        return True, f"Successfully indexed: {title}"
    except Exception as e:
        return False, str(e)

def search_nexus(query):
    query_clean = query.lower().strip()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # This line searches without caring about uppercase or lowercase!
    cursor.execute("SELECT url, title, content FROM web_pages WHERE LOWER(content) LIKE ? OR LOWER(title) LIKE ?", ('%' + query_clean + '%', '%' + query_clean + '%'))
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for url, title, content in rows:
        score = 0
        if query_clean in title.lower():
            score += 15
        score += content.lower().count(query_clean)
        
        match_idx = content.lower().find(query_clean)
        if match_idx == -1:
            match_idx = 0
        start = max(0, match_idx - 40)
        end = min(len(content), match_idx + 120)
        snippet = "..." + content[start:end] + "..."
        results.append({"url": url, "title": title, "content": snippet, "score": score})
        
    return sorted(results, key=lambda x: x["score"], reverse=True)

@app.route('/')
def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.route('/static/style.css')
def serve_css():
    return send_from_directory('static', 'style.css')

@app.route('/search')
def api_search():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    return jsonify(search_nexus(query))

@app.route('/crawl', methods=['POST'])
def api_crawl():
    data = request.get_json()
    url_to_scrape = data.get('url', '')
    if not url_to_scrape:
        return jsonify({"success": False, "error": "No URL provided"}), 400
    success, message = scrape_and_index_url(url_to_scrape)
    return jsonify({"success": success, "message": message})

if __name__ == '__main__':
    init_db()
    print("Nexus Engine Database Ready.")
    app.run(debug=True, port=5000)