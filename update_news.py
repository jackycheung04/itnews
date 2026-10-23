    "Accept-Language": "en-US,en;q=0.9",
}
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
            print(f"📡 RSS 回應狀態碼: {resp.status_code}")
            if resp.status_code != 200:
                print(f"❌ 無法讀取 RSS (HTTP {resp.status_code}): {url}")
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
                published = getattr(entry, 'published', time.strftime("%Y-%m-%d"))

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

                

                print(f"📄 正在抓取新聞原文：{orig_title[:30]}...")
                article_text = get_article_text(link)

                if not article_text:
                    print("⏭️ 未能取得足夠原文，跳過這篇新聞")
                    continue

                print(f"🔄 正在核對來源並撰寫 ({category_name}): {orig_title[:30]}...")
                zh_title, zh_summary, zh_content = translate_text(
                    orig_title,
                    orig_summary,
                    link,
                    article_text
                )
                
                if zh_title and zh_summary and zh_content:
                    new_news_list.append({
                        "title": zh_title,
                        "summary": zh_summary,
                        "content": zh_content,
                        "link": link,
                        "image": image_url,
                        "date": published,
                        "category": category_name,
                        "is_manual": False,
                        "_archive_key": "rss:" + normalize_source_url(link)
                    })
                    existing_links.add(link)
                    cat_new_count += 1
                    time.sleep(3)

        except Exception as e:
            print(f"抓取 {url} 失敗: {e}")


# ----------------------------------------------------------------
# 4. 合併、建立永久文章頁及完整索引，再更新最新 50 篇新聞 JSON
# ----------------------------------------------------------------
# 排序邏輯：手動原創文章最優先 -> 新抓取的翻譯新聞 -> 舊有 RSS 新聞。
combined_news = manual_news_list + new_news_list + existing_rss_news

# 為所有可用文章建立永久網址和索引；這一步一定在截取最新 50 篇之前執行。
combined_news = update_permanent_archive(combined_news)

# 舊網站仍使用 data/news.json 的數字 id，暫時保留以維持相容；新文章連結會改用 permalink。
final_news = combined_news[:50]
for idx, item in enumerate(final_news):
    item["id"] = idx

if final_news:
    atomic_write_json(json_path, final_news)
    print(
        f"\n🚀 更新成功！載入 {len(manual_news_list)} 篇原創，新增 {len(new_news_list)} 篇翻譯，"
        f"目前最新清單保留 {len(final_news)} 篇；永久文章索引累積保存更多文章。"
    )
else:
    print("⚠️ 本次沒有可寫入的新聞；為保護資料，未覆寫 data/news.json。")
        f"目前最新清單保留 {len(final_news)} 篇；永久文章索引累積保存更多文章。"
    )
else:
    print("⚠️ 本次沒有可寫入的新聞；為保護資料，未覆寫 data/news.json。")
