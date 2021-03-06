#!/usr/bin/env python
"""
telegram-github-webhook (or tgw) is a simple Flask + python-telegram-bot microservice made to
relay github updates in Telegram chats. It will require a telegram bot and a publicly accessible IP
(where github can send updates). You should configure your repo:chat_id association inside
config.json, together with the bot token.
"""
import logging, json, io, os

from flask import Flask, request, redirect
from telegram import Bot, ParseMode

with open("config.json") as f:
	config = json.load(f)
logger = logging.getLogger()
bot = Bot(config["token"])
app = Flask(__name__)  # Standard Flask app

@app.route("/", methods=["GET"])
def landing():
	"""This should never be reached, just redirect to the github page"""
	return redirect('https://github.com/alemigliardi/telegram-github-webhook')

@app.route("/", methods=["POST"])
def github_event():
	"""This is the main endpoint github will send updates to. Parse and send telegram message"""
	data = request.json
	if data["repository"]["name"] in config["repos"]:
		target = config["repos"][data["repository"]["name"]]
		if "commits" in data: # New commits
			out = f"<b>{data['repository']['full_name']}</b> | <i>new commits</i>\n"
			for commit in data["commits"]:
				out += (f"→ <code>{commit['author']['username']}</code> {commit['message']} " +
						f"[<a href=\"{commit['url']}\">{commit['id'][:7]}</a>]\n")
			bot.send_message(target, out, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
		elif "hook" in data: # New webhook or maybe just the initial event?
			out = (f"<b>{data['repository']['full_name']}</b> | <i>new hook</i>\n" +
				   f"→ <u>{data['hook']['config']['url']}</u> [{','.join(data['hook']['events'])}]")
			bot.send_message(target, out, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
		elif "member" in data:
			if data["action"] == "added":
				out =  (f"<b>{data['repository']['full_name']}</b> | <i>new collaborator</i>\n" +
						f"→ <u><a href=\"{data['member']['url']}\">{data['member']['login']}</a></u>")
				bot.send_message(target, out, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
			else:
				logger.error(" * [!] Not prepared to handle action \"%s\"\n> %s", data['action'], str(data))
				text = f"<b>{data['repository']['full_name']}</b> | <i>unmapped member event</i>"
				out = io.BytesIO(json.dumps(data, indent=2).encode('utf-8'))
				out.name = "member-event.json"
				bot.sendDocument(chat_id=target, document=out, caption=text, parse_mode=ParseMode.HTML)
		elif "issue" in data: # Something happened in Issues
			if data["action"] == "opened":
				out =  (f"<b>{data['repository']['full_name']}</b> | <i>opened issue</i>\n" +
						f"→ <u><a href=\"{data['issue']['url']}\">#{data['issue']['number']}" +
						f"</a></u> <b>{data['issue']['title']}</b> {data['issue']['body']}")
				bot.send_message(target, out, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
			elif data["action"] == "labeled":
				labels = ",".join([ l["name"] for l in data["issue"]["labels"] ])
				out =  (f"<b>{data['repository']['full_name']}</b> | <i>labeled issue</i>\n" +
						f"→ <u><a href=\"{data['issue']['url']}\">#{data['issue']['number']}" +
						f"</a></u> <b>{data['issue']['title']}</b> <u>[{labels}]</u>")
				bot.send_message(target, out, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
			elif data["action"] == "created" and "comment" in data:
				out =  (f"<b>{data['repository']['full_name']}</b> | <i>new issue comment</i>\n" +
						f"→ <u><a href=\"{data['issue']['url']}\">#{data['issue']['number']}" +
						f"</a></u> <code>{data['comment']['user']['login']}</code> : {data['comment']['body']}")
				bot.send_message(target, out, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
			else:
				logger.error(" * [!] Not prepared to handle action \"%s\"\n> %s", data['action'], str(data))
				text = f"<b>{data['repository']['full_name']}</b> | <i>unmapped issue event</i>"
				out = io.BytesIO(json.dumps(data, indent=2).encode('utf-8'))
				out.name = "issue-event.json"
				bot.sendDocument(chat_id=target, document=out, caption=text, parse_mode=ParseMode.HTML)
		elif "comment" in data: # New comment on commit or maybe on anything?
			out =  (f"<b>{data['repository']['full_name']}</b> | " +
					f"<code>{data['issue']['user']['login']}</code> <i>new comment</i>\n" +
					f"→ [<a href=\"{data['comment']['url']}\">{data['comment']['commit_id'][:7]}</a>] " +
					f"<code>{data['comment']['user']['login']}</code> : {data['comment']['body']}")
			bot.send_message(target, out, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
		else: # Don't know (yet) what to do with this
			logger.error(" * [!] Not prepared to handle update\n> %s", str(data))
			text = f"<b>{data['repository']['full_name']}</b> | <i>unmapped event</i>"
			out = io.BytesIO(json.dumps(data, indent=2).encode('utf-8'))
			out.name = "event.json"
			bot.sendDocument(chat_id=target, document=out, caption=text, parse_mode=ParseMode.HTML)
	else:
		logger.warning(" * Received event from unmapped repository\n> %s", str(data))
	return "OK"

if __name__ == "__main__":
	app.run( # if you don't have a reverse proxy to put in front of this, set host 0.0.0.0
		host= os.environ["TGW_HOST"] if "TGW_HOST" in os.environ else "127.0.0.1",
		port= int(os.environ["TGW_PORT"]) if "TGW_PORT" in os.environ else 33333
	)
