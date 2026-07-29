import os
import json
import feedparser
import google.generativeai as genai

# 1. 設定 Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# 使用 gemini-1.5-flash 模型
model = genai.GenerativeModel('gemini-1.5-flash')

# 2. 設定 RSS 來源（加上 User-Agent 避免被網站阻擋）
rss_url = "https://techcrunch.com/feed/"
feed = feedparser.parse(rss_url, agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

print(f"成功抓取 RSS，共有 {len(feed.entries)} 則新聞")

news_list = []

# 3. 處理前 5 則新聞
for entry in feed.entries[:5]:
    original_title = entry.title
    original_summary = entry.get('summary', '')
    link = entry.link
    published = entry.get('published', 'Today')

    # 嘗試抓取圖片網址（若抓不到則使用預設圖）
    image_url = "src/img/dummy/img2.jpg"
    if 'media_content' in entry and len(entry.media_content) > 0:
        image_url = entry.media_content[0].get('url', image_url)
    elif 'links' in entry:
        for l in entry.links:
            if l.get('type', '').startswith('image/'):
                image_url = l.get('href', image_url)
                break

    # 4. 請 Gemini 進行繁體中文翻譯與總結
    prompt = f"""
    請將以下英文 IT 新聞總結並翻譯成吸引人的繁體中文：
    標題：{original_title}
    內容：{original_summary}

    請嚴格回傳一個純 JSON 格式（不要包含 markdown 的 ```json 標籤），格式如下：
    {{"title": "繁體中文新聞標題", "summary": "150字左右的繁體中文核心總結"}}
    """

    try:
        response = model.generate_content(prompt)
        text_res = response.text.strip()
        
        # 清理可能包覆的 markdown 符號
        if text_res.startswith("```"):
            text_res = text_res.split("```")[1]
            if text_res.startswith("json"):
                text_res = text_res[4:]
        
        ai_data = json.loads(text_res.strip())
        
        news_list.append({
            "title": ai_data.get("title", original_title),
            "summary": ai_data.get("summary", original_summary),
            "link": link,
            "image": image_url,
            "date": published
        })
        print(f"成功處理新聞：{ai_data.get('title')}")
    except Exception as e:
        print(f"處理新聞『{original_title}』失敗: {e}")

# 5. 確保 data 資料夾存在，並寫入 data/news.json
os.makedirs("data", exist_ok=True)
with open("data/news.json", "w", encoding="utf-8") as f:
    json.dump(news_list, f, ensure_ascii=False, indent=4)

print(f"新聞更新成功！共寫入 {len(news_list)} 則新聞至 news.json")
