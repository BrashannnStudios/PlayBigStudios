from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, Dict, Any, List
import os
import time

class Database:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None

    async def connect(self):
        uri = os.getenv("MONGO_URI")
        if not uri:
            raise ValueError("MONGO_URI environment variable is required")
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client["playbig_studios"]
        await self.db.guilds.create_index("guild_id", unique=True)
        await self.db.users.create_index([("guild_id", 1), ("user_id", 1)], unique=True)

    async def close(self):
        if self.client:
            self.client.close()

    # ─── Guild Config ───────────────────────────────────────────────
    async def get_guild(self, guild_id: int) -> Dict[str, Any]:
        doc = await self.db.guilds.find_one({"guild_id": guild_id})
        if not doc:
            doc = {
                "guild_id": guild_id,
                "welcome": {
                    "enabled": False,
                    "channel_id": None,
                    "message": "Welcome {user} to **{server}**!",
                    "color": 0x5865F2,
                    "image": None,
                    "recommended_channels": [],
                    "links": []
                },
                "vacants": {
                    "enabled": False,
                    "announce_channel_id": None,
                    "review_channel_id": None,
                    "categories": [],
                    "questions": []
                }
            }
            await self.db.guilds.insert_one(doc)
        return doc

    async def update_welcome(self, guild_id: int, data: Dict[str, Any]):
        await self.db.guilds.update_one(
            {"guild_id": guild_id},
            {"$set": {"welcome": data}},
            upsert=True
        )

    async def update_vacants(self, guild_id: int, data: Dict[str, Any]):
        await self.db.guilds.update_one(
            {"guild_id": guild_id},
            {"$set": {"vacants": data}},
            upsert=True
        )

    # ─── User Data ──────────────────────────────────────────────────
    async def get_user(self, guild_id: int, user_id: int) -> Dict[str, Any]:
        doc = await self.db.users.find_one({"guild_id": guild_id, "user_id": user_id})
        if not doc:
            doc = {
                "guild_id": guild_id,
                "user_id": user_id,
                "notes": [],
                "warns": [],
                "tempban_until": None,
                "tempban_reason": None
            }
            await self.db.users.insert_one(doc)
        return doc

    async def add_note(self, guild_id: int, user_id: int, note: str, moderator_id: int) -> int:
        user = await self.get_user(guild_id, user_id)
        note_id = len(user["notes"]) + 1
        entry = {
            "id": note_id,
            "content": note,
            "moderator_id": moderator_id,
            "timestamp": int(time.time())
        }
        await self.db.users.update_one(
            {"guild_id": guild_id, "user_id": user_id},
            {"$push": {"notes": entry}}
        )
        return note_id

    async def remove_note(self, guild_id: int, user_id: int, note_id: int) -> bool:
        result = await self.db.users.update_one(
            {"guild_id": guild_id, "user_id": user_id},
            {"$pull": {"notes": {"id": note_id}}}
        )
        return result.modified_count > 0

    async def add_warn(self, guild_id: int, user_id: int, reason: str, moderator_id: int) -> int:
        user = await self.get_user(guild_id, user_id)
        warn_id = len(user["warns"]) + 1
        entry = {
            "id": warn_id,
            "reason": reason,
            "moderator_id": moderator_id,
            "timestamp": int(time.time())
        }
        await self.db.users.update_one(
            {"guild_id": guild_id, "user_id": user_id},
            {"$push": {"warns": entry}}
        )
        return warn_id

    async def remove_warn(self, guild_id: int, user_id: int, warn_id: int) -> bool:
        result = await self.db.users.update_one(
            {"guild_id": guild_id, "user_id": user_id},
            {"$pull": {"warns": {"id": warn_id}}}
        )
        return result.modified_count > 0

    async def set_tempban(self, guild_id: int, user_id: int, until: int, reason: str):
        await self.db.users.update_one(
            {"guild_id": guild_id, "user_id": user_id},
            {"$set": {"tempban_until": until, "tempban_reason": reason}},
            upsert=True
        )

    async def clear_tempban(self, guild_id: int, user_id: int):
        await self.db.users.update_one(
            {"guild_id": guild_id, "user_id": user_id},
            {"$set": {"tempban_until": None, "tempban_reason": None}}
        )

    async def get_expired_tempbans(self) -> List[Dict[str, Any]]:
        now = int(time.time())
        cursor = self.db.users.find({"tempban_until": {"$lte": now, "$ne": None}})
        return await cursor.to_list(length=100)

db = Database()
