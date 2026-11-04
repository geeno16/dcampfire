from datetime import datetime

from pydantic import BaseModel

from src.bonfire.schema import BonfireCard
from src.user.schema import Nickname, UserBrief


class InviteRequest(BaseModel):
    nickname: Nickname


class InvitationRead(BaseModel):
    bonfire: BonfireCard
    owner: UserBrief
    created_at: datetime
