import json
import os
import re
import time
from bs4 import BeautifulSoup
import feedparser
import requests

api_key = os.environ.get("GEMINI_API_KEY")
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
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    name = m.get("name").replace("models/", "")
                    if name not in ["gemini-2.5-flash", "gemini-1.5-flash"]:
                        valid_models.append(name)

            print(f"✅ 可用模型清單: {valid_models}")

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

            return preferred if preferred else valid_models[:3]
    except Exception as e:
        print(f"⚠️ 請求模型清單發生錯誤: {e}")

    return ["gemini-2.0-flash-lite"]


MODELS_TO_TRY = get_available_models()


def get_real_image_url(article_url):
    """前往文章內頁抓取 og:image 或 twitter:image 高解析度封面圖"""
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

            og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
            if og_img and og_img.get("content"):
                return og_img["content"]

            tw_img = soup.find("meta", property="twitter:image") or soup.find("meta", attrs={"name": "twitter:image"})
            if tw_img and tw_img.get("content"):
                return tw_img["content"]
    except Exception as e:
        print(f"⚠️ 抓取網頁圖片失敗 ({article_url[:30]}...): {e}")

    return None


def translate_text(title, summary):
    if not api_key:
        return None, None, None

    prompt = f"""
    請針對以下英文科技新聞進行深度擴充與詳細報導（使用繁體中文）：
    原始標題：{title}
    原始摘要：{summary}

    請以專業科技記者角度，將此新聞擴充為約 800 至 1200 字的深度報導。

    內文（content）請包含以下四大面向並分段撰寫：
    1. 【事件背景與起因】
    2. 【核心細節與技術解析】
    3. 【產業影響與市場分析】
    4. 【未來展望與結語】

    請嚴格回傳純 JSON 格式（不要包含 markdown 的 ```json 標籤）：
    {{
        "title": "繁體中文新聞標題",
        "summary": "50字左右的簡明摘要",
        "content": "800-1200字的深度報導內文，各段落用換行分隔"
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
                    timeout=60,
                )

                if res.status_code == 200:
                    data = res.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()

                    if text.startswith("```"):
                        text = re.sub(r"^```(?:json)?", "", text)
                        text = re.sub(r"```$", "", text).strip()

                    try:
                        result = json.loads(text)
                        if "title" in result and "summary" in result:
                            print(f"✅ [{m_name}] 翻譯成功：{result['title']}")
                            return result["title"], result["summary"], result.get("content", result["summary"])
                    except json.JSONDecodeError:
                        print(f"⚠️ JSON 解析失敗，原始回傳: {text}")

                elif res.status_code == 429:
                    print(f"⏳ [{m_name}] 觸發頻率限制 (429)，等待 10 秒後重試...")
                    time.sleep(10)
                else:
                    break

            except Exception as e:
                print(f"⚠️ [{m_name}] 請求發生錯誤: {e}")
                break

    print("❌ 所有模型翻譯皆失敗")
    return None, None, None


# ----------------------------------------------------------------
# 1. 讀取舊新聞紀錄並自動補齊 category 欄位
# ----------------------------------------------------------------
os.makedirs("data", exist_ok=True)
json_path = "data/news.json"

existing_news = []
if os.path.exists(json_path):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            existing_news = json.load(f)
            # 相容性升級：確保舊資料都有 category 欄位
            for item in existing_news:
                if "category" not in item:
                    item["category"] = "Techno"
    except Exception as e:
        print(f"⚠️ 讀取舊新聞紀錄失敗: {e}")

existing_links = {item.get("link") for item in existing_news if item.get("link")}


# ----------------------------------------------------------------
# 2. 定義各分類及其對應的 RSS 來源
# ----------------------------------------------------------------
CATEGORIES_RSS = {
    "Techno": [
        "https://techcrunch.com/feed/",
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        "https://www.wired.com/feed/category/gear/latest/rss",
    ],
    "Ecosystem": [
        "https://www.techinasia.com/feed",
        "https://techcrunch.com/category/startups/feed/",
    ],
}

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
new_news_list = []
max_new_per_category = 3  # 每個分類每次最多抓取 3 篇新新聞


# ----------------------------------------------------------------
# 3. 分類抓取、去重與翻譯
# ----------------------------------------------------------------
for category_name, rss_urls in CATEGORIES_RSS.items():
    cat_new_count = 0
    print(f"\n==========================================")
    print(f"🔍 開始處理分類：[{category_name}]")
    print(f"==========================================")

    for url in rss_urls:
        if cat_new_count >= max_new_per_category:
            break

        print(f"嘗試抓取 RSS: {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue

            feed = feedparser.parse(resp.text)
            if not feed.entries:
                continue

            for entry in feed.entries:
                if cat_new_count >= max_new_per_category:
                    break

                link = entry.get("link", "#")

                # 去重檢查
                if link in existing_links:
                    print(f"⏩ 跳過已存在新聞: {entry.get('title')[:30]}...")
                    continue

                orig_title = entry.get("title", "")
                orig_summary = entry.get("summary", entry.get("description", ""))
                published = entry.get("published", "Today")

                print(f"\n📷 [{category_name} 新聞 {cat_new_count + 1}/{max_new_per_category}] 解析圖片中...")
                image_url = get_real_image_url(link)

                if not image_url:
                    if "media_content" in entry and len(entry.media_content) > 0:
                        image_url = entry.media_content[0].get("url")
                    elif "media_thumbnail" in entry and len(entry.media_thumbnail) > 0:
                        image_url = entry.media_thumbnail[0].get("url")
                    elif "enclosures" in entry and len(entry.enclosures) > 0:
                        image_url = entry.enclosures[0].get("href")

                if not image_url:
                    image_url = "src/img/dummy/img2.jpg"

                print(f"🔄 正在翻譯與擴寫 ({category_name}): {orig_title[:30]}...")
                zh_title, zh_summary, zh_content = translate_text(orig_title, orig_summary)

                if zh_title and zh_summary:
                    new_news_list.append({
                        "title": zh_title,
                        "summary": zh_summary,
                        "content": zh_content,
                        "link": link,
                        "image": image_url,
                        "date": published,
                        "category": category_name  # 🌟 標註所屬分類
                    })
                    existing_links.add(link)
                    cat_new_count += 1
                    time.sleep(3)

        except Exception as e:
            print(f"抓取 {url} 失敗: {e}")


# ----------------------------------------------------------------
# 4. 合併新舊資料、更新 ID 並存檔
# ----------------------------------------------------------------
combined_news = new_news_list + existing_news
final_news = combined_news[:50]  # 保留最新 50 篇

for idx, item in enumerate(final_news):
    item["id"] = idx

if final_news:
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_news, f, ensure_ascii=False, indent=4)
    print(f"\n🚀 更新成功！新增了 {len(new_news_list)} 篇新聞，目前資料庫共保留 {len(final_news)} 篇。")
