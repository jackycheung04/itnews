import json
import os
import re
import time
from bs4 import BeautifulSoup
import feedparser
import requests

api_key = os.environ.get("GEMINI_API_KEY")

# 安全組裝 API Host 避免 Markdown 污染
API_HOST = "https://" + "generativelanguage.googleapis.com"


def get_available_models():
    """向 Google 查詢模型，並智慧過濾掉舊版本"""
    if not api_key:
        print("❌ 找不到 GEMINI_API_KEY 環境變數")
        return ["gemini-2.0-flash-lite"]

    url = f"{API_HOST}/v1beta/models?key={api_key}"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            models_data = res.json().get("models", [])
            valid_models = []
            for m in models_data:
                if "generateContent" in m.get(
                    "supportedGenerationMethods", []
                ):
                    name = m.get("name").replace("models/", "")
                    if name not in ["gemini-2.5-flash", "gemini-1.5-flash"]:
                        valid_models.append(name)

            print(
                f"✅ 您的 API Key 實際可用模型清單 (已過濾): {valid_models}"
            )

            preferred = []
            target_list = [
                "gemini-3.1-flash-lite",
                "gemini-3.0-flash-lite",
                "gemini-2.0-flash-lite",
                "gemini-3.1-pro-preview",
                "gemini-2.0-flash",
            ]
            for target in target_list:
                if target in valid_models:
                    preferred.append(target)

            if preferred:
                return preferred
            elif valid_models:
                return valid_models[:3]
        else:
            print(f"⚠️ 獲取模型清單失敗 ({res.status_code})")
    except Exception as e:
        print(f"⚠️ 請求模型清單發生錯誤: {e}")

    return ["gemini-2.0-flash-lite"]


MODELS_TO_TRY = get_available_models()
print(f"🎯 系統決定優先使用以下模型進行翻譯: {MODELS_TO_TRY}")


def get_real_image_url(article_url):
    """🎯 核心新增：前往文章內頁抓取 og:image 或 twitter:image 高解析度封面圖"""
    if not article_url or article_url == "#":
        return None

    try:
        req_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(article_url, headers=req_headers, timeout=5)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")

            # 1. 優先抓取 og:image
            og_img = soup.find("meta", property="og:image") or soup.find(
                "meta", attrs={"name": "og:image"}
            )
            if og_img and og_img.get("content"):
                return og_img["content"]

            # 2. 次選 twitter:image
            tw_img = soup.find("meta", property="twitter:image") or soup.find(
                "meta", attrs={"name": "twitter:image"}
            )
            if tw_img and tw_img.get("content"):
                return tw_img["content"]
    except Exception as e:
        print(f"⚠️ 抓取網頁圖片失敗 ({article_url[:30]}...): {e}")

    return None


def translate_text(title, summary):
    if not api_key:
        return title, summary, summary

   prompt = f"""
    請將以下英文 IT 新聞總結並翻譯成繁體中文：
    標題：{title}
    內容：{summary}

    請嚴格回傳一個純 JSON 格式（不要包含 markdown 的 ```json 標籤），格式如下：
    {{
        "title": "繁體中文新聞標題",
        "summary": "50字左右的簡明摘要 (供列表卡片使用)",
        "content": "300-500字詳細的繁體中文新聞內文，分2-3個段落，用換行分隔"
    }}
    """

    for m_name in MODELS_TO_TRY:
        url = f"{API_HOST}/v1beta/models/{m_name}:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        for attempt in range(2):
            try:
                res = requests.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30,
                )

                if res.status_code == 200:
                    data = res.json()
                    text = data["candidates"][0]["content"]["parts"][0][
                        "text"
                    ].strip()

                    if text.startswith("```"):
                        text = re.sub(r"^```(?:json)?", "", text)
                        text = re.sub(r"```$", "", text).strip()

                    try:
                        result = json.loads(text)
                        if "title" in result and "summary" in result:
                            print(
                                f"✅ [{m_name}] 翻譯成功：{result['title']}"
                            )
                            return result["title"], result["summary"], result.get("content", result["summary"])
                    except json.JSONDecodeError:
                        print(f"⚠️ JSON 解析失敗，原始回傳: {text}")
                        return title, summary, summary

                elif res.status_code == 429:
                    wait_time = 15
                    print(
                        f"⏳ [{m_name}] 觸發頻率限制 (429)，等待 {wait_time}"
                        " 秒後重試..."
                    )
                    time.sleep(wait_time)
                else:
                    print(
                        f"⚠️ [{m_name}] API 錯誤 ({res.status_code}):"
                        f" {res.text}"
                    )
                    break

            except Exception as e:
                print(f"⚠️ [{m_name}] 請求發生例外錯誤: {e}")
                break

    print("❌ 所有模型皆失敗，保留英文原文")
    return title, summary, summary


RSS_SOURCES = [
    "https://" + "techcrunch.com/feed/",
    "https://" + "rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "https://" + "www.wired.com/feed/category/gear/latest/rss",
]

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
}

entries = []
for url in RSS_SOURCES:
    clean_url = (
        url.replace("]", "").replace("[", "").replace(")", "").replace("(", "")
    )
    print(f"嘗試抓取 RSS: {clean_url}")
    try:
        resp = requests.get(clean_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            feed = feedparser.parse(resp.text)
            if feed.entries:
                entries = feed.entries
                print(
                    f"🎉 成功從 {clean_url} 抓取 {len(entries)} 則新聞！"
                )
                break
    except Exception as e:
        print(f"抓取 {clean_url} 失敗: {e}")

news_list = []
if entries:
    for idx, entry in enumerate(entries[:5]):
        orig_title = entry.get("title", "")
        orig_summary = entry.get("summary", entry.get("description", ""))
        link = entry.get("link", "#")
        published = entry.get("published", "Today")

        print(f"📷 正在解析第 {idx+1}/5 篇真實圖片...")
        # 1. 優先爬取網頁 Meta (og:image / twitter:image)
        image_url = get_real_image_url(link)

        # 2. 若網頁沒抓到，退回檢查 RSS 結構中的圖片標籤
        if not image_url:
            if "media_content" in entry and len(entry.media_content) > 0:
                image_url = entry.media_content[0].get("url")
            elif "media_thumbnail" in entry and len(entry.media_thumbnail) > 0:
                image_url = entry.media_thumbnail[0].get("url")
            elif "enclosures" in entry and len(entry.enclosures) > 0:
                image_url = entry.enclosures[0].get("href")

        # 3. 最終備用圖
        if not image_url:
            image_url = "src/img/dummy/img2.jpg"

        print(f"🔄 正在翻譯第 {idx+1}/5 篇...")
        zh_title, zh_summary, zh_content = translate_text(orig_title, orig_summary)

        news_list.append(
    {
        "title": zh_title,
        "summary": zh_summary,
        "content": zh_content,
        "link": link,
        "image": image_url,
        "date": published,
    }
)

        if idx < 4:
            time.sleep(5)

os.makedirs("data", exist_ok=True)
json_path = "data/news.json"

existing_news = []
if os.path.exists(json_path):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            existing_news = json.load(f)
    except Exception as e:
        print(f"⚠️ 讀取舊新聞紀錄失敗: {e}")

existing_titles = {item["title"] for item in existing_news}
unique_new_items = [
    item for item in news_list if item["title"] not in existing_titles
]

combined_news = unique_new_items + existing_news
final_news = combined_news[:50]

if final_news:
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_news, f, ensure_ascii=False, indent=4)
    print(
        f"🚀 更新成功！新增 {len(unique_new_items)} 篇，共累積"
        f" {len(final_news)} 篇新聞。"
    )
