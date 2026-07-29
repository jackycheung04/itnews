import os
import json
import time
import re
import requests
import feedparser
from google import genai
from google.genai import errors

# 1. 初始化新版 Gemini API Client
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# 當前官方標準模型名稱
MODELS = ['gemini-2.0-flash', 'gemini-1.5-flash']

def translate_text(title, summary):
    prompt = f"""
    請將以下英文 IT 新聞總結並翻譯成吸引人的繁體中文：
    標題：{title}
    內容：{summary}

    請嚴格回傳一個純 JSON 格式（不要包含 markdown 的 ```json 標籤），格式如下：
    {{"title": "繁體中文新聞標題", "summary": "150字左右的繁體中文核心總結"}}
    """
    
    for m_name in MODELS:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=m_name,
                    contents=prompt
                )
                text = response.text.strip()
                
                # 清除 markdown codeblock 標籤
                if "```" in text:
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:].strip()
                
                # 嘗試解析 JSON
                data = json.loads(text.strip())
                if "title" in data and "summary" in data:
                    print(f"✅ AI 模型 [{m_name}] 翻譯成功：{data['title']}")
                    return data["title"], data["summary"]
            
            except errors.APIError as e:
                # 針對 429 超過速率限制進行自動等待重試
                if getattr(e, 'code', None) == 429 or "429" in str(e):
                    wait_time = 20 * (attempt + 1)
                    print(f"⏳ 觸發 API 頻率限制 (429)，自動等待 {wait_time} 秒後進行第 {attempt + 1} 次重試...")
                    time.sleep(wait_time)
                else:
                    print(f"⚠️ 模型 {m_name} API 錯誤: {e}")
                    break
            except Exception as e:
                print(f"⚠️ 模型 {m_name} 解析或處理失敗: {e}")
                break

    print("❌ 所有 AI 模型與重試皆嘗試完畢，暫時改用英文原文")
    return title, summary

# 2. RSS 來源設定
RSS_SOURCES = [
    "https://techcrunch.com/feed/",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "https://www.wired.com/feed/category/gear/latest/rss"
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

entries = []
for url in RSS_SOURCES:
    clean_url = url
    if "](" in url:
        clean_url = url.split("](")[-1].replace(")", "")
        
    print(f"嘗試抓取 RSS: {clean_url}")
    try:
        resp = requests.get(clean_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            feed = feedparser.parse(resp.text)
            if feed.entries and len(feed.entries) > 0:
                entries = feed.entries
                print(f"🎉 成功從 {clean_url} 抓取到 {len(entries)} 則新聞！")
                break
            else:
                print(f"⚠️ {clean_url} 回傳內容不包含新聞文章")
        else:
            print(f"⚠️ {clean_url} 回傳 HTTP 狀態碼 {resp.status_code}")
    except Exception as e:
        print(f"抓取 {clean_url} 失敗: {e}")

news_list = []

# 3. 處理新聞並進行翻譯
if entries:
    for idx, entry in enumerate(entries[:5]):
        orig_title = entry.get('title', '')
        orig_summary = entry.get('summary', entry.get('description', ''))
        link = entry.get('link', '#')
        published = entry.get('published', 'Today')

        image_url = "src/img/dummy/img2.jpg"
        if 'media_content' in entry and len(entry.media_content) > 0:
            image_url = entry.media_content[0].get('url', image_url)
        elif 'links' in entry:
            for l in entry.links:
                if l.get('type', '').startswith('image/'):
                    image_url = l.get('href', image_url)
                    break

        # AI 翻譯處理
        zh_title, zh_summary = translate_text(orig_title, orig_summary)

        news_list.append({
            "title": zh_title,
            "summary": zh_summary,
            "link": link,
            "image": image_url,
            "date": published
        })

        # 新聞間間隔 15 秒，避免連續請求觸發免費額度紅線
        if idx < 4:
            time.sleep(15)

# 4. 寫入 JSON 檔案
os.makedirs("data", exist_ok=True)
if news_list:
    with open("data/news.json", "w", encoding="utf-8") as f:
        json.dump(news_list, f, ensure_ascii=False, indent=4)
    print(f"🚀 新聞更新成功！共寫入 {len(news_list)} 則繁體中文新聞。")
else:
    print("⚠️ 這次沒有抓取到任何新聞，保持舊檔案，不覆蓋 news.json！")
