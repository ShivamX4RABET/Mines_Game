import json
import os
from typing import List, Tuple, Optional, Dict, Any
import datetime  # Added import for time handling
from pathlib import Path

DATA_DIR = Path(os.getenv("PERSISTENT_STORAGE_PATH", "persistent_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

class UserDatabase:
    def __init__(self, filename: str):
        self.filename = str(DATA_DIR / filename)
        self.data = self._load_data()
        self.emoji_store = [
            {'emoji': '⭐', 'price': 100000, 'description': 'Shiny Star'},
            {'emoji': '🎁', 'price': 500000, 'description': 'Gift Box'},
            {'emoji': '❤️', 'price': 1000000, 'description': 'Heart of Love'},
            {'emoji': '🚀', 'price': 15000000, 'description': 'Rocket Booster'},
            {'emoji': '👻', 'price': 50000000, 'description': 'Ghost'},
            {'emoji': '💀', 'price': 100000000, 'description': 'Skull'},
            {'emoji': '☠️', 'price': 150000000, 'description': 'Skull and Crossbones'},
            {'emoji': '👑', 'price': 50000000000000000000, 'description': 'Royal Crown'}
        ]
    
    def get_emoji_store(self) -> list:
        # Returns list like [{"emoji": "⭐", "price": 500}, ...]
        return self.emoji_store

    def get_user_emojis(self, user_id: int) -> list:
        # Returns list like ["🌟", "🌸"]
        return self.data["users"][str(user_id)].get("emojis", [])

    def add_emoji(self, user_id: int, emoji: str):
        users = self.data["users"]
        user = users.setdefault(str(user_id), {})
        user.setdefault("emojis", [])
        if emoji not in user["emojis"]:
            user["emojis"].append(emoji)
            self._save_data()

    def remove_emoji(self, user_id, emoji):
        users = self.data["users"]
        user = users.get(str(user_id), {})
        if emoji in user.get('emojis', []):
            user['emojis'].remove(emoji)
            self._save_data()  # Fixed method name

    def get_selected_emoji(self, user_id):
        users = self.data["users"]
        user = users.get(str(user_id), {})
        return user.get('selected_emoji', '💎')

    def set_selected_emoji(self, user_id, emoji):
        users = self.data["users"]
        user = users.setdefault(str(user_id), {})
        user['selected_emoji'] = emoji
        self._save_data()  # Fixed method name

    def sync_user_info(user: User):
        user_id = str(user.id)
        if not db.user_exists(user.id):
            return

        stored = db.data["users"][user_id]
        updated = False

        current_username = user.username or ""
        current_first_name = user.first_name

        if stored.get("username", "") != current_username:
            stored["username"] = current_username
            updated = True

        if stored.get("first_name", "") != current_first_name:
            stored["first_name"] = current_first_name
            updated = True

        if updated:
            db._save_data()

    def _load_data(self) -> Dict[str, Any]:
        """Load user data from JSON file."""
        # If the file doesn’t exist yet, initialize both users and groups
        if not os.path.exists(self.filename):
            return {"users": {}, "groups": []}

        # Otherwise open and parse it
        with open(self.filename, 'r') as f:
            data = json.load(f)

        # Ensure legacy files get a groups key
        if "groups" not in data:
            data["groups"] = []

        return data
    
    def add_group(self, group_id: int) -> None:
        """Add a group to the database if not already present"""
        if group_id not in self.data["groups"]:
            self.data["groups"].append(group_id)
            self._save_data()

    def remove_group(self, group_id: int) -> None:
        """Remove a group from the database"""
        if group_id in self.data["groups"]:
            self.data["groups"].remove(group_id)
            self._save_data()

    def get_all_groups(self) -> List[int]:
        """Get all group IDs where the bot is present"""
        return self.data["groups"]
    
    def _save_data(self) -> None:
        """Save user data to JSON file."""
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    # ... (keep all other methods exactly the same as before)
    # Only ensure all datetime handling is present
    
    def user_exists(self, user_id: int) -> bool:
        """Check if a user exists in the database."""
        return str(user_id) in self.data["users"]
    
    def add_user(self, user_id: int, username: Optional[str], first_name: str, balance: int = 100) -> None:
        """Add a new user, storing both Telegram username (if any) and first name."""
        self.data["users"][str(user_id)] = {
            "username": username or "",
            "first_name": first_name,
            "balance": balance,
            "last_daily": None,
            "last_weekly": None
        }
        self._save_data()
    
    def get_balance(self, user_id: int) -> int:
        """Get a user's balance."""
        return self.data["users"][str(user_id)]["balance"]
    
    def set_balance(self, user_id: int, amount: float) -> None:
        """Set balance to whole numbers only"""
        self.data["users"][str(user_id)]["balance"] = int(round(amount))
        self._save_data()
    
    def has_sufficient_balance(self, user_id: int, amount: int) -> bool:
        """Check if user has sufficient balance."""
        return self.get_balance(user_id) >= amount
    
    def add_balance(self, user_id: int, amount: float) -> None:
        """Add whole number Hiwa only"""
        amount = int(round(amount))  # Convert to nearest integer
        self.data["users"][str(user_id)]["balance"] += amount
        self._save_data()

    def deduct_balance(self, user_id: int, amount: float) -> None:
        """Deduct whole number Hiwa only"""
        amount = int(round(amount))  # Convert to nearest integer
        self.data["users"][str(user_id)]["balance"] -= amount
        self._save_data()
    
    def get_last_daily(self, user_id: int):
        """Get last daily bonus claim time."""
        last = self.data["users"][str(user_id)]["last_daily"]
        return datetime.datetime.fromisoformat(last) if last else None
    
    def set_last_daily(self, user_id: int, time) -> None:
        """Set last daily bonus claim time."""
        self.data["users"][str(user_id)]["last_daily"] = time.isoformat()
        self._save_data()
    
    def get_last_weekly(self, user_id: int):
        """Get last weekly bonus claim time."""
        last = self.data["users"][str(user_id)]["last_weekly"]
        return datetime.datetime.fromisoformat(last) if last else None
    
    def set_last_weekly(self, user_id: int, time) -> None:
        """Set last weekly bonus claim time."""
        self.data["users"][str(user_id)]["last_weekly"] = time.isoformat()
        self._save_data()
    
    def get_top_users(self, limit: int = 10) -> List[Tuple[int, str, str, int]]:
        users = []
        for uid, data in self.data["users"].items():
            try:
                balance = int(data.get("balance", 0))
                users.append((
                    int(uid),
                    data.get("username", ""),
                    data.get("first_name", "Unknown"),
                    balance
                ))
            except Exception as e:
                logger.warning(f"Skipping user {uid} due to data error: {e}")
        return sorted(users, key=lambda x: x[3], reverse=True)[:limit]
    
    def get_user_id_by_username(self, username: str) -> Optional[int]:
        """Get user ID by username."""
        username = username.lower()
        for user_id, data in self.data["users"].items():
            if data["username"].lower() == username:
                return int(user_id)
        return None
    
    def get_all_users(self) -> List[int]:
        """Get all user IDs."""
        return [int(user_id) for user_id in self.data["users"].keys()]
    
    def reset_all_data(self) -> None:
        """Reset all user data."""
        self.data = {"users": {}}
        self._save_data()
