import json
import os
from typing import List, Tuple, Optional, Dict, Any
import datetime  # Added import for time handling
from pathlib import Path

DATA_DIR = Path(os.getenv("PERSISTENT_STORAGE_PATH", "persistent_data"))
DATA_DIR.mkdir(exist_ok=True)

class UserDatabase:
    def __init__(self, filename: str):
        self.filename = str(DATA_DIR / filename)  # <-- This line changed
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
    
    # ... (keep all other methods exactly the same as before)
    # Only ensure all datetime handling is present
    
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
    
    def get_top_users(self, limit: int = 10) -> List[Tuple[int, str, int]]:
        """Get top users by balance."""
        users = [
            (int(user_id), data["username"], data["balance"])
            for user_id, data in self.data["users"].items()
        ]
        return sorted(users, key=lambda x: x[2], reverse=True)[:limit]
    
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
