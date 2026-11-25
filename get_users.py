import aiohttp
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import logging
import os
from typing import Dict, Any, List, Optional

# Configuration
load_dotenv()
TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv('TELEGRAM_BOT_TOKEN')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
LOG: logging.Logger = logging.getLogger(__name__)


async def get_updates(offset: Optional[int] = None, limit: int = 100) -> Dict[str, Any]:
    """Fetch updates from Telegram bot API.
    
    Args:
        offset: Identifier of the first update to be returned
        limit: Limits the number of updates to be retrieved
        
    Returns:
        JSON response from Telegram API
    """
    url: str = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params: Dict[str, Any] = {
        "limit": limit
    }
    
    if offset is not None:
        params["offset"] = offset
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text: str = await response.text()
                    LOG.error(f"Failed to get updates. Status: {response.status}, Response: {error_text}")
                    return {"ok": False, "result": []}
    except Exception as e:
        LOG.error(f"Error fetching updates: {e}")
        return {"ok": False, "result": []}


async def list_users() -> None:
    """List all chat IDs with date of last message and username."""
    if not TELEGRAM_BOT_TOKEN:
        LOG.error("❌ TELEGRAM_BOT_TOKEN is not set in .env file")
        return
    
    LOG.info("🔍 Fetching user data from Telegram bot...")
    
    # Dictionary to store chat information
    # Key: chat_id, Value: {username, last_message_date}
    chats: Dict[int, Dict[str, Any]] = {}
    
    # Fetch all available updates
    offset: Optional[int] = None
    
    while True:
        response: Dict[str, Any] = await get_updates(offset=offset)
        
        if not response.get("ok"):
            LOG.error("Failed to fetch updates from Telegram API")
            break
        
        updates: List[Dict[str, Any]] = response.get("result", [])
        
        if not updates:
            break
        
        # Process each update
        for update in updates:
            update_id: int = update.get("update_id", 0)
            
            # Handle different types of updates (message, edited_message, etc.)
            message: Optional[Dict[str, Any]] = update.get("message") or update.get("edited_message")
            
            if message:
                chat: Dict[str, Any] = message.get("chat", {})
                chat_id: int = chat.get("id")
                
                if chat_id:
                    # Extract user information
                    username: Optional[str] = chat.get("username")
                    first_name: Optional[str] = chat.get("first_name")
                    last_name: Optional[str] = chat.get("last_name")
                    chat_type: str = chat.get("type", "unknown")
                    
                    # Build display name
                    name_parts: List[str] = []
                    if first_name:
                        name_parts.append(first_name)
                    if last_name:
                        name_parts.append(last_name)
                    
                    display_name: str = " ".join(name_parts) if name_parts else "No name"
                    
                    # Get message date
                    message_date: int = message.get("date", 0)
                    message_datetime: datetime = datetime.fromtimestamp(message_date)
                    
                    # Update chat info (keep the latest message date)
                    if chat_id not in chats or message_datetime > chats[chat_id]["last_message_date"]:
                        chats[chat_id] = {
                            "username": username,
                            "display_name": display_name,
                            "chat_type": chat_type,
                            "last_message_date": message_datetime
                        }
            
            # Update offset for next batch
            offset = update_id + 1
        
        # If we got fewer updates than the limit, we've reached the end
        if len(updates) < 100:
            break
    
    # Display results
    if not chats:
        LOG.info("📭 No chats found")
        return
    
    LOG.info(f"\n{'='*80}")
    LOG.info(f"📊 Found {len(chats)} chat(s):\n")
    
    # Sort chats by last message date (most recent first)
    sorted_chats = sorted(chats.items(), key=lambda x: x[1]["last_message_date"], reverse=True)
    
    for chat_id, info in sorted_chats:
        username_display: str = f"@{info['username']}" if info['username'] else "No username"
        last_message: str = info['last_message_date'].strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"Chat ID: {chat_id}")
        print(f"  Type: {info['chat_type']}")
        print(f"  Name: {info['display_name']}")
        print(f"  Username: {username_display}")
        print(f"  Last Message: {last_message}")
        print()
    
    LOG.info(f"{'='*80}")
    LOG.info("\n💡 Tip: Add chat IDs to TELEGRAM_CHAT_IDS in your .env file (comma-separated)")


if __name__ == "__main__":
    try:
        asyncio.run(list_users())
    except KeyboardInterrupt:
        LOG.info("\n👋 Goodbye!")
