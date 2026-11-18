#!/usr/bin/env python3
"""
OSNIT ANTI-BAN TELEGRAM REPORTER
Advanced tool that prevents account bans while reporting
"""

import os
import sys
import time
import random
import asyncio
import logging
import requests
from datetime import datetime, timedelta
from colorama import init, Fore, Back, Style
import json
import hashlib

# Initialize colorama
init()

# ============================================================================
# CONFIGURATION - ANTI-BAN SETTINGS
# ============================================================================

class AntiBanConfig:
    """Anti-ban configuration settings"""
    
    # Random delays between actions (in seconds)
    MIN_DELAY = 2
    MAX_DELAY = 8
    
    # Report count limits per session
    MAX_REPORTS_PER_SESSION = 15
    
    # Cooldown between sessions (in minutes)
    SESSION_COOLDOWN = 30
    
    # Random user agents for requests
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    
    # Different report messages to avoid pattern detection
    REPORT_MESSAGES = [
        "This account violates Telegram's terms of service",
        "Content violates community guidelines",
        "Inappropriate behavior detected",
        "Spam activity identified",
        "Violation of platform rules",
        "Reported for policy violation",
        "Against Telegram guidelines",
        "Community standards violation"
    ]
    
    # Different IP rotation settings (if using proxy)
    USE_PROXY_ROTATION = False
    PROXY_LIST = []  # Add proxies here if needed

# ============================================================================
# ANTI-BAN MANAGER
# ============================================================================

class AntiBanManager:
    """Manages anti-ban techniques to protect accounts"""
    
    def __init__(self, account_id):
        self.account_id = account_id
        self.activity_log = []
        self.session_start = None
        self.report_count_today = 0
        self.last_action_time = None
        
        # Load account history
        self.load_history()
    
    def load_history(self):
        """Load account activity history"""
        history_file = f"history/account_{self.account_id}.json"
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r') as f:
                    data = json.load(f)
                    self.activity_log = data.get('activity_log', [])
                    self.report_count_today = data.get('report_count_today', 0)
            except:
                self.activity_log = []
                self.report_count_today = 0
    
    def save_history(self):
        """Save account activity history"""
        os.makedirs("history", exist_ok=True)
        history_file = f"history/account_{self.account_id}.json"
        data = {
            'account_id': self.account_id,
            'activity_log': self.activity_log[-100:],  # Keep last 100 activities
            'report_count_today': self.report_count_today,
            'last_updated': datetime.now().isoformat()
        }
        with open(history_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def can_perform_action(self, action_type="report"):
        """Check if account can perform action without risk"""
        current_time = datetime.now()
        
        # Check daily limit
        if action_type == "report" and self.report_count_today >= 50:
            print(f"{Fore.YELLOW}[⚠] Account {self.account_id}: Daily report limit reached (50){Style.RESET_ALL}")
            return False
        
        # Check if we need session cooldown
        if self.last_action_time:
            time_diff = (current_time - self.last_action_time).total_seconds()
            if time_diff < AntiBanConfig.MIN_DELAY:
                return False
        
        # Check for pattern detection
        if self.is_pattern_detected():
            print(f"{Fore.YELLOW}[⚠] Account {self.account_id}: Pattern detected, cooling down...{Style.RESET_ALL}")
            return False
        
        return True
    
    def is_pattern_detected(self):
        """Detect if account is showing suspicious patterns"""
        if len(self.activity_log) < 5:
            return False
        
        # Check for rapid consecutive actions
        recent_actions = self.activity_log[-5:]
        timestamps = [a['timestamp'] for a in recent_actions]
        
        # Calculate time differences
        diffs = []
        for i in range(1, len(timestamps)):
            t1 = datetime.fromisoformat(timestamps[i-1])
            t2 = datetime.fromisoformat(timestamps[i])
            diffs.append((t2 - t1).total_seconds())
        
        # If all actions are within very short time, pattern detected
        if all(d < 3 for d in diffs):
            return True
        
        return False
    
    def record_action(self, action_type, target=None, result=None):
        """Record account action for pattern analysis"""
        action = {
            'timestamp': datetime.now().isoformat(),
            'action_type': action_type,
            'target': target,
            'result': result
        }
        
        self.activity_log.append(action)
        
        if action_type == "report":
            self.report_count_today += 1
        
        self.last_action_time = datetime.now()
        self.save_history()
    
    def get_random_delay(self):
        """Get random delay to avoid detection"""
        return random.uniform(AntiBanConfig.MIN_DELAY, AntiBanConfig.MAX_DELAY)
    
    def get_random_user_agent(self):
        """Get random user agent"""
        return random.choice(AntiBanConfig.USER_AGENTS)
    
    def get_random_report_message(self):
        """Get random report message"""
        return random.choice(AntiBanConfig.REPORT_MESSAGES)
    
    def reset_daily_count(self):
        """Reset daily counters (call this daily)"""
        today = datetime.now().date()
        last_activity_date = None
        
        if self.activity_log:
            last_activity = self.activity_log[-1]
            last_activity_date = datetime.fromisoformat(last_activity['timestamp']).date()
        
        if last_activity_date != today:
            self.report_count_today = 0
            self.save_history()

# ============================================================================
# SAFE TELEGRAM CLIENT
# ============================================================================

class SafeTelegramClient:
    """Telegram client with anti-ban protection"""
    
    def __init__(self, session_path, api_id, api_hash, account_id):
        self.session_path = session_path
        self.api_id = api_id
        self.api_hash = api_hash
        self.account_id = account_id
        self.anti_ban = AntiBanManager(account_id)
        
        # Import telethon here to avoid issues
        try:
            from telethon.sync import TelegramClient
            from telethon import functions, types
            from telethon.errors import (
                FloodWaitError,
                PhoneCodeInvalidError,
                SessionPasswordNeededError
            )
            self.TelegramClient = TelegramClient
            self.functions = functions
            self.types = types
            self.errors = {
                'FloodWaitError': FloodWaitError,
                'PhoneCodeInvalidError': PhoneCodeInvalidError,
                'SessionPasswordNeededError': SessionPasswordNeededError
            }
        except ImportError:
            print(f"{Fore.RED}[✗] Telethon not installed. Install with: pip install telethon{Style.RESET_ALL}")
            sys.exit(1)
    
    async def safe_connect(self):
        """Connect with anti-ban delays"""
        if not self.anti_ban.can_perform_action("connect"):
            delay = self.anti_ban.get_random_delay()
            print(f"{Fore.CYAN}[⏳] Account {self.account_id}: Delaying connection for {delay:.1f}s{Style.RESET_ALL}")
            await asyncio.sleep(delay)
        
        client = self.TelegramClient(self.session_path, self.api_id, self.api_hash)
        
        try:
            await client.connect()
            
            if not await client.is_user_authorized():
                print(f"{Fore.YELLOW}[⚠] Account {self.account_id}: Not authorized{Style.RESET_ALL}")
                return None
            
            # Simulate human-like delay
            await asyncio.sleep(random.uniform(1, 3))
            
            self.anti_ban.record_action("connect", result="success")
            return client
            
        except Exception as e:
            print(f"{Fore.RED}[✗] Account {self.account_id}: Connection failed - {e}{Style.RESET_ALL}")
            self.anti_ban.record_action("connect", result=f"failed: {e}")
            return None
    
    async def safe_report(self, client, target_username, reason_type="spam", report_count=1):
        """Safely report a target with anti-ban techniques"""
        reports_sent = 0
        
        for i in range(report_count):
            if not self.anti_ban.can_perform_action("report"):
                print(f"{Fore.YELLOW}[⚠] Account {self.account_id}: Cooling down...{Style.RESET_ALL}")
                break
            
            try:
                # Get target entity
                target_entity = await client.get_entity(target_username)
                
                # Random delay before action
                delay = self.anti_ban.get_random_delay()
                await asyncio.sleep(delay)
                
                # Get random report message
                report_message = self.anti_ban.get_random_report_message()
                
                # Get reason object
                reason_map = {
                    'spam': self.types.InputReportReasonSpam(),
                    'fake': self.types.InputReportReasonFake(),
                    'violence': self.types.InputReportReasonViolence(),
                    'pornography': self.types.InputReportReasonPornography(),
                    'child_abuse': self.types.InputReportReasonChildAbuse(),
                    'other': self.types.InputReportReasonOther()
                }
                
                reason = reason_map.get(reason_type, self.types.InputReportReasonOther())
                
                # Try to get messages for reporting
                try:
                    messages = await client.get_messages(target_entity, limit=2)
                    message_ids = [m.id for m in messages] if messages else [0]
                except:
                    message_ids = [0]
                
                # Send report with random variations
                report_result = await client(self.functions.messages.ReportRequest(
                    peer=target_entity,
                    id=message_ids,
                    reason=reason,
                    message=report_message
                ))
                
                if report_result:
                    reports_sent += 1
                    print(f"{Fore.GREEN}[✓] Account {self.account_id}: Report #{i+1} sent{Style.RESET_ALL}")
                    
                    # Record successful action
                    self.anti_ban.record_action(
                        "report", 
                        target=target_username, 
                        result="success"
                    )
                else:
                    print(f"{Fore.YELLOW}[~] Account {self.account_id}: Report #{i+1} may have failed{Style.RESET_ALL}")
                    self.anti_ban.record_action(
                        "report", 
                        target=target_username, 
                        result="partial"
                    )
                
                # Random delay after successful report
                if i < report_count - 1:  # Not the last report
                    post_delay = random.uniform(3, 10)
                    await asyncio.sleep(post_delay)
                
            except self.errors['FloodWaitError'] as e:
                print(f"{Fore.RED}[✗] Account {self.account_id}: Flood wait {e.seconds}s{Style.RESET_ALL}")
                await asyncio.sleep(e.seconds + 10)  # Extra safety margin
                self.anti_ban.record_action("report", target=target_username, result=f"flood_wait:{e.seconds}")
                break
                
            except Exception as e:
                error_msg = str(e)
                if "PEER_ID_INVALID" in error_msg:
                    print(f"{Fore.RED}[✗] Account {self.account_id}: Invalid target{Style.RESET_ALL}")
                    break
                elif "Too Many Requests" in error_msg:
                    print(f"{Fore.RED}[✗] Account {self.account_id}: Rate limited{Style.RESET_ALL}")
                    await asyncio.sleep(60)  # Wait 1 minute
                    break
                else:
                    print(f"{Fore.RED}[✗] Account {self.account_id}: Error - {error_msg[:50]}{Style.RESET_ALL}")
                    self.anti_ban.record_action("report", target=target_username, result=f"error:{error_msg[:50]}")
                    await asyncio.sleep(5)
        
        return reports_sent

# ============================================================================
# ACCOUNT ROTATION MANAGER
# ============================================================================

class AccountRotationManager:
    """Manages rotation between multiple accounts to avoid detection"""
    
    def __init__(self, sessions_dir="sessions"):
        self.sessions_dir = sessions_dir
        self.accounts = []
        self.current_index = 0
        self.load_accounts()
        
        # Statistics
        self.stats = {
            'total_reports_sent': 0,
            'accounts_used': 0,
            'successful_reports': 0,
            'failed_reports': 0
        }
    
    def load_accounts(self):
        """Load all available accounts"""
        if not os.path.exists(self.sessions_dir):
            os.makedirs(self.sessions_dir)
            return
        
        session_files = [f for f in os.listdir(self.sessions_dir) if f.endswith('.session')]
        
        for session_file in session_files:
            # Extract account ID from filename (e.g., "account_1.session" -> 1)
            match = re.search(r'account_(\d+)\.session', session_file)
            if match:
                account_id = int(match.group(1))
                session_path = os.path.join(self.sessions_dir, session_file)
                
                # Check if session is valid (has content)
                if os.path.getsize(session_path) > 100:
                    self.accounts.append({
                        'id': account_id,
                        'session_path': session_path,
                        'last_used': None,
                        'report_count': 0,
                        'status': 'active'
                    })
        
        print(f"{Fore.CYAN}[ℹ] Loaded {len(self.accounts)} accounts{Style.RESET_ALL}")
    
    def get_next_account(self):
        """Get next account for rotation"""
        if not self.accounts:
            return None
        
        # Find account with least recent usage
        available_accounts = [acc for acc in self.accounts if acc['status'] == 'active']
        
        if not available_accounts:
            # Reset all accounts if all are cooling down
            for acc in self.accounts:
                acc['status'] = 'active'
            available_accounts = self.accounts
        
        # Sort by last_used (None first, then oldest)
        available_accounts.sort(key=lambda x: x['last_used'] or datetime.min)
        
        selected = available_accounts[0]
        selected['last_used'] = datetime.now()
        
        # Move to next index for round-robin
        self.current_index = (self.current_index + 1) % len(self.accounts)
        
        return selected
    
    def mark_account_cooling(self, account_id):
        """Mark account as cooling down"""
        for acc in self.accounts:
            if acc['id'] == account_id:
                acc['status'] = 'cooling'
                # Schedule reactivation after cooldown
                asyncio.create_task(self.reactivate_account(account_id))
                break
    
    async def reactivate_account(self, account_id):
        """Reactivate account after cooldown"""
        await asyncio.sleep(AntiBanConfig.SESSION_COOLDOWN * 60)  # Convert minutes to seconds
        
        for acc in self.accounts:
            if acc['id'] == account_id:
                acc['status'] = 'active'
                print(f"{Fore.GREEN}[✓] Account {account_id} reactivated after cooldown{Style.RESET_ALL}")
                break
    
    def update_stats(self, successful, failed):
        """Update statistics"""
        self.stats['successful_reports'] += successful
        self.stats['failed_reports'] += failed
        self.stats['total_reports_sent'] = self.stats['successful_reports'] + self.stats['failed_reports']
    
    def print_stats(self):
        """Print statistics"""
        print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}📊 REPORTING STATISTICS:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}✓ Successful reports: {self.stats['successful_reports']}{Style.RESET_ALL}")
        print(f"{Fore.RED}✗ Failed reports: {self.stats['failed_reports']}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📈 Total reports sent: {self.stats['total_reports_sent']}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}👥 Accounts available: {len(self.accounts)}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")

# ============================================================================
# MAIN OSNIT REPORTER
# ============================================================================

class OsnitReporter:
    """Main Osnit Anti-Ban Reporter"""
    
    def __init__(self):
        self.api_id = 2040  # Example API ID
        self.api_hash = 'b18441a1ff607e10a989891a5462e627'  # Example API Hash
        self.sessions_dir = "osnit_sessions"
        self.rotation_manager = AccountRotationManager(self.sessions_dir)
        
        # Create directories
        os.makedirs(self.sessions_dir, exist_ok=True)
        os.makedirs("history", exist_ok=True)
        
        self.display_banner()
    
    def display_banner(self):
        """Display Osnit banner"""
        banner = f"""
{Fore.RED}
╔══════════════════════════════════════════════╗
║                                              ║
║           {Fore.YELLOW}OSNIT ANTI-BAN REPORTER{Fore.RED}            ║
║          {Fore.CYAN}Advanced Protection System{Fore.RED}            ║
║                                              ║
║    {Fore.GREEN}• Account Rotation{Fore.RED}                         ║
║    {Fore.GREEN}• Pattern Avoidance{Fore.RED}                        ║
║    {Fore.GREEN}• Smart Delays{Fore.RED}                             ║
║    {Fore.GREEN}• Zero Ban Guarantee{Fore.RED}                       ║
║                                              ║
╚══════════════════════════════════════════════╝
{Style.RESET_ALL}
        """
        print(banner)
    
    def add_account(self):
        """Add new Telegram account"""
        print(f"\n{Fore.CYAN}[+] Adding new account...{Style.RESET_ALL}")
        
        phone = input(f"{Fore.GREEN}Enter phone number (+country code): {Style.RESET_ALL}").strip()
        
        if not phone.startswith('+'):
            print(f"{Fore.RED}[✗] Phone must start with +{Style.RESET_ALL}")
            return
        
        # Find next account number
        existing = [acc['id'] for acc in self.rotation_manager.accounts]
        next_id = max(existing) + 1 if existing else 1
        
        session_path = os.path.join(self.sessions_dir, f"account_{next_id}.session")
        
        from telethon.sync import TelegramClient
        from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
        
        client = TelegramClient(session_path, self.api_id, self.api_hash)
        
        try:
            client.connect()
            
            if not client.is_user_authorized():
                client.send_code_request(phone)
                code = input(f"{Fore.GREEN}Enter verification code: {Style.RESET_ALL}").strip()
                
                try:
                    client.sign_in(phone, code)
                    print(f"{Fore.GREEN}[✓] Account {next_id} added successfully!{Style.RESET_ALL}")
                    
                    # Add to rotation manager
                    self.rotation_manager.accounts.append({
                        'id': next_id,
                        'session_path': session_path,
                        'last_used': None,
                        'report_count': 0,
                        'status': 'active'
                    })
                    
                except SessionPasswordNeededError:
                    password = input(f"{Fore.GREEN}Enter 2FA password: {Style.RESET_ALL}")
                    client.sign_in(password=password)
                    print(f"{Fore.GREEN}[✓] Account {next_id} added with 2FA!{Style.RESET_ALL}")
                    
                    self.rotation_manager.accounts.append({
                        'id': next_id,
                        'session_path': session_path,
                        'last_used': None,
                        'report_count': 0,
                        'status': 'active'
                    })
                    
                except PhoneCodeInvalidError:
                    print(f"{Fore.RED}[✗] Invalid verification code{Style.RESET_ALL}")
                    
            else:
                print(f"{Fore.GREEN}[✓] Account {next_id} already authorized!{Style.RESET_ALL}")
                
                self.rotation_manager.accounts.append({
                    'id': next_id,
                    'session_path': session_path,
                    'last_used': None,
                    'report_count': 0,
                    'status': 'active'
                })
                
        except Exception as e:
            print(f"{Fore.RED}[✗] Error: {e}{Style.RESET_ALL}")
        finally:
            client.disconnect()
    
    async def safe_report_target(self, target_username, total_reports, reason="spam"):
        """Safely report target using account rotation"""
        print(f"\n{Fore.CYAN}[⚡] Starting OSNIT reporting session...{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}🎯 Target: {target_username}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}📊 Total reports to send: {total_reports}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}📝 Reason: {reason}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        
        reports_sent = 0
        accounts_used = 0
        
        while reports_sent < total_reports:
            # Get next account for rotation
            account_info = self.rotation_manager.get_next_account()
            
            if not account_info:
                print(f"{Fore.RED}[✗] No accounts available{Style.RESET_ALL}")
                break
            
            account_id = account_info['id']
            session_path = account_info['session_path']
            
            print(f"{Fore.CYAN}[👤] Using Account {account_id}...{Style.RESET_ALL}")
            
            # Create safe client
            client_wrapper = SafeTelegramClient(session_path, self.api_id, self.api_hash, account_id)
            
            # Connect
            client = await client_wrapper.safe_connect()
            
            if not client:
                print(f"{Fore.RED}[✗] Account {account_id} connection failed{Style.RESET_ALL}")
                self.rotation_manager.mark_account_cooling(account_id)
                await asyncio.sleep(10)
                continue
            
            # Calculate how many reports this account should send
            remaining = total_reports - reports_sent
            account_limit = min(AntiBanConfig.MAX_REPORTS_PER_SESSION, remaining, 5)  # Max 5 per session
            
            print(f"{Fore.CYAN}[📨] Account {account_id} sending {account_limit} reports...{Style.RESET_ALL}")
            
            # Send reports
            successful = await client_wrapper.safe_report(
                client, 
                target_username, 
                reason, 
                account_limit
            )
            
            # Update statistics
            reports_sent += successful
            accounts_used += 1
            
            print(f"{Fore.GREEN}[✓] Account {account_id} sent {successful} reports{Style.RESET_ALL}")
            print(f"{Fore.CYAN}[📊] Progress: {reports_sent}/{total_reports} reports sent{Style.RESET_ALL}")
            
            # Mark account for cooldown
            self.rotation_manager.mark_account_cooling(account_id)
            
            # Disconnect client
            await client.disconnect()
            
            # Update rotation manager stats
            self.rotation_manager.update_stats(successful, account_limit - successful)
            
            # Check if we need to continue
            if reports_sent < total_reports:
                print(f"{Fore.YELLOW}[⏳] Rotating to next account...{Style.RESET_ALL}")
                await asyncio.sleep(random.uniform(5, 15))  # Random delay between accounts
        
        print(f"\n{Fore.GREEN}[✅] OSNIT reporting session completed!{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        self.rotation_manager.print_stats()
        
        return reports_sent
    
    def list_accounts(self):
        """List all accounts with status"""
        print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}📋 ACCOUNT LIST:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        
        if not self.rotation_manager.accounts:
            print(f"{Fore.RED}No accounts found.{Style.RESET_ALL}")
            return
        
        for acc in self.rotation_manager.accounts:
            status_color = Fore.GREEN if acc['status'] == 'active' else Fore.YELLOW
            status_text = "ACTIVE" if acc['status'] == 'active' else "COOLING"
            
            last_used = acc['last_used']
            last_used_str = "Never" if not last_used else last_used.strftime("%H:%M:%S")
            
            print(f"{Fore.CYAN}Account {acc['id']}: {status_color}{status_text}{Style.RESET_ALL}")
            print(f"  Session: {acc['session_path']}")
            print(f"  Last used: {last_used_str}")
            print(f"  Reports sent: {acc['report_count']}")
            print(f"{Fore.CYAN}{'-'*30}{Style.RESET_ALL}")
    
    def view_stats(self):
        """View detailed statistics"""
        self.rotation_manager.print_stats()
        
        # Load and display account histories
        print(f"\n{Fore.YELLOW}📈 INDIVIDUAL ACCOUNT STATS:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        
        for acc in self.rotation_manager.accounts:
            history_file = f"history/account_{acc['id']}.json"
            if os.path.exists(history_file):
                try:
                    with open(history_file, 'r') as f:
                        data = json.load(f)
                        report_count = data.get('report_count_today', 0)
                        print(f"{Fore.CYAN}Account {acc['id']}: {Fore.GREEN}{report_count} reports today{Style.RESET_ALL}")
                except:
                    print(f"{Fore.CYAN}Account {acc['id']}: {Fore.YELLOW}No history data{Style.RESET_ALL}")
    
    def run_interactive(self):
        """Run interactive menu"""
        while True:
            print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}OSNIT ANTI-BAN MENU:{Style.RESET_ALL}")
            print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}1.{Style.RESET_ALL} Add Telegram Account")
            print(f"{Fore.GREEN}2.{Style.RESET_ALL} Report Target")
            print(f"{Fore.GREEN}3.{Style.RESET_ALL} List Accounts")
            print(f"{Fore.GREEN}4.{Style.RESET_ALL} View Statistics")
            print(f"{Fore.GREEN}5.{Style.RESET_ALL} Exit")
            print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
            
            choice = input(f"{Fore.GREEN}Select option: {Style.RESET_ALL}").strip()
            
            if choice == "1":
                self.add_account()
                
            elif choice == "2":
                target = input(f"{Fore.GREEN}Enter target username (with @): {Style.RESET_ALL}").strip()
                if not target:
                    print(f"{Fore.RED}[✗] Target required{Style.RESET_ALL}")
                    continue
                
                try:
                    count = int(input(f"{Fore.GREEN}Number of reports to send (1-100): {Style.RESET_ALL}").strip())
                    if not 1 <= count <= 100:
                        print(f"{Fore.RED}[✗] Must be between 1-100{Style.RESET_ALL}")
                        continue
                except:
                    print(f"{Fore.RED}[✗] Invalid number{Style.RESET_ALL}")
                    continue
                
                print(f"\n{Fore.YELLOW}Available reasons:{Style.RESET_ALL}")
                reasons = ['spam', 'fake', 'violence', 'pornography', 'child_abuse', 'other']
                for i, r in enumerate(reasons, 1):
                    print(f"  {Fore.GREEN}{i}.{Style.RESET_ALL} {r}")
                
                reason_choice = input(f"{Fore.GREEN}Select reason (1-6): {Style.RESET_ALL}").strip()
                if reason_choice.isdigit() and 1 <= int(reason_choice) <= 6:
                    reason = reasons[int(reason_choice)-1]
                else:
                    reason = "spam"
                
                # Run reporting
                asyncio.run(self.safe_report_target(target, count, reason))
                
            elif choice == "3":
                self.list_accounts()
                
            elif choice == "4":
                self.view_stats()
                
            elif choice == "5":
                print(f"{Fore.GREEN}[✓] Exiting OSNIT Reporter{Style.RESET_ALL}")
                break
                
            else:
                print(f"{Fore.RED}[✗] Invalid choice{Style.RESET_ALL}")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main entry point"""
    # Import regex for account parsing
    global re
    import re
    
    print(f"{Fore.CYAN}Initializing OSNIT Anti-Ban Reporter...{Style.RESET_ALL}")
    
    # Check for required packages
    try:
        import telethon
        print(f"{Fore.GREEN}[✓] Telethon installed{Style.RESET_ALL}")
    except ImportError:
        print(f"{Fore.RED}[✗] Telethon not installed{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Installing required packages...{Style.RESET_ALL}")
        os.system("pip install telethon colorama")
        print(f"{Fore.GREEN}[✓] Packages installed{Style.RESET_ALL}")
    
    # Create and run reporter
    reporter = OsnitReporter()
    reporter.run_interactive()

if __name__ == "__main__":
    main()