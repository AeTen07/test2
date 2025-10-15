# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import re
import time

# -----------------------------
# Selenium headless 設定，不開啟瀏覽器畫面
# -----------------------------
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(options=options)

# -----------------------------
# 設定目標網址
# -----------------------------
city = "Taichung-city"
page = 1

all_properties = []

while True:
    url = f"https://www.sinyi.com.tw/buy/list/{city}/default-desc/{page}"
    print(f"正在抓取第 {page} 頁: {url}")
    driver.get(url)

    # 等待房屋列表載入完成
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.buy-list-item"))
        )
    except:
        print(f"第 {page} 頁載入超時，跳過")
        break

    # 滾動頁面，確保 JS 渲染完成
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)

    # -----------------------------
    # 解析 HTML
    # -----------------------------
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    property_list = soup.find_all('div', class_='buy-list-item')

    # 如果這頁已經沒東西，代表到底了 → 停止
    if not property_list:
        print("已經沒有更多頁面，結束抓取")
        break

    for item in property_list:
        try:
            # 標題
            title = item.find('div', class_='LongInfoCard_Type_Name').get_text(strip=True)

            # 地址/屋齡/類型
            address_tag = item.find('div', class_='LongInfoCard_Type_Address')
            spans = address_tag.find_all('span') if address_tag else []
            address = spans[0].get_text(strip=True) if len(spans) > 0 else ''
            age = spans[1].get_text(strip=True) if len(spans) > 1 else ''
            if age == "--":
                age = ""
            house_type = spans[2].get_text(strip=True) if len(spans) > 2 else ''

            # 建坪/主+陽/格局/樓層
            house_info_tag = item.find('div', class_='longInfoCard_LongInfoCard_Type_HouseInfo__tZXDa')
            spans = house_info_tag.find_all('span') if house_info_tag else []
            
            area = ""
            if len(spans) > 0:
                match = re.search(r'[\d.]+', spans[0].get_text(strip=True))
                area = match.group() if match else ""
            
            Actual_space = ""
            if len(spans) > 1:
                match = re.search(r'[\d.]+', spans[1].get_text(strip=True))
                Actual_space = match.group() if match else ""
            
            layout = spans[2].get_text(strip=True) if len(spans) > 2 else ""
            if layout == "--":
                layout = ""
            floor = spans[3].get_text(strip=True) if len(spans) > 3 else ""
            # 如果是 "--樓/--樓" 就改成空字串
            if floor == "--樓/--樓":
                floor = ""


            # 車位
            Car_Grip_tag = item.find('span', class_='longInfoCard_LongInfoCard_Type_Parking__ZXl_e')
            Car_Grip = Car_Grip_tag.get_text(strip=True) if Car_Grip_tag and Car_Grip_tag.get_text(strip=True) != '' else '無車位'

            # 總價
            price = ""
            price_block = item.find('div', class_='LongInfoCard_Type_Right')
            if price_block:
                # 找到紅字的總價 (打折或沒打折都是紅字)
                red_price_span = price_block.find('span', style=lambda s: s and "color: rgb(221, 37, 37)" in s)
                if red_price_span:
                    price = red_price_span.get_text(strip=True)
                    # 把數字轉乾淨
                    match = re.search(r'[\d,.]+', price)
                    price = match.group().replace(",", "") if match else ""




            # 編號
            a_tag = item.find('a', href=True)
            house_id = '無編號'
            if a_tag:
                match = re.search(r'/buy/house/([A-Za-z0-9]+)', a_tag['href'])
                if match:
                    house_id = match.group(1)

            all_properties.append({
                '標題': title,
                '地址': address,
                '屋齡': age,
                '類型': house_type,
                '建坪': area,
                '主+陽': Actual_space,
                '格局': layout,
                '樓層': floor,
                '車位': Car_Grip,
                '總價(萬)': price,
                '編號': house_id
            })
        except Exception as e:
            print(f"解析錯誤: {e}")
            continue

    page += 1  # 換下一頁
    '''
    if page > 1:
        break
    '''

# -----------------------------
# 存成 CSV
# -----------------------------
df = pd.DataFrame(all_properties)
df.to_csv('buy_properties.csv', index=False, encoding='utf-8-sig')
print(f"總共抓到 {len(all_properties)} 筆房屋資料，已儲存到 buy_properties.csv")

driver.quit()
