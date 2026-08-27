from pydantic import BaseModel


class Token(BaseModel):
    """Returned by /auth/login. The client sends `access_token` back on every
    protected request as an `Authorization: Bearer <token>` header."""
    access_token: str
    token_type: str = "bearer"
