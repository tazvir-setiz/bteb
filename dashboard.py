import logging
from typing import Dict, Any, Optional
from bale_client import BaleClient
from eitaa_client import EitaaClient, EitaaError
from config import ConfigManager

logger = logging.getLogger(__name__)

class AdminDashboard:
    """
    Manages the interactive admin dashboard inside Bale.
    Provides inline keyboards, status inspection, and wizard forms for configuring
    Eitaa API key, Bale channel, and Eitaa channel.
    """
    def __init__(self, bale_client: BaleClient, eitaa_client: EitaaClient, config: ConfigManager):
        self.bale_client = bale_client
        self.eitaa_client = eitaa_client
        self.config = config
        # State tracking: user_id -> state_name
        self.user_states: Dict[int, str] = {}

    def _mask_token(self, token: str) -> str:
        if not token:
            return "❌ تنظیم نشده"
        if len(token) <= 8:
            return token[:2] + "****" + token[-2:]
        return token[:4] + "****" + token[-4:]

    def _build_dashboard_text(self) -> str:
        eitaa_token = self.config.get_eitaa_token()
        eitaa_channel = self.config.get_eitaa_channel()
        bale_channel = self.config.get_bale_channel()
        forwarding_on = self.config.is_forwarding_enabled()
        stats = self.config.get_stats()

        status_icon = "🟢 فعال" if forwarding_on else "🔴 متوقف"
        eitaa_chan_display = f"@{eitaa_channel}" if eitaa_channel else "❌ تنظیم نشده"
        bale_chan_display = bale_channel if bale_channel else "❌ تنظیم نشده"

        text = (
            "🎛 **داشبورد مدیریت انتقال پیام (بله به ایتا)**\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🔹 **وضعیت ارسال:** {status_icon}\n"
            f"🔑 **کلید API ایتا یار:** `{self._mask_token(eitaa_token)}`\n"
            f"📢 **کانال مقصد ایتا:** `{eitaa_chan_display}`\n"
            f"📥 **کانال مبدا بله:** `{bale_chan_display}`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 **آمار ارسال‌ها:** {stats['total_forwarded']} موفق | {stats['total_failed']} ناموفق\n"
            f"🕒 **آخرین انتقال:** {stats['last_forwarded_at'] or 'هنوز ارسالی انجام نشده'}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "جهت ویرایش هر بخش، از دکمه‌های زیر استفاده کنید:"
        )
        return text

    def _build_dashboard_keyboard(self) -> Dict[str, Any]:
        forwarding_on = self.config.is_forwarding_enabled()
        toggle_label = "⏸ توقف ارسال" if forwarding_on else "▶️ فعال‌سازی ارسال"

        return {
            "inline_keyboard": [
                [
                    {"text": toggle_label, "callback_data": "toggle_forward"}
                ],
                [
                    {"text": "🔑 تنظیم توکن ایتا یار", "callback_data": "set_eitaa_token"},
                    {"text": "📢 تنظیم کانال ایتا", "callback_data": "set_eitaa_channel"}
                ],
                [
                    {"text": "📥 تنظیم کانال بله", "callback_data": "set_bale_channel"},
                    {"text": "🔍 تست اتصال ایتا", "callback_data": "test_eitaa"}
                ],
                [
                    {"text": "📊 گزارش و آمار", "callback_data": "view_stats"},
                    {"text": "❓ راهنمای راه‌اندازی", "callback_data": "help"}
                ],
                [
                    {"text": "🔄 بروزرسانی صفحه", "callback_data": "refresh_dash"}
                ]
            ]
        }

    async def send_dashboard(self, chat_id: int) -> None:
        """Send the main dashboard message."""
        text = self._build_dashboard_text()
        keyboard = self._build_dashboard_keyboard()
        await self.bale_client.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    async def handle_message(self, message: Dict[str, Any]) -> None:
        """Process incoming private messages from users / admins."""
        chat = message.get("chat", {})
        from_user = message.get("from", {})
        user_id = from_user.get("id") or chat.get("id")
        text = (message.get("text") or "").strip()

        if not user_id:
            return

        # If no admins configured, make the first user who sends /start an admin!
        if not self.config.has_admins():
            self.config.add_admin(user_id)
            logger.info(f"Initialized first admin user: {user_id}")
            await self.bale_client.send_message(
                chat_id=user_id,
                text="🎉 شما به عنوان مدیر اصلی ربات ثبت شدید!"
            )
            await self.send_dashboard(user_id)
            return

        # Check authorization
        if not self.config.is_admin(user_id):
            await self.bale_client.send_message(
                chat_id=user_id,
                text="⚠️ دسترسی غیرمجاز. شما ادمین این ربات نیستید."
            )
            return

        # Commands
        if text in ["/start", "/dashboard", "/settings", "/panel"]:
            self.user_states.pop(user_id, None)
            await self.send_dashboard(user_id)
            return

        if text == "/cancel":
            self.user_states.pop(user_id, None)
            await self.bale_client.send_message(
                chat_id=user_id,
                text="عملیات لغو شد."
            )
            await self.send_dashboard(user_id)
            return

        # Check state machine
        current_state = self.user_states.get(user_id)
        if not current_state:
            await self.send_dashboard(user_id)
            return

        if current_state == "awaiting_eitaa_token":
            self.config.set_eitaa_token(text)
            self.eitaa_client.token = text
            self.user_states.pop(user_id, None)
            await self.bale_client.send_message(
                chat_id=user_id,
                text=f"✅ کلید API ایتا یار با موفقیت تنظیم شد:\n`{self._mask_token(text)}`",
                parse_mode="Markdown"
            )
            await self.send_dashboard(user_id)

        elif current_state == "awaiting_eitaa_channel":
            self.config.set_eitaa_channel(text)
            self.user_states.pop(user_id, None)
            clean_chan = self.config.get_eitaa_channel()
            await self.bale_client.send_message(
                chat_id=user_id,
                text=f"✅ کانال مقصد ایتا با موفقیت ثبت شد:\n`@{clean_chan}`",
                parse_mode="Markdown"
            )
            await self.send_dashboard(user_id)

        elif current_state == "awaiting_bale_channel":
            self.config.set_bale_channel(text)
            self.user_states.pop(user_id, None)
            await self.bale_client.send_message(
                chat_id=user_id,
                text=f"✅ کانال مبدا بله با موفقیت ثبت شد:\n`{text}`",
                parse_mode="Markdown"
            )
            await self.send_dashboard(user_id)

    async def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        """Handle inline keyboard button interactions."""
        cb_id = callback_query.get("id")
        from_user = callback_query.get("from", {})
        user_id = from_user.get("id")
        data = callback_query.get("data", "")
        message = callback_query.get("message", {})
        chat_id = message.get("chat", {}).get("id") or user_id
        msg_id = message.get("message_id")

        if not self.config.is_admin(user_id):
            await self.bale_client.answer_callback_query(
                callback_query_id=cb_id,
                text="⚠️ شما دسترسی به تنظیمات ندارید.",
                show_alert=True
            )
            return

        # Acknowledge callback immediately
        await self.bale_client.answer_callback_query(callback_query_id=cb_id)

        cancel_keyboard = {
            "inline_keyboard": [
                [{"text": "❌ انصراف و بازگشت", "callback_data": "cancel_action"}]
            ]
        }
        back_keyboard = {
            "inline_keyboard": [
                [{"text": "🔙 بازگشت به داشبورد", "callback_data": "main_menu"}]
            ]
        }

        if data == "main_menu" or data == "refresh_dash":
            self.user_states.pop(user_id, None)
            text = self._build_dashboard_text()
            keyboard = self._build_dashboard_keyboard()
            try:
                await self.bale_client.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            except Exception:
                await self.send_dashboard(chat_id)

        elif data == "cancel_action":
            self.user_states.pop(user_id, None)
            text = self._build_dashboard_text()
            keyboard = self._build_dashboard_keyboard()
            await self.bale_client.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

        elif data == "toggle_forward":
            new_status = not self.config.is_forwarding_enabled()
            self.config.set_forwarding_enabled(new_status)
            text = self._build_dashboard_text()
            keyboard = self._build_dashboard_keyboard()
            await self.bale_client.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

        elif data == "set_eitaa_token":
            self.user_states[user_id] = "awaiting_eitaa_token"
            prompt_text = (
                "🔑 **تنظیم کلید API ایتا یار**\n\n"
                "لطفاً توکن دریافتی از پنل `eitaayar.ir` را ارسال کنید.\n"
                "(برای نمونه: `bot123456:abcdef...`)\n\n"
                "برای انصراف دکمه زیر را فشار دهید یا `/cancel` را بفرستید."
            )
            await self.bale_client.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=prompt_text,
                reply_markup=cancel_keyboard,
                parse_mode="Markdown"
            )

        elif data == "set_eitaa_channel":
            self.user_states[user_id] = "awaiting_eitaa_channel"
            prompt_text = (
                "📢 **تنظیم کانال مقصد در ایتا**\n\n"
                "لطفاً شناسه یکتای کانال ایتا (یا آیدی کانال بدون @) را ارسال نمایید.\n"
                "مثال: `my_news_channel` یا `1404`\n\n"
                "📌 دقت کنید ربات ایتایار باید در کانال مقصد به عنوان ادمین با دسترسی ارسال پیام عضو شده باشد."
            )
            await self.bale_client.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=prompt_text,
                reply_markup=cancel_keyboard,
                parse_mode="Markdown"
            )

        elif data == "set_bale_channel":
            self.user_states[user_id] = "awaiting_bale_channel"
            prompt_text = (
                "📥 **تنظیم کانال مبدا در بله**\n\n"
                "لطفاً شناسه عددی کانال بله یا آیدی عمومی کانال را ارسال کنید.\n"
                "مثال عددی: `-1001234567890` یا آیدی: `@my_bale_channel`\n\n"
                "📌 توجه: ربات باید در این کانال بله به عنوان مدیر (Admin) اضافه شده باشد تا پیام‌ها را دریافت کند."
            )
            await self.bale_client.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=prompt_text,
                reply_markup=cancel_keyboard,
                parse_mode="Markdown"
            )

        elif data == "test_eitaa":
            token = self.config.get_eitaa_token()
            if not token:
                await self.bale_client.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text="❌ کلید API ایتا یار تنظیم نشده است. ابتدا توکن را ثبت کنید.",
                    reply_markup=back_keyboard
                )
                return

            self.eitaa_client.token = token
            try:
                res = await self.eitaa_client.get_me()
                bot_info = res.get("result", {})
                info_text = (
                    "✅ **ارتباط با ایتا یار موفقیت‌آمیز بود!**\n\n"
                    f"👤 **نام:** {bot_info.get('first_name', '')}\n"
                    f"🆔 **شناسه:** `{bot_info.get('id', '')}`\n"
                    f"🏷 **نام کاربری:** `@{bot_info.get('username', '')}`"
                )
            except Exception as e:
                info_text = f"❌ **خطا در اتصال به ایتا:**\n`{str(e)}`"

            await self.bale_client.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=info_text,
                reply_markup=back_keyboard,
                parse_mode="Markdown"
            )

        elif data == "view_stats":
            stats = self.config.get_stats()
            stats_text = (
                "📊 **آمار و گزارش تفصیلی ربات**\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ تعداد پیام‌های ارسال شده: **{stats['total_forwarded']}**\n"
                f"❌ تعداد پیام‌های ناموفق: **{stats['total_failed']}**\n"
                f"🕒 آخرین زمان ارسال: **{stats['last_forwarded_at'] or 'ندارد'}**\n"
                f"⚡️ وضعیت سیستم: **{'فعال' if stats['forwarding_enabled'] else 'متوقف'}**\n"
            )
            stats_keyboard = {
                "inline_keyboard": [
                    [{"text": "🗑 صفر کردن آمار", "callback_data": "reset_stats"}],
                    [{"text": "🔙 بازگشت به داشبورد", "callback_data": "main_menu"}]
                ]
            }
            await self.bale_client.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=stats_text,
                reply_markup=stats_keyboard,
                parse_mode="Markdown"
            )

        elif data == "reset_stats":
            self.config.reset_stats()
            await self.bale_client.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text="✅ آمار ارسال با موفقیت صفر شد.",
                reply_markup=back_keyboard
            )

        elif data == "help":
            help_text = (
                "📖 **راهنمای گام‌به‌گام راه‌اندازی ربات**\n\n"
                "1️⃣ **دریافت توکن ایتا یار:**\n"
                "به سایت `https://eitaayar.ir` رفته، ثبت‌نام کنید و در بخش توکن، یک کلید API جدید بسازید و در دکمه «تنظیم توکن ایتا یار» قرار دهید.\n\n"
                "2️⃣ **کانال مبدا در بله:**\n"
                "ربات بله را در کانال مبدا عضو کرده و دسترسی مدیر (Admin) به آن بدهید. سپس شناسه یا آیدی کانال را در دکمه «تنظیم کانال بله» وارد کنید.\n\n"
                "3️⃣ **کانال مقصد در ایتا:**\n"
                "در پنل ایتا یار کانال خود را متصل کنید (یا طبق راهنما، بات ایتایار را ادمین کانال ایتا کنید) و نام کاربری کانال را در بخش «تنظیم کانال ایتا» بگذارید.\n\n"
                "4️⃣ **تست و بررسی:**\n"
                "از دکمه «تست اتصال ایتا» برای تایید درستی کلید API استفاده کنید."
            )
            await self.bale_client.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=help_text,
                reply_markup=back_keyboard,
                parse_mode="Markdown"
            )
