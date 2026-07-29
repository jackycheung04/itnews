import os
import json
import feedparser
import google.generativeai as genai

# 1. 設定 Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# 備選模型清單（按優先順序嘗試）
CANDIDATE_MODELS = ['gemini-2.0-flash', 'gemini-1.5-flash-latest', 'gemini-1.5-flash', 'gemini-1.5-pro']

def get_working_model():
    for model_name in CANDIDATE_MODELS:
        try:
            m = genai.GenerativeModel(model_name)
            return m, model_name
        except Exception:
            continue
    return genai.GenerativeModel('gemini-1.5-flash'), 'gemini-1.5-flash'

model, used_model_name = get_working_model()
print(f"目前使用的 AI 模型：{used_model_name}")

# 2. 設定 RSS 來源
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

    # 預設抓取圖片網址
    image_url = "src/img/dummy/img2.jpg"
    if 'media_content' in entry and len(entry.media_content) > 0:
        image_url = entry.media_content[0].get('url', image_url)
    elif 'links' in entry:
        for l in entry.links:
            if l.get('type', '').startswith('image/'):
                image_url = l.get('href', image_url)
                break

    # 預設使用原始英文資料（保底機制）
    final_title = original_title
    final_summary = original_summary

    # 4. 嘗試請 Gemini 進行繁體中文翻譯與總結
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
        if "```" in text_res:
            text_res = text_res.split("```")[1]
            if text_res.startswith("json"):
                text_res = text_res[4:].strip()
        
        ai_data = json.loads(text_res.strip())
        final_title = ai_data.get("title", original_title)
        final_summary = ai_data.get("summary", original_summary)
        print(f"✅ AI 成功翻譯：{final_title}")
    except Exception as e:
        print(f"⚠️ AI 處理失敗，改用原始新聞內容：{e}")

    # ⚠️ 關鍵修正：不論 AI 是否成功，都一定會將新聞寫入清單！
    news_list.append({
        "title": final_title,
        "summary": final_summary,
        "link": link,
        "image": image_url,
        "date": published
    })

# 5. 寫入 data/news.json
os.makedirs("data", exist_ok=True)
with open("data/news.json", "w", encoding="utf-8") as f:
    json.dump(news_list, f, ensure_ascii=False, indent=4)

print(f"🎉 新聞更新成功！共寫入 {len(news_list)} 則新聞至 news.json")
# 5. 寫入 data/news.json
os.makedirs("data", exist_ok=True)
with open("data/news.json", "w", encoding="utf-8") as f:
    json.dump(news_list, f, ensure_ascii=False, indent=4)

print(f"新聞更新成功！共寫入 {len(news_list)} 則新聞至 news.json")
