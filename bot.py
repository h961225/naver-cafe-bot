from pathlib import Path
import json
import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

BOARD_URLS = {
    2: "https://cafe.naver.com/f-e/cafes/30244990/menus/2",
    3: "https://cafe.naver.com/f-e/cafes/30244990/menus/3",
}

STATE_FILE = Path("last_posts.json")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=ko-KR")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return webdriver.Chrome(service=Service(), options=options)


def send_discord_message(content: str) -> None:
    if not WEBHOOK_URL:
        raise RuntimeError("DISCORD_WEBHOOK_URL 환경변수가 설정되지 않았습니다.")

    resp = requests.post(
        WEBHOOK_URL,
        json={"content": content},
        timeout=15,
    )
    resp.raise_for_status()


def get_latest_post(menu_id: int, url: str):
    print(f"\n🔧 get_latest_post(menu {menu_id})")
    driver = build_driver()

    try:
        driver.get(url)
        print("📄 게시판 접속 완료")

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.article-table tbody tr"))
        )
        print("⏳ 게시글 로딩 완료")

        rows = driver.find_elements(By.CSS_SELECTOR, "table.article-table tbody tr")
        print(f"📋 게시글 수: {len(rows)}")

        for row in rows:
            try:
                if row.find_elements(By.CSS_SELECTOR, "span.ico_notice"):
                    continue

                text = row.text.strip()
                if not text:
                    continue

                parts = text.split("\n")
                if len(parts) < 2:
                    continue

                article_id = parts[0].strip()
                title = parts[1].strip()

                if not article_id.isdigit():
                    continue

                post_url = (
                    f"https://cafe.naver.com/f-e/cafes/30244990/articles/"
                    f"{article_id}?menuid={menu_id}&referrerAllArticles=false"
                )

                print(f"📝 제목: {title}")
                print(f"🆔 article_id: {article_id}")
                print(f"🔗 링크: {post_url}")

                return {
                    "article_id": article_id,
                    "title": title,
                    "url": post_url,
                }

            except Exception as e:
                print(f"⚠️ 행 파싱 오류: {e}")

        return None

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return None

    finally:
        driver.quit()


def main():
    state = load_state()
    print("✅ 메뉴2 & 메뉴3 게시판 1회 확인 시작")

    for menu_id, url in BOARD_URLS.items():
        post = get_latest_post(menu_id, url)

        if not post:
            print(f"📭 메뉴 {menu_id}: 읽어온 게시글이 없습니다.")
            continue

        last_article_id = state.get(str(menu_id), "")
        current_article_id = post["article_id"]

        if current_article_id != last_article_id:
            message = f"📌 새 글: **{post['title']}**\n👉 {post['url']}"
            send_discord_message(message)
            state[str(menu_id)] = current_article_id
            print(f"✅ 메뉴 {menu_id}: 새 글 전송 완료")
        else:
            print(f"🔁 메뉴 {menu_id}: 이미 전송한 글입니다.")

    save_state(state)
    print("💾 상태 저장 완료")


if __name__ == "__main__":
    main()
