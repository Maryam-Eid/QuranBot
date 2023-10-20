import asyncio
import logging
import os
import re
from datetime import datetime
from dotenv import load_dotenv
import pytz
from glob import glob
import httpx
from telegram import Bot, InputMediaPhoto

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load environment variables from .env file
load_dotenv()

token = os.environ.get('TELEGRAM_BOT_TOKEN')
channel_id = os.environ.get('TELEGRAM_CHANNEL_ID')

# Initialize the Telegram bot
bot = Bot(token=token)

# File to store the current Quranic page
current_page_file = 'current_page.txt'


# Function to get a list of local Quranic pages
def get_local_quranic_pages():
    pages = glob('quran-images/*.png')
    pages.sort()
    return pages


# Function to send local Quranic pages to the Telegram channel
async def send_local_quranic_pages():
    pages = get_local_quranic_pages()

    # Read the current page from the file or initialize it to 0
    if os.path.exists(current_page_file):
        with open(current_page_file, 'r') as file:
            current_page = int(file.read().strip())
    else:
        current_page = 0

    if current_page >= len(pages):
        current_page = 0

    media_group = []

    for _ in range(2):
        try:
            page_path = pages[current_page]
            media_group.append(InputMediaPhoto(media=open(page_path, 'rb')))
            logging.info(f'Added {page_path} to the media group')
        except Exception as e:
            logging.error(f'Error adding {page_path} to the media group: {e}')

        current_page += 1

    try:
        # Send the photos as a media group
        await bot.send_media_group(chat_id=channel_id, media=media_group)
        logging.info('Successfully sent the media group')
    except Exception as e:
        logging.error(f'Error sending the media group: {e}')

    with open(current_page_file, 'w') as file:
        file.write(str(current_page))


# Function to parse prayer time string and convert it to a datetime object
def parse_prayer_time(time_str, tzinfo):
    hours, minutes = map(int, time_str.split(':'))
    now = datetime.now(tzinfo)
    prayer_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
    return prayer_time


# Function to fetch and calculate prayer times
async def calculate_prayer_time(prayer_name, date):
    try:
        async with httpx.AsyncClient() as client:
            date_str = date.strftime("%d-%m-%Y")
            response = await client.get(f"http://api.aladhan.com/v1/timingsByCity/{date_str}", params={
                "city": "Mansoura",
                "country": "Egypt",
                "method": 5
            })
            response.raise_for_status()
            data = response.json()
            prayer_time_str = data['data']['timings'][prayer_name]
            prayer_time = parse_prayer_time(prayer_time_str, date.tzinfo)
            return prayer_time
    except Exception as e:
        logging.error(f"Error fetching prayer times: {e}")
        return None


# Function to continuously check and send prayer times
async def prayer_time_loop():
    prayers = ['الفجر', 'الظهر', 'العصر', 'المغرب', 'العشاء']
    current_prayer = 4

    tz_cairo = pytz.timezone('Africa/Cairo')

    while True:
        now = datetime.now(tz_cairo)
        logging.info("Fetching prayer times from the API...")

        # Fetch prayer times for the current day
        fajr_time = await calculate_prayer_time('Fajr', now)
        dhuhr_time = await calculate_prayer_time('Dhuhr', now)
        asr_time = await calculate_prayer_time('Asr', now)
        maghrib_time = await calculate_prayer_time('Maghrib', now)
        isha_time = await calculate_prayer_time('Isha', now)

        prayer_times = [fajr_time, dhuhr_time, asr_time, maghrib_time, isha_time]
        if any(time is None for time in prayer_times):
            logging.error("Error fetching prayer times. Retrying...")
            await asyncio.sleep(60)
            continue

        # Log the fetched prayer times
        for i, prayer_name in enumerate(prayers):
            logging.info(f'{prayer_name} Time: {prayer_times[i]}')
        logging.info(f'Now: {now}')

        upcoming_prayers = [time for time in prayer_times if time > now]

        if not upcoming_prayers:
            logging.info("No upcoming prayer times. Waiting for the next fetch...")
            await asyncio.sleep(7200)
            continue

        next_prayer_time = min(upcoming_prayers)
        time_until_next_prayer = next_prayer_time - now
        total_seconds_until_prayer = int(time_until_next_prayer.total_seconds())
        logging.info(f'Time until the next prayer: {total_seconds_until_prayer // 60} minute/s')

        if 300 >= total_seconds_until_prayer >= 0:
            # Wait 10 minutes after prayer time before sending
            await asyncio.sleep(10 * 60)
            await send_local_quranic_pages()
            await bot.send_message(chat_id=channel_id, text=f"ورد صلاة {prayers[current_prayer]} ♡")
            current_prayer = (current_prayer + 1) % len(prayers)
        else:
            await asyncio.sleep(total_seconds_until_prayer - 60)


if __name__ == "__main__":
    asyncio.run(prayer_time_loop())
