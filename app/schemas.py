from pydantic import BaseModel
from typing import Optional, Any


class User(BaseModel):
    """Telegram User object."""
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None


class Chat(BaseModel):
    """Telegram Chat object."""
    id: int
    type: str
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class Message(BaseModel):
    """Telegram Message object."""
    message_id: int
    from_user: Optional[User] = None
    sender_chat: Optional[Chat] = None
    date: int
    chat: Chat
    text: Optional[str] = None
    entities: Optional[list[Any]] = None
    # Add more fields as needed


class Update(BaseModel):
    """Telegram Update object — the root payload sent to the webhook."""
    update_id: int
    message: Optional[Message] = None
    edited_message: Optional[Message] = None
    channel_post: Optional[Message] = None
    edited_channel_post: Optional[Message] = None
    # Add more fields as needed (inline_query, callback_query, etc.)
