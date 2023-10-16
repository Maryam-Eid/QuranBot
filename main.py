import httpx
import asyncio
from telegram import Bot, InputMediaPhoto
from glob import glob
import logging
from datetime import datetime
import os
import re

logging.basicConfig(level=logging.INFO)

bot = Bot(token='6479590757:AAH2m-4vPBHpATbHen5X14fxVNgo0oSz0p4')
channel_id = '@elquranelkareem1'
current_page_file = 'current_page.txt'

def get_local_quranic_pages():
    pages = glob('quran-images/*.png')
    sorted_pages = sorted(pages, key=lambda x: int(re.search(r'\d+', x).group()))
    return sorted_pages


async def send_local_quranic_pages():
    pages = get_local_quranic_pages()

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

def parse_prayer_time(time_str):
    hours, minutes = map(int, time_str.split(':'))
    now = datetime.now()
    prayer_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
    return prayer_time


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
            prayer_time = parse_prayer_time(prayer_time_str)
            return prayer_time
    except Exception as e:
        logging.error(f"Error fetching prayer times: {e}")
        return None


async def prayer_time_loop():
    prayers = ['الفجر', 'الظهر', 'العصر', 'المغرب', 'العشاء']
    current_prayer = 0

    while True:
        now = datetime.now()

        logging.info("Fetching prayer times from the API...")
        year, month = now.year, now.month

        fajr_time = await calculate_prayer_time('Fajr', now)
        dhuhr_time = await calculate_prayer_time('Dhuhr', now)
        asr_time = await calculate_prayer_time('Asr', now)
        maghrib_time = await calculate_prayer_time('Maghrib', now)
        isha_time = await calculate_prayer_time('Isha', now)

        logging.info(f'Fajr Time: {fajr_time}')
        logging.info(f'Dhuhr Time: {dhuhr_time}')
        logging.info(f'Asr Time: {asr_time}')
        logging.info(f'Maghrib Time: {maghrib_time}')
        logging.info(f'Isha Time: {isha_time}')

        upcoming_prayers = list(filter(lambda x: x > now, [fajr_time, dhuhr_time, asr_time, maghrib_time, isha_time]))
        if not upcoming_prayers:
            logging.info("No upcoming prayer times. Waiting for the next fetch...")
            await asyncio.sleep(7200)
            continue

        next_prayer_time = min(upcoming_prayers)
        time_until_next_prayer = next_prayer_time - now
        total_seconds_until_prayer = int(time_until_next_prayer.total_seconds())
        logging.info(f'Time until the next prayer: {total_seconds_until_prayer} seconds')
        if 60 >= total_seconds_until_prayer >= 0:
            await asyncio.sleep(10 * 60)
            await send_local_quranic_pages()
            await bot.send_message(chat_id=channel_id, text=f"ورد صلاة {prayers[current_prayer]} ♡")
            current_prayer = (current_prayer + 1) % len(prayers)
        else:
            await asyncio.sleep(total_seconds_until_prayer - 30)

if __name__ == "__main__":
    asyncio.run(prayer_time_loop())
