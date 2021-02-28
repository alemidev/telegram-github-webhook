#!/usr/bin/env python
"""
This is a super simple Flask + python-telegram-bot microservice made to relay github updates to
Telegram. It will require manual configuration, a telegram bot and a publicly accessible IP
(where github can send updates). You should configure your repo-chat_id association insid
config.json, together with the bot token.
"""
import json
import io

from flask import Flask, request, redirect
from telegram import Bot, ParseMode

with open("config.json") as f:
    CONFIG = json.load(f)

BOT = Bot(CONFIG["token"])

app = Flask(__name__)  # Standard Flask app

@app.route("/", methods=["GET"])
def landing():
    """This should never be reached, just redirect to the github page"""
    return redirect('https://github.com/alemigliardi/telegram-github-webhook')

@app.route("/", methods=["POST"])
def github_push():
    """
    This is the main endpoint github will send updates to.
    Parse the POST data and send a telegram message
    """
    data = request.json
    if data["repository"]["name"] in CONFIG["repos"]:
        target = CONFIG["repos"][data["repository"]["name"]]
        if "commits" in data: # New commits
            out = f"<b>{data['repository']['full_name']}</b> | <i>new commits</i>\n"
            for commit in data["commits"]:
                out += (f"→ <code>{commit['author']['username']}</code> {commit['message']} " +
                        f"[<a href=\"{commit['url']}\">{commit['id'][:7]}</a>]\n")
            BOT.send_message(target, out, parse_mode=ParseMode.HTML)
        elif "hook" in data: # New webhook or maybe just the initial event?
            out = (f"<b>{data['repository']['full_name']}</b> | <i>new hook</i>\n" +
                   f"→ <u>{data['hook']['config']['url']}</u> [{','.join(data['hook']['events'])}]")
            BOT.send_message(target, out, parse_mode=ParseMode.HTML)
        elif "issue" in data: # Something happened in Issues
            if data["action"] == "opened":
                labels = ",".join([ l["name"] for l in data["issue"]["labels"] ])
                out =  (f"<b>{data['repository']['full_name']}</b> | " +
                        f"<code>{data['issue']['user']['login']}</code> <i>opened issue</i>\n" +
                        f"→ <u><a href=\"{data['issue']['url']}\">#{data['issue']['number']}" +
                        f"</a></u> <b>{data['issue']['title']}</b> {data['issue']['body']} " +
                        f"<u>[<i>{labels}</i>]</u>")
                BOT.send_message(target, out, parse_mode=ParseMode.HTML)
            elif data["action"] == "labeled": # Do we really care?
                pass
            else: # TODO do this in logging module
                print(f"[!] Not prepared to handle action \"{data['action']}\"\n")
                print(str(data))
                print()
        else: # Don't know what to do with this
            text = f"<b>{data['repository']['full_name']}</b> | <i>unmapped event</i>"
            out = io.BytesIO(json.dumps(data, indent=2).encode('utf-8'))
            out.name = "event.json"
            BOT.sendDocument(chat_id=target, document=out, caption=text, parse_mode=ParseMode.HTML)
    else: # TODO do this in logging module
        print("[!] Received event from unmapped repository\n")
        print(str(data))
        print() # separate with a blank line
    return "OK"

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=33333) # I have a NGINX proxy, do 0.0.0.0 to expose this service directly
