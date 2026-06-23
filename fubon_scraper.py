import os
import logging
import asyncio
import json
import gspread
from playwright.async_api import async_playwright
from oauth2client.service_account import ServiceAccountCredentials

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("FubonScraper")

class FubonScraper:
    def __init__(self, target_url: str):
        self.target_url = target_url
        self.sheet_id = os.environ.get("SHEET_ID")
        self.creds_json = os.environ.get("GSPREAD_JSON")

    async def save_to_sheets(self, data):
        try:
            creds_dict = json.loads(self.creds_json)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ])
            client = gspread.authorize(creds)
            sheet = client.open_by_key(self.sheet_id)
            
            # 確保 RAWDATA 分頁存在
            try:
                worksheet = sheet.worksheet("RAWDATA006208")
            except gspread.exceptions.WorksheetNotFound:
                worksheet = sheet.add_worksheet(title="RAWDATA", rows="1000", cols="20")
            
            worksheet.clear()
            worksheet.update(data)
            logger.info("✅ 成功同步 Fubon 資料至 RAWDATA")
        except Exception as e:
            logger.error(f"Google Sheets 寫入失敗: {e}")

    async def run(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                logger.info(f"前往: {self.target_url}")
                await page.goto(self.target_url, wait_until="networkidle")

                # 1. 關閉彈出視窗
                close_btn = page.locator("button.agree")
                if await close_btn.is_visible():
                    await close_btn.click()
                    await asyncio.sleep(1)
                    logger.info("彈窗已關閉")

                # 2. 爬取網頁資料 (對應您提供的 XPath 路徑)
                # 這裡使用 page.evaluate 讀取該 div 內的表格內容
                data = await page.evaluate('''() => {
                    const table = document.querySelector('/html/body/form/article/div/div/div/div[2]/div[3]/div[2]');
                    // 此處假設內容結構為 table 或 div 列表，需根據實際 HTML 調整解析邏輯
                    const rows = Array.from(document.querySelectorAll('.data-row-selector')); 
                    return rows.map(row => Array.from(row.querySelectorAll('td')).map(td => td.innerText.trim()));
                }''')

                # 若需透過點擊下載按鈕處理 (如果網站是透過下載 CSV 處理)
                # await page.locator("#mainContent_subMainContent_btnDownload").click()
                
                if data:
                    await self.save_to_sheets(data)

            except Exception as e:
                logger.error(f"爬取錯誤: {e}")
            finally:
                await browser.close()

if __name__ == "__main__":
    scraper = FubonScraper("https://websys.fsit.com.tw/FubonETF/Fund/Assets.aspx?stkId=006208")
    asyncio.run(scraper.run())
