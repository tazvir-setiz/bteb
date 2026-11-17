import logging
from typing import Optional, Dict, Any, Union
import httpx

logger = logging.getLogger(__name__)

class EitaaError(Exception):
    """Base exception for Eitaa API errors."""
    pass

class EitaaAuthError(EitaaError):
    """Raised when the Eitaa token is invalid or unauthorized."""
    pass

class EitaaAPIError(EitaaError):
    """Raised when Eitaa returns ok: false or HTTP error."""
    pass

class EitaaNetworkError(EitaaError):
    """Raised when network request to Eitaa fails."""
    pass

class EitaaClient:
    """
    Client for Eitaayar API (https://eitaayar.ir).
    """
    BASE_URL = "https://eitaayar.ir/api"

    def __init__(self, token: str, http_client: Optional[httpx.AsyncClient] = None, timeout: float = 30.0):
        self.token = token.strip()
        self._external_client = http_client is not None
        self._http_client = http_client or httpx.AsyncClient(timeout=timeout)

    def _get_url(self, method: str) -> str:
        return f"{self.BASE_URL}/{self.token}/{method}"

    def _process_response(self, response: httpx.Response) -> Dict[str, Any]:
        data = None
        try:
            data = response.json()
        except Exception:
            pass

        if response.status_code == 401:
            desc = data.get("description", "Unauthorized or invalid token") if isinstance(data, dict) else "Unauthorized"
            raise EitaaAuthError(f"توکن نامعتبر: {desc}")

        if data is None:
            raise EitaaAPIError(f"پاسخ نامعتبر از سرور ایتا: {response.text}")

        if not isinstance(data, dict):
            raise EitaaAPIError(f"فرمت پاسخ دریافتی از ایتا نادرست است: {data}")

        if not data.get("ok"):
            desc = data.get("description", "خطای نامشخص از ایتا")
            if "unauthorized" in desc.lower() or "token" in desc.lower():
                raise EitaaAuthError(f"خطای اعتبارسنجی ایتا: {desc}")
            raise EitaaAPIError(f"خطای ایتا: {desc}")

        return data

    async def get_me(self) -> Dict[str, Any]:
        """
        Calls getMe method to verify bot token and info.
        """
        url = self._get_url("getMe")
        try:
            resp = await self._http_client.get(url)
            return self._process_response(resp)
        except httpx.RequestError as e:
            logger.error(f"Network error connecting to Eitaa: {e}")
            raise EitaaNetworkError(f"عدم برقراری ارتباط با سرور ایتا: {e}") from e

    async def send_message(
        self,
        chat_id: str,
        text: str,
        title: Optional[str] = None,
        disable_notification: Optional[int] = None,
        reply_to_message_id: Optional[int] = None,
        date: Optional[int] = None,
        pin: Optional[int] = None,
        view_count_for_delete: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Sends text message to Eitaa channel or chat.
        chat_id can be channel ID or username without @.
        """
        url = self._get_url("sendMessage")
        # Clean chat_id if @ included
        if chat_id.startswith("@"):
            chat_id = chat_id[1:]

        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if title:
            payload["title"] = title
        if disable_notification is not None:
            payload["disable_notification"] = disable_notification
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id
        if date is not None:
            payload["date"] = date
        if pin is not None:
            payload["pin"] = pin
        if view_count_for_delete is not None:
            payload["viewCountForDelete"] = view_count_for_delete

        try:
            resp = await self._http_client.post(url, data=payload)
            return self._process_response(resp)
        except httpx.RequestError as e:
            logger.error(f"Network error sending message to Eitaa: {e}")
            raise EitaaNetworkError(f"خطا در ارسال پیام به ایتا: {e}") from e

    async def send_file(
        self,
        chat_id: str,
        file_bytes: bytes,
        filename: str,
        caption: Optional[str] = None,
        title: Optional[str] = None,
        disable_notification: Optional[int] = None,
        reply_to_message_id: Optional[int] = None,
        date: Optional[int] = None,
        pin: Optional[int] = None,
        view_count_for_delete: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Sends a file (image, video, document, voice) to Eitaa channel or chat.
        """
        url = self._get_url("sendFile")
        if chat_id.startswith("@"):
            chat_id = chat_id[1:]

        data: Dict[str, Any] = {
            "chat_id": chat_id,
        }
        if caption:
            data["caption"] = caption
        if title:
            data["title"] = title
        if disable_notification is not None:
            data["disable_notification"] = disable_notification
        if reply_to_message_id is not None:
            data["reply_to_message_id"] = reply_to_message_id
        if date is not None:
            data["date"] = date
        if pin is not None:
            data["pin"] = pin
        if view_count_for_delete is not None:
            data["viewCountForDelete"] = view_count_for_delete

        files = {
            "file": (filename, file_bytes)
        }

        try:
            resp = await self._http_client.post(url, data=data, files=files)
            return self._process_response(resp)
        except httpx.RequestError as e:
            logger.error(f"Network error uploading file to Eitaa: {e}")
            raise EitaaNetworkError(f"خطا در آپلود فایل در ایتا: {e}") from e

    async def close(self) -> None:
        if not self._external_client:
            await self._http_client.aclose()
