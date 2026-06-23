import os
import logging
import asyncio
import json
import gspread
from datetime import datetime
from playwright.async_api import async_playwright
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 【專業日誌設定】
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)
logger = logging.getLogger("YuantaRatioScraper")

class YuantaRatioScraper:
    def __init__(self, target_url: str):
        self.target_url = target_url
        # 從環境變數讀取 Google Sheets 設定
        self.sheet_id = os.environ.get("SHEET_ID")
        self.creds_json = os.environ.get("GSPREAD_JSON")

    async def save_to_sheets(self, data):
        """將資料寫入指定的 Google Sheets RAWDATA 分頁"""
        try:
            logger.info("準備連接 Google Sheets...")
            creds_dict = json.loads(self.creds_json)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ])
            client = gspread.authorize(creds)
            
            # 開啟指定的試算表
            sheet = client.open_by_key(self.sheet_id)
            
            # 獲取或建立 RAWDATA 分頁
            try:
                worksheet = sheet.worksheet("RAWDATA")
            except gspread.exceptions.WorksheetNotFound:
                worksheet = sheet.add_worksheet(title="RAWDATA", rows="1000", cols="20")
            
            # 清除舊資料並寫入新資料
            worksheet.clear()
            worksheet.update(data)
            logger.info("✅ 成功同步資料至 Google Sheets [RAWDATA] 分頁")
            
        except Exception as e:
            logger.error(f"寫入 Google Sheets 失敗: {e}")

    async def run(self):
        async with async_playwright() as p:
            logger.info("啟動瀏覽器核心...")
            browser = await p.chromium.launch(headless=True) # GitHub Actions 環境建議用 headless
            page = await browser.new_page()

            try:
                logger.info(f"前往: {self.target_url}")
                await page.goto(self.target_url, wait_until="networkidle")

                # 1. 點擊展開
                expand_btn = page.locator("div.moreBtn").first
                if await expand_btn.is_visible():
                    logger.info("執行展開渲染...")
                    await expand_btn.click()
                    await asyncio.sleep(3) 
                
                # 2. 提取資料
                extracted_data = await page.evaluate('''() => {
                    const rows = document.querySelectorAll('.tbody .tr');
                    const data = [['商品代碼', '商品名稱', '商品數量', '商品權重']];
                    rows.forEach(row => {
                        const tds = row.querySelectorAll('.td');
                        const rowData = Array.from(tds).map(td => {
                            const spans = td.querySelectorAll('span');
                            return spans.length > 1 ? spans[1].innerText.trim() : td.innerText.trim();
                        });
                        data.push(rowData);
                    });
                    return data;
                }''')

                # 3. 寫入 Google Sheets
                if len(extracted_data) > 1:
                    await self.save_to_sheets(extracted_data)
                else:
                    logger.warning("未抓取到資料。")

            except Exception as e:
                logger.error(f"執行期間發生錯誤: {e}")
            finally:
                await browser.close()

if __name__ == "__main__":
    scraper = YuantaRatioScraper(
        target_url="https://www.yuantaetfs.com/product/detail/0050/ratio"
    )
    asyncio.run(scraper.run())
