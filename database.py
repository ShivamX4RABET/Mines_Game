import json
import os
import datetime
from typing import List, Tuple, Optional, Dict, Any

class UserDatabase:
    def __init__(self, filename: str):
        self.filename = filename
        self.data = self._load_data()
    
    def _load_data(self) -> Dict[str, Any]:
        """Load user data from JSON file."""
        if not os.path.exists(self.filename):
            return {"users": {}}
        with open(self.filename, 'r') as f:
            return json.load(f)
    
    def _save_data(self) -> None:
        """Save user data to JSON file."""
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    # ADD THESE METHODS FOR INTEGER HIWA HANDLING:
    def add_balance(self, user_id: int, amount: int) -> None:
        """Add whole number Hiwa to balance (no decimals)"""
        amount = int(amount)  # Force integer conversion
        if str(user_id) not in self.data["users"]:
            self.add_user(user_id, f"User{user_id}", 0)
        self.data["users"][str(user_id)]["balance"] += amount
        self._save_data()
    
    def deduct_balance(self, user_id: int, amount: int) -> None:
        """Deduct whole number Hiwa from balance (no decimals)"""
        amount = int(amount)  # Force integer conversion
        self.data["users"][str(user_id)]["balance"] -= amount
        self._save_data()
    
    def set_balance(self, user_id: int, amount: int) -> bool:
    """Set user balance"""
    if not self.user_exists(user_id):
        return False
    self.data[str(user_id)]['balance'] = amount
    self._save()
    return True

    def user_exists(self, user_id: int) -> bool:
        """Check if a user exists in the database."""
        return str(user_id) in self.data["users"]
    
    def add_user(self, user_id: int, username: str, balance: int = 100) -> None:
        """Add a new user to the database."""
        self.data["users"][str(user_id)] = {
            "username": username,
            "balance": balance,
            "last_daily": None,
            "last_weekly": None
        }
        self._save_data()
    
    def get_balance(self, user_id: int) -> int:
        """Get a user's balance."""
        return self.data["users"][str(user_id)]["balance"]
    
    def has_sufficient_balance(self, user_id: int, amount: int) -> bool:
        """Check if user has sufficient balance."""
        return self.get_balance(user_id) >= amount
    
    def get_last_daily(self, user_id: int) -> Optional[datetime.datetime]:
        """Safely get last daily claim time."""
        user = self.data["users"].get(str(user_id))
        if not user or "last_daily" not in user:
            return None
        try:
            return datetime.datetime.fromisoformat(user["last_daily"])
        except ValueError:
            return None
    
    def set_last_daily(self, user_id: int, time: datetime.datetime) -> None:
        """Set last daily bonus claim time."""
        if str(user_id) not in self.data["users"]:
            self.add_user(user_id, f"User{user_id}", 100)
        self.data["users"][str(user_id)]["last_daily"] = time.isoformat()
        self._save_data()
    
    def get_last_weekly(self, user_id: int) -> Optional[datetime.datetime]:
        """Safely get last weekly claim time."""
        user = self.data["users"].get(str(user_id))
        if not user or "last_weekly" not in user:
            return None
        try:
            return datetime.datetime.fromisoformat(user["last_weekly"])
        except ValueError:
            return None
    
    def set_last_weekly(self, user_id: int, time: datetime.datetime) -> None:
        """Set last weekly bonus claim time."""
        if str(user_id) not in self.data["users"]:
            self.add_user(user_id, f"User{user_id}", 100)
        self.data["users"][str(user_id)]["last_weekly"] = time.isoformat()
        self._save_data()
    
    def get_top_users(self, limit: int = 10) -> List[Tuple[int, str, int]]:
        """Get top users by balance."""
        users = []
        for user_id, data in self.data["users"].items():
            username = data.get("username", f"User{user_id[:4]}")
            users.append((int(user_id), username, data["balance"]))
        return sorted(users, key=lambda x: x[2], reverse=True)[:limit]
    
    def get_user_id_by_username(self, username: str) -> Optional[int]:
    """Find user ID by username (case insensitive)"""
    username = username.lower().strip('@')
    for user_id, user_data in self.data.items():
        if 'username' in user_data and user_data['username'].lower() == username:
            return user_id
    return None
    
    def get_all_users(self) -> List[int]:
        """Get all user IDs."""
        return [int(user_id) for user_id in self.data["users"].keys()]
    
    def reset_all_data(self) -> None:
        """Reset all user data."""
        self.data = {"users": {}}
        self._save_data()
