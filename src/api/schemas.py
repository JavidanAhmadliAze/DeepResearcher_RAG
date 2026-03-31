from pydantic import BaseModel


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    identifier: str
    password: str


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default-thread"
