import os
import logging
import asyncio
import json
import gspread
from playwright.async_api import async_playwright
from oauth2client.service_account import ServiceAccountCredentials

# 日誌設定
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
            
            # 使用 RAWDATA006208 分頁
            try:
                worksheet = sheet.worksheet("RAWDATA006208")
            except gspread.exceptions.WorksheetNotFound:
                worksheet = sheet.add_worksheet(title="RAWDATA006208", rows="2000", cols="10")
            
            worksheet.clear()
            worksheet.update(data)
            logger.info("✅ 成功同步 Fubon 資料至 RAWDATA006208")
        except Exception as e:
            logger.error(f"Google Sheets 寫入失敗: {e}")

    async def run(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                logger.info(f"前往: {self.target_url}")
                await page.goto(self.target_url, wait_until="networkidle")

                # 1. 關閉彈窗
                close_btn = page.locator("button.agree")
                if await close_btn.is_visible():
                    await close_btn.click()
                    await asyncio.sleep(2)
                    logger.info("彈窗已關閉")

                # 2. 提取表格資料 (針對您提供的結構)
                # 抓取 table1 類別底下的所有 tr，排除掉標題行
                data = await page.evaluate('''() => {
                    const rows = Array.from(document.querySelectorAll('table.table1 tbody tr'));
                    const results = [];
                    // 加入表頭
                    results.push(['代碼', '名稱', '數量', '金額', '權重']);
                    
                    rows.forEach(row => {
                        const cols = Array.from(row.querySelectorAll('td')).map(td => td.innerText.trim());
                        // 過濾掉無意義的空行或格式不符的行
                        if (cols.length >= 2 && !cols[0].includes('合計')) {
                            results.push(cols);
                        }
                    });
                    return results;
                }''')

                if len(data) > 1:
                    await self.save_to_sheets(data)
                else:
                    logger.warning("未抓取到有效資料，請檢查表格選取器")

            except Exception as e:
                logger.error(f"爬取錯誤: {e}")
            finally:
                await browser.close()

if __name__ == "__main__":
    scraper = FubonScraper("https://websys.fsit.com.tw/FubonETF/Fund/Assets.aspx?stkId=006208")
    asyncio.run(scraper.run())
