import time
from io import BytesIO
from telegram import Update # type: ignore
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes # type: ignore
from selenium import webdriver # type: ignore # type: ignore
from selenium.webdriver.common.by import By # type: ignore
from selenium.webdriver.chrome.options import Options # type: ignore
from selenium.webdriver.support.ui import WebDriverWait # type: ignore
from selenium.webdriver.support import expected_conditions as EC # type: ignore
from PIL import Image # type: ignore

# === CONFIG ===
BOT_TOKEN = '7846667968:AAGsgCh0qsc-mR1bMddkNrcRGqLjWcKMpRM'  # Replace with your Telegram bot token
DOB = "21-03-2004"
APP_URL = "https://sarathi.parivahan.gov.in/sarathiservice/applicationredirect.do?as=1521946625"

# === GLOBALS ===
user_chat_id = None
driver = None
captcha_step = 0  # 1 = first captcha, 2 = second captcha

# === Setup Chrome Driver ===
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=chrome_options)


# === Capture CAPTCHA via Screenshot ===
def capture_captcha(driver, captcha_element):
    screenshot = driver.get_screenshot_as_png()
    image = Image.open(BytesIO(screenshot))

    location = captcha_element.location
    size = captcha_element.size
    left = location['x']
    top = location['y']
    right = left + size['width']
    bottom = top + size['height']

    captcha_image = image.crop((left, top, right, bottom))
    return captcha_image

# === /start command ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global driver, user_chat_id, captcha_step
    user_chat_id = update.effective_chat.id
    captcha_step = 1

    await context.bot.send_message(chat_id=user_chat_id, text="🚦 Starting slot check...")

    try:
        driver = setup_driver()
        driver.get("https://parivahan.gov.in/")
        driver.get(APP_URL)

        # Step 1: Enter DOB and submit
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "dateOfBirth"))).send_keys(DOB)
        driver.find_element(By.ID, "submit").click()

        # Step 2: Wait for CAPTCHA input field
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "entcaptxt")))
        captcha_element = driver.find_element(By.ID, "capimg")

        # Step 3: Send CAPTCHA screenshot to user
        captcha_image = capture_captcha(driver, captcha_element)
        with BytesIO() as output:
            captcha_image.save(output, format='PNG')
            output.seek(0)
            await context.bot.send_photo(chat_id=user_chat_id, photo=output)

        await context.bot.send_message(chat_id=user_chat_id, text="Please enter the first CAPTCHA.")
    
    except Exception as e:
        await context.bot.send_message(chat_id=user_chat_id, text=f"❌ Error: {str(e)}")
        if driver: driver.quit()
        captcha_step = 0

# === Handle user CAPTCHA replies ===
async def handle_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global driver, captcha_step, user_chat_id

    if driver is None or captcha_step == 0:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❗ Not expecting a CAPTCHA right now.")
        return

    captcha_text = update.message.text.strip()

    try:
        if captcha_step == 1:
            # Step 4: Submit first CAPTCHA
            driver.find_element(By.ID, "entcaptxt").send_keys(captcha_text)
            driver.find_element(By.ID, "submit").click()

            # Step 5: Click 'Proceed' button
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "applViewStages_0")))
            driver.find_element(By.ID, "applViewStages_0").click()

            # Step 6: Select Application Number checkbox
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "dlslotipform_subtype1")))
            driver.find_element(By.ID, "dlslotipform_subtype1").click()

            # Step 7: Wait for second CAPTCHA field to appear
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "captcha")))
            captcha_element = driver.find_element(By.ID, "captchaImg")

            # Step 8: Screenshot second CAPTCHA and send
            captcha_image = capture_captcha(driver, captcha_element)
            with BytesIO() as output:
                captcha_image.save(output, format='PNG')
                output.seek(0)
                await context.bot.send_photo(chat_id=user_chat_id, photo=output)

            await context.bot.send_message(chat_id=user_chat_id, text="Please enter the second CAPTCHA.")
            captcha_step = 2

        elif captcha_step == 2:
            # Step 9: Enter second CAPTCHA and submit
            driver.find_element(By.ID, "captcha").send_keys(captcha_text)
            driver.find_element(By.ID, "dlslotipform____SAVE___").click()

            # Step 10: Select LMV and MCWG
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "1")))
            driver.find_element(By.ID, "1").click()
            driver.find_element(By.ID, "2").click()

            # Step 11: Proceed to Book
            driver.find_element(By.ID, "prcdbook").click()

            # Step 12: Check for slot availability message
            time.sleep(1)
            try:
                msg = driver.find_element(By.XPATH, "//*[contains(text(), 'Slots are not Available')]")
                await context.bot.send_message(chat_id=user_chat_id, text=f"❌ {msg.text}")
            except:
                await context.bot.send_message(chat_id=user_chat_id, text="✅ SLOTS AVAILABLE! BOOK NOW!")

            driver.quit()
            captcha_step = 0

    except Exception as e:
        await context.bot.send_message(chat_id=user_chat_id, text=f"❌ Error: {str(e)}")
        if driver:
            driver.quit()
        captcha_step = 0

# === Telegram Bot Initialization ===
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_captcha))
    print("🤖 Bot is running...")
    app.run_polling()
