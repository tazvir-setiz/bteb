import logging
from typing import Optional, Dict, Any, List, Union
import httpx

logger = logging.getLogger(__name__)

class BaleError(Exception):
    """Base exception for Bale API operations."""
    pass

class BaleAPIError(BaleError):
    """Raised when Bale returns an error response."""
    pass

class BaleClient:
    """
    Client for interacting with Bale Bot API (https://docs.bale.ai).
    Implements Telegram-compatible bot methods.
    """
    API_URL = "https://tapi.bale.ai/bot"
    FILE_URL = "https://tapi.bale.ai/file/bot"

    def __init__(self, token: str, http_client: Optional[httpx.AsyncClient] = None, timeout: float = 30.0):
        self.token = token.strip()
        self._external_client = http_client is not None
        self._http_client = http_client or httpx.AsyncClient(timeout=timeout)

    def _api_endpoint(self, method: str) -> str:
        return f"{self.API_URL}{self.token}/{method}"

    def _file_endpoint(self, file_path: str) -> str:
        return f"{self.FILE_URL}{self.token}/{file_path.lstrip('/')}"

    def _process_response(self, response: httpx.Response) -> Dict[str, Any]:
        try:
            data = response.json()
        except Exception as e:
            raise BaleAPIError(f"پاسخ غیرمعتبر از سرور بله (کد {response.status_code}): {response.text}") from e

        if not isinstance(data, dict):
            raise BaleAPIError(f"پاسخ بله در قالب دیکشنری نیست: {data}")

        if not data.get("ok"):
            desc = data.get("description", "خطای ناشناخته از سرور بله")
            raise BaleAPIError(f"خطای بله: {desc}")

        return data

    async def get_me(self) -> Dict[str, Any]:
        """Verify bot token and get bot profile info."""
        url = self._api_endpoint("getMe")
        resp = await self._http_client.get(url)
        return self._process_response(resp)

    async def get_updates(
        self,
        offset: Optional[int] = None,
        limit: int = 100,
        timeout: int = 20
    ) -> List[Dict[str, Any]]:
        """Fetch incoming updates via long polling."""
        url = self._api_endpoint("getUpdates")
        payload: Dict[str, Any] = {"limit": limit, "timeout": timeout}
        if offset is not None:
            payload["offset"] = offset

        resp = await self._http_client.post(url, json=payload, timeout=timeout + 10.0)
        data = self._process_response(resp)
        return data.get("result", [])

    async def send_message(
        self,
        chat_id: Union[int, str],
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send text message to a chat, channel, or user."""
        url = self._api_endpoint("sendMessage")
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if parse_mode is not None:
            payload["parse_mode"] = parse_mode

        resp = await self._http_client.post(url, json=payload)
        return self._process_response(resp)

    async def edit_message_text(
        self,
        chat_id: Union[int, str],
        message_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """Edit text of a sent message."""
        url = self._api_endpoint("editMessageText")
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if parse_mode is not None:
            payload["parse_mode"] = parse_mode

        resp = await self._http_client.post(url, json=payload)
        return self._process_response(resp)

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False
    ) -> Dict[str, Any]:
        """Acknowledge inline keyboard button clicks."""
        url = self._api_endpoint("answerCallbackQuery")
        payload: Dict[str, Any] = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert
        }
        if text:
            payload["text"] = text

        resp = await self._http_client.post(url, json=payload)
        return self._process_response(resp)

    async def get_file(self, file_id: str) -> Dict[str, Any]:
        """Retrieve file information and path for downloading."""
        url = self._api_endpoint("getFile")
        resp = await self._http_client.post(url, json={"file_id": file_id})
        return self._process_response(resp)

    async def download_file(self, file_path: str) -> bytes:
        """Download raw binary content of a file."""
        url = self._file_endpoint(file_path)
        resp = await self._http_client.get(url)
        if resp.status_code != 200:
            raise BaleAPIError(f"دانلود فایل از بله با خطا مواجه شد: کد {resp.status_code}")
        return resp.content

    async def close(self) -> None:
        if not self._external_client:
            await self._http_client.aclose()
