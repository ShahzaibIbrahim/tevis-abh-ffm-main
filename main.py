import aiohttp
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
import logging
import os
from typing import Optional, List, Dict, Any, Union

# Configuration
load_dotenv()
TARGET_DATE: datetime = datetime.fromisoformat(
    os.getenv('TARGET_DATE', '2025-10-28'))
SHOW_POPUP: bool = os.getenv('SHOW_POPUP') not in [
    '0', 'False', 'false', '', None]
TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_IDS: List[str] = os.getenv('TELEGRAM_CHAT_IDS', '').split(',')
CHECK_DELAY: int = int(os.getenv('CHECK_DELAY', '30'))  # seconds

# Initial URL to start the appointment search
START_URL: str = os.getenv('START_URL', "https://tevis.ekom21.de/fra/select2?md=35") # Arbeitnehmer 35.3
LOCATION_CODE: str = os.getenv('LOCATION_CODE') or "315"  # Location code for Frankfurt am Main Ausländerbehörde
CNC_CODE: str = os.getenv('CNC_CODE', "5792")  # Selection code for the specific appointment type
NO_PERSONS: str = os.getenv('NO_PERSONS', "1")  # Number of persons for the appointment
LOCATION_NUMBER: Optional[str] = os.getenv('LOCATION_NUMBER') or None  # Order for location number in Standortauswahl. Leave none if any location desirable

# Global variable to track current popup
current_popup: Optional['tk.Tk'] = None

# Setup
if SHOW_POPUP:
    import webbrowser
    import tkinter as tk

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
LOG: logging.Logger = logging.getLogger(__name__)


async def run_once() -> None:
    """Single check, used for scheduled runs (e.g. GitHub Actions)."""
    next_termin: datetime = await get_next_termin_with_retry(max_retries=3)
    if next_termin is not None and next_termin <= TARGET_DATE:
        LOG.info(f"Found an appointment on or before the target date: {next_termin}")
        if TELEGRAM_BOT_TOKEN:
            await asyncio.gather(*(send_telegram_message(c.strip(), next_termin)
                                   for c in TELEGRAM_CHAT_IDS if c.strip()))
    else:
        LOG.info(f"No suitable appointment found, next available is: {next_termin}")


async def main() -> None:
    """Main application loop that continuously checks for appointments."""
    tasks = []
    while True:
        next_termin: datetime = await get_next_termin_with_retry()
        if next_termin is not None and next_termin <= TARGET_DATE:
            LOG.info(
                f"Found an appointment on or before the target date: {next_termin}")
            if SHOW_POPUP:
                popup_task = asyncio.create_task(show_popup_async(next_termin))
                tasks.append(popup_task)
            if TELEGRAM_BOT_TOKEN:
                for chat_id in TELEGRAM_CHAT_IDS:
                    telegram_task = asyncio.create_task(send_telegram_message(chat_id, next_termin))
                    tasks.append(telegram_task)
        else:
            LOG.info(
                f"No suitable appointment found, next available is: {next_termin}")
        await asyncio.sleep(CHECK_DELAY)
        # clean up completed tasks
        tasks = [task for task in tasks if not task.done()]


async def get_next_termin_with_retry(max_retries: int = 2**31, delay: int = 5) -> datetime:
    """Retry logic for fetching the next appointment.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Delay in seconds between retries

    Returns:
        The earliest available appointment datetime

    Raises:
        RuntimeError: If all retry attempts fail
    """
    for attempt in range(max_retries):
        try:
            return await get_next_termin()
        except Exception as e:
            LOG.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                LOG.info(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
    raise RuntimeError("Failed to fetch next appointment after retries")


async def get_next_termin() -> datetime:
    """Make the HTTP requests truly async using aiohttp.

    Returns:
        The earliest available appointment datetime

    Raises:
        RuntimeError: If unexpected address is found or no appointments available
        aiohttp.ClientError: If HTTP requests fail
    """

    # Common headers to simulate a real browser
    headers: Dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Referer": START_URL,
        "Origin": "https://tevis.ekom21.de"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        # Step 1: Obtain session cookies
        async with session.get(START_URL) as resp1:
            resp1.raise_for_status()
            cookies: Dict[str, str] = {
                cookie.key: cookie.value for cookie in session.cookie_jar}
            LOG.debug(f"Step 1 → Retrieved cookies: {cookies}")

        # Step 2: GET /fra/location?mdt=315&select_cnc=1&cnc-5792=1 with those cookies
        location_url: str = "https://tevis.ekom21.de/fra/location"
        location_params: Dict[str, str] = {
            "mdt": LOCATION_CODE,
            "select_cnc": "1",
            f"cnc-{CNC_CODE}": NO_PERSONS
        }

        async with session.get(location_url, params=location_params) as resp2:
            resp2.raise_for_status()
            LOG.debug(f"Step 2 → GET /location status: {resp2.status}")

            html_content: str = await resp2.text()
            soup: BeautifulSoup = BeautifulSoup(html_content, "html.parser")
            dl_suggest: Optional[Any] = soup.find("dl", class_="suggest_location_tbl")
            earliest_date: Optional[datetime] = None

            def parse_next_termin(dl: Any) -> Optional[datetime]:
                next_termin_dt = dl.find_next("dt", string="Nächster Termin")
                if not next_termin_dt:
                    return None
                next_termin = next_termin_dt.next_sibling
                return datetime.strptime(next_termin.text.strip(), "ab %d.%m.%Y, %H:%M Uhr")

            if LOCATION_NUMBER is not None:
                for _ in range(int(LOCATION_NUMBER) - 1):
                    if dl_suggest is not None:
                        dl_suggest = dl_suggest.find_next("dl", class_="suggest_location_tbl")
                if dl_suggest:
                    parsed_datetime = parse_next_termin(dl_suggest)
                    if parsed_datetime:
                        earliest_date = parsed_datetime
            else:
                while dl_suggest:
                    parsed_datetime = parse_next_termin(dl_suggest)
                    if not parsed_datetime:
                        break
                    if earliest_date is None or parsed_datetime < earliest_date:
                        earliest_date = parsed_datetime
                    dl_suggest = dl_suggest.find_next("dl", class_="suggest_location_tbl")
            return earliest_date


async def send_telegram_message(chat_id: str, appointment_date: datetime) -> None:
    """Send notification via Telegram bot.

    Args:
        chat_id: Telegram chat ID to send message to
        appointment_date: The appointment datetime to notify about
    """
    message: str = f"<b>🎉 Appointment Found!</b>\n\n📅 Date: {appointment_date.strftime('%d.%m.%Y at %H:%M')}\n🎯 Target: {TARGET_DATE.strftime('%d.%m.%Y')}\n\n🔗 Book now: {START_URL}"

    url: str = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload: Dict[str, Union[str, bool]] = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    LOG.info("✅ Telegram message sent successfully")
                else:
                    error_text: str = await response.text()
                    LOG.error(
                        f"❌ Failed to send Telegram message: {response.status} - {error_text}")
    except Exception as e:
        LOG.error(f"❌ Error sending Telegram message: {e}")


async def show_popup_async(appointment_date: datetime) -> None:
    """Create popup at cursor position without blocking the async loop.
    Closes any existing popup before opening a new one.

    Args:
        appointment_date: The appointment datetime to display
    """
    global current_popup
    
    # Close existing popup if it exists
    if current_popup is not None:
        try:
            if current_popup.winfo_exists():
                current_popup.destroy()
                LOG.debug("Closed existing popup")
        finally:
            current_popup = None

    def open_link(event: Any) -> None:
        """Open the appointment booking URL in browser."""
        webbrowser.open_new(START_URL)

    popup: tk.Tk = tk.Tk()
    current_popup = popup  # Store reference to current popup
    
    popup.title("Appointment Found")
    popup.attributes("-topmost", True)

    width: int = 300
    height: int = 150

    # Get cursor position
    cursor_x: int = popup.winfo_pointerx()
    cursor_y: int = popup.winfo_pointery()

    # Position popup at cursor location with slight offset to avoid covering cursor
    x: int = cursor_x + 10
    y: int = cursor_y + 10

    # Ensure popup doesn't go off screen
    screen_width: int = popup.winfo_screenwidth()
    screen_height: int = popup.winfo_screenheight()

    # Adjust if popup would go beyond screen boundaries
    if x + width > screen_width:
        x = screen_width - width - 10
    if y + height > screen_height:
        y = screen_height - height - 10

    popup.geometry(f"{width}x{height}+{x}+{y}")

    label: tk.Label = tk.Label(
        popup, text=f"Appointment on or before {TARGET_DATE.date()}:\n{appointment_date}", pady=10)
    label.pack()

    link: tk.Label = tk.Label(
        popup, text="Click here to open the appointment page", fg="blue", cursor="hand2")
    link.pack()
    link.bind("<Button-1>", open_link)

    def on_close():
        """Clean up global reference when popup is closed."""
        global current_popup
        current_popup = None
        popup.destroy()

    close_button: tk.Button = tk.Button(
        popup, text="Close", command=on_close)
    close_button.pack(pady=20)

    # Handle window close button (X)
    popup.protocol("WM_DELETE_WINDOW", on_close)

    try:
        while popup.winfo_exists():
            popup.update()
            # Small delay to yield control back to event loop
            await asyncio.sleep(0.01)
    except tk.TclError:
        # Popup was destroyed, which is expected when user closes it
        pass
    finally:
        # Clean up reference when function exits
        if current_popup == popup:
            current_popup = None


def is_enabled(flag: bool) -> str:
    """Helper function to return a string representation of a boolean flag."""
    return "✅ Enabled" if flag else "❌ Disabled"


if __name__ == "__main__":
    LOG.info("🔍 Starting appointment checker...")
    LOG.info(
        f"📅 Looking for appointments on or before: {TARGET_DATE.strftime('%d.%m.%Y')}")
    LOG.info(
        f"💬 Popup notifications: {is_enabled(SHOW_POPUP)}")
    LOG.info(
        f"📧 Telegram notifications: {is_enabled(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS)}")
    LOG.info("⏹️  Press Ctrl+C to stop\n")

    try:
        asyncio.run(run_once() if os.getenv('RUN_ONCE') == '1' else main())
    except KeyboardInterrupt:
        LOG.info("👋 Goodbye!")
