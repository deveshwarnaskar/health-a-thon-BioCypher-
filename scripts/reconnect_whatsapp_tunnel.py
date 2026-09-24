#!/usr/bin/env python3
"""Automatically reconnects Cloudflare tunnel and updates Meta WhatsApp Webhook Callback URL."""

import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config.settings import Settings


def main():
    settings = Settings()
    app_id = "1791447568650573"
    app_secret = settings.whatsapp.app_secret
    verify_token = settings.whatsapp.verify_token
    api_version = settings.whatsapp.api_version

    print("🔍 Checking existing cloudflared tunnel...")
    ps = subprocess.run(["pgrep", "-f", "cloudflared tunnel"], capture_output=True, text=True)
    
    # Try reading current tunnel URL from log if running
    tunnel_url = None
    log_path = os.path.expanduser("~/.gemini/antigravity-cli/brain/51128f38-11ab-41d7-97c1-642c4620e5f9/.system_generated/tasks/task-973.log")
    if os.path.exists(log_path):
        with open(log_path) as f:
            for line in f:
                m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if m:
                    tunnel_url = m.group(0)

    if not tunnel_url:
        print("❌ No active trycloudflare URL found. Please make sure cloudflared is running.")
        sys.exit(1)

    callback_url = f"{tunnel_url}/api/v2/webhooks/whatsapp"
    print(f"🌐 Found tunnel callback URL: {callback_url}")

    print("📡 Updating Meta Developer Webhook Subscription via Graph API...")
    app_token = f"{app_id}|{app_secret}"
    url = f"https://graph.facebook.com/{api_version}/{app_id}/subscriptions"
    params = urllib.parse.urlencode({
        "object": "whatsapp_business_account",
        "callback_url": callback_url,
        "verify_token": verify_token,
        "fields": "messages,account_alerts,account_review_update,account_update,calls,message_template_quality_update,message_template_status_update,phone_number_name_update,phone_number_quality_update,security",
        "access_token": app_token,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=params, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("success"):
                print("✅ Successfully updated Meta Webhook Callback URL!")
                print(f"👉 Meta Webhook is now actively delivering to: {callback_url}")
            else:
                print("⚠️ Unexpected response from Meta:", data)
    except Exception as e:
        print("❌ Error updating Meta Webhook:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
