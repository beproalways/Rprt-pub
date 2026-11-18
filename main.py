#!/usr/bin/env python3
"""
Main script to run the Telegram Report Plugin.
This creates a Telethon client and loads the report_plugin.
"""

import os
import sys
from telethon import TelegramClient, events

# Add the current directory to path so we can import report_plugin
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Your Telegram API credentials
# Get these from https://my.telegram.org
API_ID = 2040  # Replace with your API ID
API_HASH = 'b18441a1ff607e10a989891a5462e627'  # Replace with your API HASH

# Session name (will create session file)
SESSION_NAME = 'report_bot_session'

# Master ID from report_plugin.py (only this user can use .report command)
MASTER_ID = 8679127662

async def main():
    # Create the client
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    # Connect and authorize
    await client.start()
    
    # Import and initialize the report plugin
    import report_plugin
    report_plugin.init(client)
    
    print(f"[+] Report plugin loaded. Master ID: {MASTER_ID}")
    print(f"[+] Send '.report <link>' from user ID {MASTER_ID} to use the plugin")
    print("[+] Press Ctrl+C to stop")
    
    # Keep the client running
    await client.run_until_disconnected()

if __name__ == '__main__':
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[+] Stopped")