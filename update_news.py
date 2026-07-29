import os
import json
import feedparser
import google.generativeai as genai

# 1. 設定 Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

MODELS_TO_TRY = ['gemini-2.0-flash', 'gemini-1.5-flash-latest', 'gemini-1.5-pro']

def translate_with_gemini(title, summary):
    prompt = f"""
    請將以下英文 IT 新聞總結並翻譯成吸引人的繁體中文：
    標題：{title}
    內容：{summary}

    請嚴格回傳一個純 JSON 格式（不要包含 markdown 的 ```json 標籤），格式如下：
    {{"title": "繁體中文新聞標題", "summary": "150字左右的繁體中文核心總結"}}
    """
    for model_name in MODELS_TO_TRY:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            text_res = response.text.strip()
            if "```" in text_res:
                text_res = text_res.split("```")[1]
                if text_res.startswith("json"):
                    text_res = text_res[4:].strip()
            data = json.loads(text_res.strip())
            return data.get("title", title), data.get("summary", summary)
        except Exception as e:
            print(f"模型 {model_name} 翻譯失敗，嘗試下一個模型... 錯誤: {e}")
            continue
    return title, summary # 若所有模型皆失敗才使用英文保底

# 2. 抓取 RSS
rss_url = "[https://techcrunch.com/feed/](https://techcrunch.com/feed/)"
feed = feedparser.parse(rss_url, agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

print(f"成功抓取 RSS，共有 {len(feed.entries)} 則新聞")

news_list = []

# 3. 處理前 5 則新聞
for entry in feed.entries[:5]:
    orig_title = entry.title
    orig_summary = entry.get('summary', '')
    link = entry.link
    published = entry.get('published', 'Today')

    image_url = "src/img/dummy/img2.jpg"
    if 'media_content' in entry and len(entry.media_content) > 0:
        image_url = entry.media_content[0].get('url', image_url)
    elif 'links' in entry:
        for l in entry.links:
            if l.get('type', '').startswith('image/'):
                image_url = l.get('href', image_url)
                break

    # 執行翻譯
    zh_title, zh_summary = translate_with_gemini(orig_title, orig_summary)

    news_list.append({
        "title": zh_title,
        "summary": zh_summary,
        "link": link,
        "image": image_url,
        "date": published
    })

# 4. 寫入 JSON
os.makedirs("data", exist_ok=True)
with open("data/news.json", "w", encoding="utf-8") as f:
    json.dump(news_list, f, ensure_ascii=False, indent=4)

print(f"🎉 新聞更新成功！共寫入 {len(news_list)} 則新聞至 news.json")
