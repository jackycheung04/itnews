import os
import json
import requests
import feedparser
import google.generativeai as genai

# 1. 設定 Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

MODELS = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro']

def translate_text(title, summary):
    prompt = f"""
    請將以下英文 IT 新聞總結並翻譯成吸引人的繁體中文：
    標題：{title}
    內容：{summary}

    請嚴格回傳一個純 JSON 格式（不要包含 markdown 的 ```json 標籤），格式如下：
    {{"title": "繁體中文新聞標題", "summary": "150字左右的繁體中文核心總結"}}
    """
    for m_name in MODELS:
        try:
            model = genai.GenerativeModel(m_name)
            res = model.generate_content(prompt)
            text = res.text.strip()
            
            # 清除 markdown codeblock 標籤
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:].strip()
            
            data = json.loads(text.strip())
            if "title" in data and "summary" in data:
                print(f"✅ AI 模型 [{m_name}] 翻譯成功：{data['title']}")
                return data["title"], data["summary"]
        except Exception as e:
            print(f"⚠️ 模型 {m_name} 嘗試失敗: {e}")
            continue
            
    print("❌ 所有 AI 模型皆失敗，暫時改用英文原文")
    return title, summary

# 2. 設定 RSS 來源與完整瀏覽器請求頭
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
    # 🧹 自動清除複製貼上可能產生的 Markdown 超連結格式
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

# 3. 處理新聞
if entries:
    for entry in entries[:5]:
        orig_title = entry.get('title', '')
        orig_summary = entry.get('summary', entry.get('description', ''))
        link = entry.get('link', '#')
        published = entry.get('published', 'Today')

        # 嘗試抓取圖片網址
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

# 4. 寫入 data/news.json
os.makedirs("data", exist_ok=True)
if news_list:
    with open("data/news.json", "w", encoding="utf-8") as f:
        json.dump(news_list, f, ensure_ascii=False, indent=4)
    print(f"🚀 新聞更新成功！共寫入 {len(news_list)} 則繁體中文新聞。")
else:
    print("⚠️ 這次沒有抓取到任何新聞，保持舊檔案，不覆蓋 news.json！")
