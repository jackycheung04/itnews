import os
import json
import time
import re
import requests
import feedparser

# 1. 取得環境變數中的 API Key
api_key = os.environ.get("GEMINI_API_KEY")

# ⚠️ 故意將網址拆開，防止聊天視窗將其自動轉為 Markdown 連結，確保複製貼上絕對安全
API_HOST = "https://" + "generativelanguage.googleapis.com"

def get_available_models():
    """向 Google 查詢這個 API Key 實際能用的模型清單"""
    if not api_key:
        print("❌ 找不到 GEMINI_API_KEY 環境變數")
        return ['gemini-2.5-flash']
    
    url = f"{API_HOST}/v1beta/models?key={api_key}"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            models_data = res.json().get('models', [])
            valid_models = []
            for m in models_data:
                if 'generateContent' in m.get('supportedGenerationMethods', []):
                    name = m.get('name').replace('models/', '')
                    valid_models.append(name)
            
            print(f"✅ 您的 API Key 支援以下模型: {valid_models}")
            
            preferred = []
            for target in ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash']:
                if target in valid_models:
                    preferred.append(target)
                    
            if preferred:
                return preferred
            elif valid_models:
                return valid_models[:2] 
        else:
            print(f"⚠️ 獲取模型清單失敗 ({res.status_code})")
    except Exception as e:
        print(f"⚠️ 請求模型清單發生錯誤: {e}")
        
    return ['gemini-2.5-flash']

# 取得保證不會 404 的模型清單
MODELS_TO_TRY = get_available_models()
print(f"🎯 系統決定使用以下模型進行翻譯: {MODELS_TO_TRY}")

def translate_text(title, summary):
    if not api_key:
        return title, summary
        
    prompt = f"""
    請將以下英文 IT 新聞總結並翻譯成吸引人的繁體中文：
    標題：{title}
    內容：{summary}

    請嚴格回傳一個純 JSON 格式（不要包含 markdown 的 ```json 標籤），格式如下：
    {{"title": "繁體中文新聞標題", "summary": "150字左右的繁體中文核心總結"}}
    """
    
    for m_name in MODELS_TO_TRY:
        # 安全組裝 URL
        url = f"{API_HOST}/v1beta/models/{m_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        
        for attempt in range(2):
            try:
                res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=30)
                
                if res.status_code == 200:
                    data = res.json()
                    text = data['candidates'][0]['content']['parts'][0]['text'].strip()
                    
                    if text.startswith("```"):
                        text = re.sub(r"^```(?:json)?", "", text)
                        text = re.sub(r"```$", "", text).strip()
                    
                    try:
                        result = json.loads(text)
                        if "title" in result and "summary" in result:
                            print(f"✅ [{m_name}] 翻譯成功：{result['title']}")
                            return result["title"], result["summary"]
                    except json.JSONDecodeError:
                        print(f"⚠️ JSON 解析失敗，原始回傳: {text}")
                        return title, summary
                        
                elif res.status_code == 429:
                    wait_time = 15
                    print(f"⏳ [{m_name}] 觸發頻率限制，等待 {wait_time} 秒後重試...")
                    time.sleep(wait_time)
                else:
                    print(f"⚠️ [{m_name}] API 錯誤 ({res.status_code}): {res.text}")
                    break 
                    
            except Exception as e:
                print(f"⚠️ [{m_name}] 請求發生例外錯誤: {e}")
                break
                
    print("❌ 所有模型皆失敗，保留英文原文")
    return title, summary

# 2. 抓取 RSS (同樣拆開網址防止污染)
RSS_SOURCES = [
    "https://" + "techcrunch.com/feed/",
    "https://" + "rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "https://" + "www.wired.com/feed/category/gear/latest/rss"
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

entries = []
for url in RSS_SOURCES:
    # 雙重保險：強制清除可能殘留的 markdown 括號
    clean_url = url.replace("]", "").replace("[", "").replace(")", "").replace("(", "")
    print(f"嘗試抓取 RSS: {clean_url}")
    try:
        resp = requests.get(clean_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            feed = feedparser.parse(resp.text)
            if feed.entries:
                entries = feed.entries
                print(f"🎉 成功從 {clean_url} 抓取 {len(entries)} 則新聞！")
                break
    except Exception as e:
        print(f"抓取 {clean_url} 失敗: {e}")

# 3. 處理與翻譯
news_list = []
if entries:
    for idx, entry in enumerate(entries[:5]):
        orig_title = entry.get('title', '')
        orig_summary = entry.get('summary', entry.get('description', ''))
        link = entry.get('link', '#')
        published = entry.get('published', 'Today')

        image_url = "src/img/dummy/img2.jpg"
        if 'media_content' in entry and len(entry.media_content) > 0:
            image_url = entry.media_content[0].get('url', image_url)
            
        print(f"🔄 正在翻譯第 {idx+1}/5 篇...")
        zh_title, zh_summary = translate_text(orig_title, orig_summary)

        news_list.append({
            "title": zh_title,
            "summary": zh_summary,
            "link": link,
            "image": image_url,
            "date": published
        })

        if idx < 4:
            time.sleep(5)

# 4. 寫入檔案
os.makedirs("data", exist_ok=True)
if news_list:
    with open("data/news.json", "w", encoding="utf-8") as f:
        json.dump(news_list, f, ensure_ascii=False, indent=4)
    print(f"🚀 更新成功！共寫入 {len(news_list)} 則繁體中文新聞。")
