import os
import pwd
import logging
import telegram
import subprocess
import pwnagotchi
import random
from time import sleep
from pwnagotchi import fs
from pwnagotchi.ui import view
from pwnagotchi.voice import Voice
import pwnagotchi.plugins as plugins
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.botcommand import BotCommand
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    Updater,
)

home_dir = "/home/pi"
# TODO Get plugins dir from config file
plugins_dir = "/usr/local/share/pwnagotchi/custom-plugins"

main_menu = [
    [
        InlineKeyboardButton("🔄 Reboot", callback_data="reboot"),
        InlineKeyboardButton("🛑 Shutdown", callback_data="shutdown"),
        InlineKeyboardButton("⏰ Uptime", callback_data="uptime"),
    ],
    [
        InlineKeyboardButton("🤝 Handshake Count", callback_data="handshake_count"),
        InlineKeyboardButton(
            "🔓 Read WPA-Sec Cracked", callback_data="read_wpa_sec_cracked"
        ),
        InlineKeyboardButton(
            "📬 Fetch Pwngrid Inbox", callback_data="fetch_pwngrid_inbox"
        ),
    ],
    [
        InlineKeyboardButton("🧠 Read Memory & Temp", callback_data="read_memtemp"),
        InlineKeyboardButton("🎨 Take Screenshot", callback_data="take_screenshot"),
        InlineKeyboardButton("💾 Create Backup", callback_data="create_backup"),
    ],
    [
        InlineKeyboardButton("🔄 Update bot", callback_data="bot_update"),
        InlineKeyboardButton("🗡️  Kill the daemon", callback_data="pwnkill"),
        InlineKeyboardButton("🔁 Restart Daemon", callback_data="soft_restart"),
    ],
]

stickers_exception = [
    "CAACAgIAAxkBAAIKJGXHDISOASdXpKbXske2Q1IaVEMpAAIwAAMPdWsI7k_UrvN3piI0BA",
    "CAACAgIAAxkBAAIKJmXHDIji0_pKBLqYHJMHQkw3QzZ9AAIyAAMPdWsIBdtzkkhTXqY0BA",
    "CAACAgQAAxkBAAIKLmXHDM-ynEU2Int0s1YcpC3bqKK2AAIUAAPTrAoCbIyNeEmfdRo0BA",
    "CAACAgIAAxkBAAIKMmXHDOTYF93WIanWQLgh9FgR8SnpAALtDAACT6QpSMtoWq3QTPsONAQ",
]

stickers_kill_daemon = [
    "CAACAgQAAxkBAAIKKGXHDMFCsebQHdKaxBMwDJDpTrc7AAI5AAPTrAoCTTZZF0MD5og0BA",
]

stickers_handshake_or_wpa = [
    "CAACAgIAAxkBAAIKMGXHDNlSDzyw6spWefM0J7O9br61AAL6EAACoccoSDllduuTWAejNAQ",
    "CAACAgQAAxkBAAIKLGXHDMbkJgl6jf2fmkoz5WoSVO8KAAIcAAPTrAoC1E8xZAtCX8A0BA",
]


class Telegram(plugins.Plugin):
    __author__ = "WPA2"
    __version__ = "0.2.0"
    __license__ = "GPL3"
    __description__ = "Chats to telegram"
    __dependencies__ = ("python-telegram-bot==13.15",)

    def on_loaded(self):
        logging.info("[TELEGRAM] telegram plugin loaded.")
        self.logger = logging.getLogger("TelegramPlugin")
        self.options["auto_start"] = True
        self.completed_tasks = 0
        self.num_tasks = 8  # Increased for the new pwnkill task
        self.updater = None
        self.start_menu_sent = False

    def on_agent(self, agent):
        if "auto_start" in self.options and self.options["auto_start"]:
            self.on_internet_available(agent)

    def register_command_handlers(self, agent, dispatcher):
        dispatcher.add_handler(
            MessageHandler(
                Filters.regex("^/start$"),
                lambda update, context: self.start(agent, update, context),
            )
        )
        dispatcher.add_handler(
            CommandHandler(
                "reboot_to_manual",
                lambda update, context: self.reboot_mode("MANUAL", update, context),
            )
        )
        dispatcher.add_handler(
            CommandHandler(
                "reboot_to_auto",
                lambda update, context: self.reboot_mode("AUTO", update, context),
            )
        )
        dispatcher.add_handler(
            CommandHandler(
                "shutdown", lambda update, context: self.shutdown(update, context)
            )
        )
        dispatcher.add_handler(
            CommandHandler(
                "uptime", lambda update, context: self.uptime(agent, update, context)
            )
        )
        CommandHandler(
            "handshake_count",
            lambda update, context: self.handshake_count(agent, update, context),
        )
        CommandHandler(
            "read_wpa_sec_cracked",
            lambda update, context: self.read_wpa_sec_cracked(agent, update, context),
        )
        CommandHandler(
            "fetch_pwngrid_inbox",
            lambda update, context: self.handle_pwngrid_inbox(agent, update, context),
        )
        CommandHandler(
            "read_memtemp",
            lambda update, context: self.handle_memtemp(agent, update, context),
        )
        CommandHandler(
            "take_screenshot",
            lambda update, context: self.take_screenshot(agent, update, context),
        )
        CommandHandler(
            "create_backup",
            lambda update, context: self.create_backup(agent, update, context),
        )
        CommandHandler(
            "pwnkill", lambda update, context: self.pwnkill(agent, update, context)
        )
        CommandHandler(
            "soft_restart", lambda update, context: self.soft_restart(update)
        )
        CommandHandler(
            "soft_restart_to_manual",
            lambda update, context: self.soft_restart_mode("MANUAL", update, context),
        )
        CommandHandler(
            "soft_restart_to_auto",
            lambda update, context: self.soft_restart_mode("AUTO", update, context),
        )
        CommandHandler(
            "send_backup", lambda update, context: self.send_backup(update, context)
        )
        CommandHandler(
            "bot_update", lambda update, context: self.bot_update(update, context)
        )

        dispatcher.add_handler(
            CallbackQueryHandler(
                lambda update, context: self.button_handler(agent, update, context)
            )
        )

    def start(self, agent, update, context):
        # Verify if the user is authorized
        if update.effective_chat.id == int(self.options["chat_id"]):
            try:
                self.options["bot_name"]
            except:
                self.options["bot_name"] = "Pwnagotchi"

            bot_name = self.options["bot_name"]
            response = f"🖖 Welcome to <b>{bot_name}</b>\n\nPlease select an option:"
            reply_markup = InlineKeyboardMarkup(main_menu)
            try:
                update.message.reply_text(
                    response, reply_markup=reply_markup, parse_mode="HTML"
                )
            except AttributeError:
                self.update_existing_message(update, response, main_menu)
            except:
                update.effective_message.reply_text(
                    response, reply_markup=reply_markup, parse_mode="HTML"
                )
        return

    def button_handler(self, agent, update, context):
        if update.effective_chat.id == int(self.options["chat_id"]):
            query = update.callback_query
            query.answer()

            if query.data == "reboot":
                self.reboot(agent, update, context)
            elif query.data == "reboot_to_manual":
                self.reboot_mode("MANUAL", update, context)
            elif query.data == "reboot_to_auto":
                self.reboot_mode("AUTO", update, context)
            elif query.data == "shutdown":
                self.shutdown(update, context)
            elif query.data == "uptime":
                self.uptime(agent, update, context)
            elif query.data == "read_wpa_sec_cracked":
                self.read_wpa_sec_cracked(agent, update, context)
            elif query.data == "handshake_count":
                self.handshake_count(agent, update, context)
            elif query.data == "fetch_pwngrid_inbox":
                self.handle_pwngrid_inbox(agent, update, context)
            elif query.data == "read_memtemp":
                self.handle_memtemp(agent, update, context)
            elif query.data == "take_screenshot":
                self.take_screenshot(agent, update, context)
            elif query.data == "create_backup":
                self.last_backup = self.create_backup(agent, update, context)
            elif query.data == "pwnkill":
                self.pwnkill(agent, update, context)
            elif query.data == "start":
                self.start(agent, update, context)
            elif query.data == "soft_restart":
                self.soft_restart(update)
            elif query.data == "soft_restart_to_manual":
                self.soft_restart_mode("MANUAL", update, context)
            elif query.data == "soft_restart_to_auto":
                self.soft_restart_mode("AUTO", update, context)
            elif query.data == "send_backup":
                self.send_backup(update, context)
            elif query.data == "bot_update":
                self.bot_update(update, context)

            self.completed_tasks += 1
            if self.completed_tasks == self.num_tasks:
                self.terminate_program()

    # TODO Create a function to handle exceptions and send all the exceptions to that function

    def send_sticker(self, update, context, fileid):
        user_id = update.effective_message.chat_id
        context.bot.send_sticker(chat_id=user_id, sticker=fileid)

    def update_existing_message(self, update, text, keyboard=[]):
        try:
            old_message = update.callback_query
            old_message.answer()
            go_back_button = [
                InlineKeyboardButton("🔙 Go back", callback_data="start"),
            ]
            if keyboard != main_menu and go_back_button not in keyboard:
                # Add back button if the keyboard is not the main menu and the keyboard does not have the back button
                keyboard.append(go_back_button)
            old_message.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )
            # Reset keyboard
            keyboard = []
        except:
            if keyboard:
                update.effective_message.reply_text(
                    text, reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                update.effective_message.reply_text(text)
        return

    def run_as_user(self, cmd, user):
        uid = pwd.getpwnam(user).pw_uid
        os.setuid(uid)
        os.system(cmd)
        os.setuid(0)
        return

    def bot_update(self, update, context):
        logging.info("[TELEGRAM] Updating bot...")
        response = "🆙 Updating bot..."
        self.update_existing_message(update, response)
        chat_id = update.effective_user["id"]
        context.bot.send_chat_action(chat_id=chat_id, action="upload_document")
        try:
            # Change directory to /home/pi
            os.chdir(home_dir)

            # Check if the telegram-bot folder exists
            if not os.path.exists("telegram-bot"):
                # Clone the telegram-bot repository if it doesn't exist
                logging.debug("[TELEGRAM] Cloning telegram-bot repository...")
                subprocess.run(
                    [
                        "git",
                        "clone",
                        "https://github.com/wpa-2/telegram.py",
                        "telegram-bot",
                    ],
                    check=True,
                )

                # Add the repository as a safe directory as root
                logging.debug("[TELEGRAM] Adding telegram-bot repository as safe...")
                subprocess.run(
                    [
                        "git",
                        "config",
                        "--global",
                        "--add",
                        "safe.directory",
                        "/home/pi/telegram-bot",
                    ],
                    check=True,
                )
                # Add the repository as a safe directory as the pi user
                logging.debug(
                    "[TELEGRAM] Adding telegram-bot repository as safe for pi..."
                )
                self.run_as_user(
                    "git config --global --add safe.directory /home/pi/telegram-bot",
                    "pi",
                )

                # Create a symbolic link so when the bot is updated, the new version is used
                subprocess.run(
                    ["ln", "-sf", "/home/pi/telegram-bot/telegram.py", plugins_dir],
                    check=True,
                )
            # Change directory to telegram-bot
            os.chdir("telegram-bot")

            # Pull the latest changes from the repository
            logging.info(
                "[TELEGRAM] Pulling latest changes from telegram-bot repository..."
            )
            subprocess.run(["git", "pull"], check=True)

        except subprocess.CalledProcessError as e:
            # Handle errors
            logging.error(f"[TELEGRAM] Error updating bot: {e}")
            response = f"⛔ Error updating bot: <code>{e}</code>"
            update.effective_message.reply_text(response, parse_mode="HTML")
            return

        # Send a message indicating success
        response = "✅ Bot updated <b>successfully!</b>"
        self.update_existing_message(update, response)
        return

    def take_screenshot(self, agent, update, context):
        try:
            chat_id = update.effective_user["id"]
            context.bot.send_chat_action(chat_id, "upload_photo")
            display = agent.view()
            picture_path = "/root/pwnagotchi_screenshot.png"

            # Capture screenshot
            screenshot = display.image()

            # Capture the screen rotation value and rotate the image (x degrees) before saving
            # If there is no rotation value, the default value is 0

            rotation_degree = self.options.get("rotation", 0)

            rotated_screenshot = screenshot.rotate(rotation_degree)

            # Save the rotated image
            rotated_screenshot.save(picture_path, "png")

            with open(picture_path, "rb") as photo:
                context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo)

            response = "✅ Screenshot taken and sent!"
        except Exception as e:
            self.send_sticker(update, context, random.choice(stickers_exception))
            response = f"⛔ Error taking screenshot: <code>{e}</code>"

        update.effective_message.reply_text(response, parse_mode="HTML")

    def reboot(self, agent, update, context):
        keyboard = [
            [
                InlineKeyboardButton(
                    "🤖 Reboot to manual mode", callback_data="reboot_to_manual"
                ),
                InlineKeyboardButton(
                    "🛜 Reboot to auto mode", callback_data="reboot_to_auto"
                ),
            ],
        ]

        text = "⚠️  This will restart the device, not the daemon.\nSSH or bluetooth will be interrupted\nPlease select an option:"
        self.update_existing_message(update, text, keyboard)
        return

    def reboot_mode(self, mode, update, context):
        if mode is not None:
            mode = mode.upper()
            reboot_text = f"🔄 rebooting in <b>{mode}</b> mode"
        else:
            reboot_text = "🔄 rebooting..."

        try:
            response = reboot_text
            logging.warning("[TELEGRAM]", reboot_text)

            self.update_existing_message(update, response)

            if view.ROOT:
                view.ROOT.on_custom("Rebooting...")
                # give it some time to refresh the ui
                sleep(10)

            if mode == "AUTO":
                subprocess.run(["sudo", "touch", "/root/.pwnagotchi-auto"])
            elif mode == "MANU":
                subprocess.run(["sudo", "touch", "/root/.pwnagotchi-manual"])

            logging.warning("[TELEGRAM] syncing...")

            for m in fs.mounts:
                m.sync()

            subprocess.run(["sudo", "sync"])
            subprocess.run(["sudo", "reboot"])
        except Exception as e:
            self.send_sticker(update, context, random.choice(stickers_exception))
            logging.error(f"[TELEGRAM] Error rebooting: {e}")
            response = f"⛔ Error rebooting: <b>{e}</b>"
            update.effective_message.reply_text(response)

    def shutdown(self, update, context):
        response = "📴 Shutting down <b>now</b>..."
        self.update_existing_message(update, response)
        logging.warning("[TELEGRAM] shutting down ...")

        try:
            if view.ROOT:
                view.ROOT.on_shutdown()
                # Give it some time to refresh the ui
                sleep(10)

            logging.warning("[TELEGRAM] syncing...")

            for m in fs.mounts:
                m.sync()

            subprocess.run(["sudo", "sync"])
            subprocess.run(["sudo", "halt"])
        except Exception as e:
            self.send_sticker(update, context, random.choice(stickers_exception))
            logging.error(f"[TELEGRAM] Error shutting down: {e}")
            response = f"⛔ Error shutting down: <code>{e}</code>"
            update.effective_message.reply_text(response)
        return

    def soft_restart(self, update):
        keyboard = [
            [
                InlineKeyboardButton(
                    "🤖 Restart to manual mode", callback_data="soft_restart_to_manual"
                ),
                InlineKeyboardButton(
                    "🛜 Restart to auto mode", callback_data="soft_restart_to_auto"
                ),
            ],
        ]

        text = "⚠️  This will restart the daemon, not the device.\nSSH or bluetooth will not be interrupted\nPlease select an option:"
        self.update_existing_message(update, text, keyboard)
        return

    def soft_restart_mode(self, mode, update, context):
        logging.warning("[TELEGRAM] restarting in %s mode ...", mode)
        response = f"🔃 Restarting in <b>{mode}</b> mode..."
        self.update_existing_message(update, response)

        if view.ROOT:
            view.ROOT.on_custom(f"Restarting daemon to {mode}")
            sleep(10)
        try:
            mode = mode.upper()
            if mode == "AUTO":
                subprocess.run(["sudo", "touch", "/root/.pwnagotchi-auto"])
            else:
                subprocess.run(["sudo", "touch", "/root/.pwnagotchi-manual"])

            subprocess.run(["sudo", "systemctl", "restart", "pwnagotchi"])
        except Exception as e:
            self.send_sticker(update, context, random.choice(stickers_exception))
            logging.error(f"[TELEGRAM] Error restarting: {e}")
            response = f"⛔ Error restarting: <code>{e}</code>"
            update.effective_message.reply_text(response, parse_mode="HTML")
        return

    def uptime(self, agent, update, context):
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])

        uptime_minutes = uptime_seconds / 60
        uptime_hours = int(uptime_minutes // 60)
        uptime_remaining_minutes = int(uptime_minutes % 60)

        response = (
            f"⏰ Uptime: {uptime_hours} hours and {uptime_remaining_minutes} minutes"
        )
        self.update_existing_message(update, response)

        self.completed_tasks += 1
        if self.completed_tasks == self.num_tasks:
            self.terminate_program()
        return

    def pwnkill(self, agent, update, context):
        try:
            response = "⏰ Sending <code>pwnkill</code> to pwnagotchi..."
            self.send_sticker(update, context, random.choice(stickers_kill_daemon))
            update.effective_message.reply_text(response, parse_mode="HTML")
            # TODO Maybe it's better to use systemctl stop pwnagotchi? To turn it off gracefully?
            subprocess.run(["sudo", "killall", "-USR1", "pwnagotchi"])
        except subprocess.CalledProcessError as e:
            response = f"⛔ Error executing pwnkill command: <code>{e}</code>"
            update.effective_message.reply_text(response, parse_mode="HTML")

    def format_handshake_pot_files(self, file_path):
        try:
            messages_list = []
            message = ""

            with open(file_path, "r") as file:
                content = file.readlines()
                for line in content:
                    pwned = line.split(":")[2:]
                    if len(message + line) > 4096:
                        messages_list.append(message)
                        message = ""
                    # This code formatting allow us to copy the code block with one tap
                    # SSID:password
                    message += ":<code>".join(pwned)
                    message = message + "</code>"
                messages_list.append(message)
            return messages_list

        except subprocess.CalledProcessError as e:
            return [f"⛔ Error reading file: {e}"]

    def read_wpa_sec_cracked(self, agent, update, context):
        # TODO Read every .potfile available
        file_path = "/root/handshakes/wpa-sec.cracked.potfile"
        chunks = self.format_handshake_pot_files(file_path)
        if not chunks or not any(chunk.strip() for chunk in chunks):
            self.update_existing_message(
                text="The wpa-sec.cracked.potfile is empty.", update=update
            )
        else:
            self.send_sticker(update, context, random.choice(stickers_handshake_or_wpa))
            chat_id = update.effective_user["id"]
            context.bot.send_chat_action(chat_id, "typing")
            import time

            message_counter = 0
            for chunk in chunks:
                if message_counter >= 20:
                    response = "💤 Sleeping for <b>60</b> seconds to avoid <i>flooding</i> the chat..."
                    update.effective_message.reply_text(response)
                    time.sleep(60)
                    context.bot.send_chat_action(chat_id, "typing", timeout=60)
                    message_counter = 0
                update.effective_message.reply_text(chunk, parse_mode="HTML")
                message_counter += 1

        self.completed_tasks += 1
        if self.completed_tasks == self.num_tasks:
            self.terminate_program()

    def handshake_count(self, agent, update, context):
        handshake_dir = "/root/handshakes/"
        count = len(
            [
                name
                for name in os.listdir(handshake_dir)
                if os.path.isfile(os.path.join(handshake_dir, name))
            ]
        )

        response = f"🤝 Total handshakes captured: <b>{count}</b>"
        self.update_existing_message(update, response)
        self.send_sticker(update, context, random.choice(stickers_handshake_or_wpa))
        self.completed_tasks += 1
        if self.completed_tasks == self.num_tasks:
            self.terminate_program()
        return

    def fetch_inbox(self):
        command = "sudo pwngrid -inbox"
        output = subprocess.check_output(command, shell=True).decode("utf-8")
        lines = output.split("\n")
        formatted_output = []
        for line in lines:
            if "│" in line:
                message = line.split("│")[1:4]
                formatted_message = (
                    "ID: "
                    + message[0].strip().replace("\x1b[2m", "").replace("\x1b[0m", "")
                    + "\n"
                    + "Date: "
                    + message[1].strip().replace("\x1b[2m", "").replace("\x1b[0m", "")
                    + "\n"
                    + "Sender: "
                    + message[2].strip().replace("\x1b[2m", "").replace("\x1b[0m", "")
                )
                formatted_output.append(formatted_message)

        if len(formatted_output) > 0:
            formatted_output.pop(0)

        return "\n".join(formatted_output)

    def handle_pwngrid_inbox(self, agent, update, context):
        reply = self.fetch_inbox()
        if reply:
            context.bot.send_message(chat_id=update.effective_chat.id, text=reply)
        else:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="No messages found in Pwngrid inbox.",
            )

    def on_internet_available(self, agent):
        if hasattr(self, "telegram_connected") and self.telegram_connected:
            return

        config = agent.config()
        display = agent.view()
        last_session = agent.last_session

        try:
            logging.info("[TELEGRAM] Connecting to Telegram...")
            bot = telegram.Bot(self.options["bot_token"])
            bot.set_my_commands(
                commands=[
                    # Add all the buttons actions as commands
                    BotCommand(command="start", description="See buttons menu"),
                    BotCommand(
                        command="reboot_to_manual",
                        description="Reboot the device to manual mode",
                    ),
                    BotCommand(
                        command="reboot_to_auto",
                        description="Reboot the device to auto mode",
                    ),
                    BotCommand(command="shutdown", description="Shutdown the device"),
                    BotCommand(
                        command="uptime", description="Get the uptime of the device"
                    ),
                    BotCommand(
                        command="handshake_count", description="Get the handshake count"
                    ),
                    BotCommand(
                        command="read_wpa_sec_cracked",
                        description="Read the wpa-sec.cracked.potfile",
                    ),
                    BotCommand(
                        command="fetch_pwngrid_inbox",
                        description="Fetch the Pwngrid inbox",
                    ),
                    BotCommand(
                        command="read_memtemp",
                        description="Read memory and temperature",
                    ),
                    BotCommand(
                        command="take_screenshot", description="Take a screenshot"
                    ),
                    BotCommand(command="create_backup", description="Create a backup"),
                    BotCommand(command="bot_update", description="Update the bot"),
                    BotCommand(command="pwnkill", description="Kill the daemon"),
                    BotCommand(
                        command="soft_restart_to_manual",
                        description="Restart the daemon to manual mode",
                    ),
                    BotCommand(
                        command="soft_restart_to_auto",
                        description="Restart the daemon to auto mode",
                    ),
                    BotCommand(
                        command="send_backup",
                        description="Send the backup if it is available",
                    ),
                ],
            )
            if self.updater is None:
                self.updater = Updater(
                    token=self.options["bot_token"], use_context=True
                )
                self.register_command_handlers(agent, self.updater.dispatcher)
                self.updater.start_polling()

            if not self.start_menu_sent:
                try:
                    self.options["bot_name"]
                except:
                    self.options["bot_name"] = "Pwnagotchi"

                bot_name = self.options["bot_name"]
                response = (
                    f"🖖 Welcome to <b>{bot_name}!</b>\n\nPlease select an option:"
                )
                reply_markup = InlineKeyboardMarkup(main_menu)
                bot.send_message(
                    chat_id=self.options["chat_id"],
                    text=response,
                    reply_markup=reply_markup,
                    parse_mode="HTML",
                )
                self.start_menu_sent = True

            self.telegram_connected = True

        except Exception as e:
            self.logger.error("Error while sending on Telegram")
            self.logger.error(str(e))

        if last_session.is_new() and last_session.handshakes > 0:
            msg = f"Session started at {last_session.started_at()} and captured {last_session.handshakes} new handshakes"
            self.send_notification(msg)

            if last_session.is_new() and last_session.handshakes > 0:
                message = Voice(lang=config["main"]["lang"]).on_last_session_tweet(
                    last_session
                )
                if self.options["send_message"] is True:
                    bot.sendMessage(
                        chat_id=self.options["chat_id"],
                        text=message,
                        disable_web_page_preview=True,
                    )
                    self.logger.info("telegram: message sent: %s" % message)

                picture = "/root/pwnagotchi.png"
                display.on_manual_mode(last_session)
                display.image().save(picture, "png")
                display.update(force=True)

                if self.options["send_picture"] is True:
                    bot.sendPhoto(
                        chat_id=self.options["chat_id"], photo=open(picture, "rb")
                    )
                    self.logger.info("telegram: picture sent")

                last_session.save_session_id()
                display.set("status", "Telegram notification sent!")
                display.update(force=True)

    def handle_memtemp(self, agent, update, context):
        reply = f"Memory Usage: {int(pwnagotchi.mem_usage() * 100)}%\n\nCPU Load: {int(pwnagotchi.cpu_load() * 100)}%\n\nCPU Temp: {pwnagotchi.temperature()}c"
        self.update_existing_message(update, reply)
        return

    def create_backup(self, agent, update, context):
        context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        backup_files = [
            "/root/brain.json",
            "/root/.api-report.json",
            "/root/handshakes/",
            "/root/peers/",
            "/etc/pwnagotchi/",
            "/var/log/pwnagotchi.log",
        ]

        # Get datetime

        from datetime import datetime

        current_time = datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%d-%H:%M:%S")

        backup_file_name = f"pwnagotchi-backup-{formatted_time}.tar.gz"
        backup_tar_path = f"/root/{backup_file_name}"

        try:
            # Create a tarball
            subprocess.run(["sudo", "tar", "czf", backup_tar_path] + backup_files)

            # Move the tarball to /home/pi/
            subprocess.run(["sudo", "mv", backup_tar_path, "/home/pi/"])

            logging.info("[TELEGRAM] Backup created and moved successfully.")

        except Exception as e:
            self.send_sticker(update, context, random.choice(stickers_exception))
            logging.error(f"[TELEGRAM] Error creating or moving backup: {e}")

        # Obtain the file size

        # Get the size on bytes
        file_size = os.path.getsize(f"/home/pi/{backup_file_name}")
        # Convert to mb
        file_size /= 1024 * 1024
        # Round to 2 decimal places
        file_size = round(file_size, 2)
        keyboard = [
            [
                InlineKeyboardButton(
                    "📤 Send me the backup here", callback_data="send_backup"
                ),
            ],
        ]

        response = f"✅ Backup created and moved successfully to <code>/home/pi</code>.\nFile size: <b>{file_size} MB</b>"
        self.update_existing_message(update, response, keyboard)
        self.completed_tasks += 1
        if self.completed_tasks == self.num_tasks:
            self.terminate_program()
        return backup_file_name

    def send_backup(self, update, context):
        chat_id = update.effective_user["id"]
        context.bot.send_chat_action(chat_id, "upload_document")

        try:
            backup = self.last_backup
            if backup:
                logging.info(f"[TELEGRAM] Sending backup: {backup}")
                backup_path = f"/home/pi/{backup}"
                with open(backup_path, "rb") as backup_file:
                    update.effective_chat.send_document(document=backup_file)
                update.effective_message.reply_text("Backup sent successfully.")
            else:
                logging.error("[TELEGRAM] No backup file found.")
                update.effective_message.reply_text("No backup file found.")
        except Exception as e:
            self.send_sticker(update, context, random.choice(stickers_exception))
            logging.error(f"[TELEGRAM] Error sending backup: {e}")
            response = f"⛔ Error sending backup: <code>{e}</code>"
            update.effective_message.reply_text(response, parse_mode="HTML")

    def on_handshake(self, agent, filename, access_point, client_station):
        config = agent.config()
        display = agent.view()

        try:
            self.logger.info("Connecting to Telegram...")

            bot = telegram.Bot(self.options["bot_token"])

            message = f"🤝 New handshake captured: {access_point['hostname']} - {client_station['mac']}"
            if self.options["send_message"] is True:
                bot.sendMessage(
                    chat_id=self.options["chat_id"],
                    text=message,
                    disable_web_page_preview=True,
                )
                self.logger.info("telegram: message sent: %s" % message)

            display.set("status", "Telegram notification sent!")
            display.update(force=True)
        except Exception:
            self.logger.exception("Error while sending on Telegram")

    def terminate_program(self):
        logging.info("[TELEGRAM] All tasks completed. Terminating program.")


if __name__ == "__main__":
    plugin = Telegram()
    plugin.on_loaded()
