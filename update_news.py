import os
import json
import feedparser
import google.generativeai as genai

# 1. 設定 Gemini API (從 GitHub 的保險箱讀取你那把 AQ. 開頭的鑰匙)
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# 使用免費且快速的 gemini-1.5-flash 模型
model = genai.GenerativeModel('gemini-1.5-flash')

# 2. 設定要抓取的 IT 新聞 RSS 來源 (以 TechCrunch 為例)
rss_url = "https://techCrunch.com/feed/"
feed = feedparser.parse(rss_url)

news_list = []

# 3. 抓取最新 5 則新聞
for entry in feed.entries[:5]:
    original_title = entry.title
    original_summary = entry.get('summary', '')
    link = entry.link
    published = entry.get('published', 'Today')

    # 4. 請 Gemini 進行繁體中文翻譯與總結
    prompt = f"""
    請將以下英文 IT 新聞總結並翻譯成吸引人的繁體中文：
    標題：{original_title}
    內容：{original_summary}

    請嚴格回傳一個 JSON 格式（不要包含 markdown 的 ```json 標籤），格式如下：
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
            "date": published
        })
    except Exception as e:
        print(f"AI 處理失敗: {e}")

# 5. 確保 data 資料夾存在，並把結果寫入 data/news.json
os.makedirs("data", exist_ok=True)
with open("data/news.json", "w", encoding="utf-8") as f:
    json.dump(news_list, f, ensure_ascii=False, indent=4)

print("新聞更新成功！")
