import random
from telegram import InlineKeyboardButton
from dataclasses import dataclass
from typing import List

def generate_game_grid(grid_state, revealed):
    """
    Create an interactive 5x5 grid with numbered buttons
    Returns a list of button rows
    """
    buttons = []
    for i in range(5):
        row = []
        for j in range(5):
            if revealed[i][j]:
                emoji = "💎" if grid_state[i][j] == "gem" else "💣"
                row.append(InlineKeyboardButton(emoji, callback_data=f"revealed_{i}_{j}"))
            else:
                row.append(InlineKeyboardButton(f"{i+1}{j+1}", callback_data=f"tap_{i}_{j}"))
        buttons.append(row)
    
    # Add Cashout button at bottom
    buttons.append([InlineKeyboardButton("💰 Cash Out", callback_data="cashout_now")])
    return buttons

@dataclass
class Tile:
    value: str
    revealed: bool = False

class MinesGame:
    def __init__(self, bet_amount: int, mines_count: int):
        self.bet_amount = bet_amount
        self.mines_count = mines_count
        self.gems_revealed = 0
        self.current_multiplier = 1.0
        self.message_id = None
        self.board = self._generate_board()
    
    def _generate_board(self) -> List[List[Tile]]:
        """Generate a 5x5 board with gems and bombs."""
        # Create empty board
        board = [[Tile("🟦") for _ in range(5)] for _ in range(5)]
        
        # Place bombs
        bomb_positions = random.sample(range(25), self.mines_count)
        for pos in bomb_positions:
            i, j = divmod(pos, 5)
            board[i][j].value = "💣"
        
        # Place gems (3 gems)
        gem_positions = random.sample(
            [pos for pos in range(25) if pos not in bomb_positions],
            3
        )
        for pos in gem_positions:
            i, j = divmod(pos, 5)
            board[i][j].value = "💎"
        
        return board
    
    def reveal_tile(self, i: int, j: int) -> bool:
        """Reveal a tile. Returns True if it was a gem, False if bomb."""
        tile = self.board[i][j]
        tile.revealed = True
        
        if tile.value == "💣":
            return False
        elif tile.value == "💎":
            self.gems_revealed += 1
            self._update_multiplier()
            return True
        else:
            # Empty tile
            self._update_multiplier()
            return True
    
    def _update_multiplier(self) -> None:
        """Update the multiplier based on revealed gems and mines count."""
        base_increase = 0.25 + (self.mines_count / 24) * 0.5
        self.current_multiplier = 1.0 + (self.gems_revealed * base_increase)
