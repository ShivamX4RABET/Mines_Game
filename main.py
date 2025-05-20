import logging
from telegram.constants import ParseMode
import html
from telegram import MessageEntity, User
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
import random
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from game_logic import MinesGame
from game_logic import TicTacToeGame
from database import UserDatabase
db = UserDatabase("users.json")
import config
import datetime
from typing import Dict
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

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Changed from: user_games: Dict[int, MinesGame] = {}
# New structure: {chat_id: {user_id: MinesGame}}
user_games: Dict[int, Dict[int, MinesGame]] = {}
# track pending invitations: {chat_id: {challenger_id: {'amount':int, 'message_id':int}}}
pending_ttt: Dict[int, Dict[int, Dict]] = {}

# track active games: {chat_id: {user1_id: TicTacToeGame}}
active_ttt: Dict[int, Dict[int, TicTacToeGame]] = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    if not db.user_exists(user.id):
        db.add_user(
            user.id,
            user.username,     # may be None if they have no @username
            user.first_name,   # always present
            100
                )
        await update.message.reply_text(
            f"Welcome to Mines Game, {user.first_name}!\n"
            "You've been given 100 Hiwa to start playing.\n"
            "Use /help to learn how to play."
        )
    else:
        await update.message.reply_text(
            f"Welcome back, {user.first_name}!\n"
            f"Your current balance: {db.get_balance(user.id)} Hiwa\n"
            "Use /help to see available commands."
        )

async def auto_sync_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        sync_user_info(update.effective_user)
        
async def track_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Track when the bot is added to groups"""
    if update.message and update.message.new_chat_members:
        if context.bot.id in [u.id for u in update.message.new_chat_members]:
            group_id = update.message.chat_id
            db.add_group(group_id)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = """
🎮 *Mines Game Bot Help* 🎮

*Basic Commands:*
/start - Initialize your account
/help - Show this help message
/balance - Check your Hiwa balance
/mine <amount> <mines> - Start a new game (e.g., /mine 10 5)
/cashout - Cash out your current winnings
/daily - Claim daily bonus (24h cooldown)
/weekly - Claim weekly bonus (7d cooldown)
/leaderboard - Show top players
/gift @username <amount> - Send Hiwa to another player

*New Features:*
/store - View and buy emojis
/collection - View your owned emojis
/give [emoji] - Gift an emoji (reply to user)

*Game Rules:*
1. 5x5 grid with hidden gems (💎) and bombs (💣)
2. Choose how many bombs (3-24) when starting
3. Reveal tiles to find gems
4. Cash out after finding at least 2 gems
5. Hit a bomb and you lose your bet

*Admin Commands:*
/broadcast <message> - Send message to all users
/resetdata - Reset all user data (admin only)
/setbalance @user <amount> - Set user balance (admin only)
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user balance."""
    user_id = update.effective_user.id
    balance = db.get_balance(user_id)
    await update.message.reply_text(f"Your current balance: {balance} Hiwa")

async def send_game_board(update: Update, game: MinesGame, user_id: int, exploded_row: int = -1, exploded_col: int = -1):
    """Send updated game board with proper user ID in callbacks"""
    keyboard = []
    for i in range(5):
        row = []
        for j in range(5):
            tile = game.board[i][j]
            text = "🟦"
            if game.game_over or tile.revealed:
                # Use custom emoji for revealed tiles
                text = tile.value
                if i == exploded_row and j == exploded_col and tile.value == "💣":
                    text = "💥"
            
            # Add user ID to callback data
            row.append(InlineKeyboardButton(
                text, 
                callback_data=f"reveal_{i}_{j}_{user_id}"
            ))
        keyboard.append(row)
    
    if game.gems_revealed >= 2 and not game.game_over:
        keyboard.append([
            InlineKeyboardButton(
                f"💰 Cash Out ({game.current_multiplier:.2f}x)", 
                callback_data=f"cashout_{user_id}"
            )
        ])
    
    text = (
        f"{game.user_emoji} Mines Game 💣\n\n"  # Show custom emoji here
        f"Bet: {game.bet_amount} Hiwa\n"
        f"Mines: {game.mines_count}\n"
        f"Gems Found: {game.gems_revealed}/{25 - game.mines_count}\n"
        f"Multiplier: {game.current_multiplier:.2f}x"
    )
    
    try:
        await update.callback_query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Board update error: {e}")

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /mine command and initialize game"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    user_id = user.id

    # Check existing game in this chat
    if chat_id in user_games and user_id in user_games[chat_id]:
        await update.message.reply_text(
            "❌ You have an ongoing game in this chat! Finish it first."
        )
        return

    try:
        if len(context.args) != 2:
            await update.message.reply_text("Usage: /mine <amount> <mines>\nExample: /mine 100 5")
            return

        amount = int(context.args[0])
        mines = int(context.args[1])

        if amount < 1 or mines < 3 or mines > 24:
            await update.message.reply_text("Invalid input!\nAmount ≥1 | Mines 3–24")
            return

        if not db.has_sufficient_balance(user_id, amount):
            await update.message.reply_text("Insufficient balance!")
            return

        # Get user's selected emoji from database
        selected_emoji = db.get_selected_emoji(user_id)

        # Deduct balance and initialize game
        db.deduct_balance(user_id, amount)
        game = MinesGame(amount, mines, selected_emoji)

        # Store game under chat_id and user_id
        if chat_id not in user_games:
            user_games[chat_id] = {}
        user_games[chat_id][user_id] = game

        await send_initial_board(update, context, chat_id, user_id, game)

    except Exception as e:
        logger.error(f"/mine error: {e}")
        await update.message.reply_text("Error starting game. Start the Bot first. Try again.")

async def send_initial_board(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    chat_id: int, 
    user_id: int, 
    game: MinesGame
) -> None:
    """Send the first game board with tiles to GROUP CHAT"""
    keyboard = [
        [
            InlineKeyboardButton(
                "🟦", 
                callback_data=f"reveal_{i}_{j}_{user_id}"  # Added user_id
            ) for j in range(5)
        ] for i in range(5)
    ]
    
    keyboard.append([
        InlineKeyboardButton(
            "💰 Initialize Cashout", 
            callback_data=f"cashout_{user_id}"  # Added user_id
        )
    ])
    
    text = (
        f"💎 {update.effective_user.first_name}'s Mines Game Started! 💣\n"
        f"Bet: {game.bet_amount} Hiwa\n"
        f"Mines: {game.mines_count}\n"
        f"Tap tiles to begin!"
    )
    
    message = await context.bot.send_message(
        chat_id=chat_id,  # Send to group chat
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    game.message_id = message.message_id

async def update_board(update: Update, game: MinesGame, user_id: int):
    """Refresh game board with revealed tiles"""
    keyboard = []
    for i in range(5):
        row = []
        for j in range(5):
            tile = game.board[i][j]
            text = tile.value if tile.revealed else "🟦"
            row.append(InlineKeyboardButton(
                text,
                callback_data=f"reveal_{i}_{j}_{user_id}"
            ))
        keyboard.append(row)
    
    if game.gems_revealed >= 2 and not game.game_over:
        keyboard.append([
            InlineKeyboardButton(
                f"💰 Cash Out ({game.current_multiplier:.2f}x)", 
                callback_data=f"cashout_{user_id}"
            )
        ])
    
    text = (
        f"💎 Mines Game 💣\n"
        f"Bet: {game.bet_amount} Hiwa\n"
        f"Mines: {game.mines_count}\n"
        f"Gems Found: {game.gems_revealed}\n"
        f"Multiplier: {game.current_multiplier:.2f}x"
    )
    
    try:
        await update.callback_query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Board update error: {e}")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    chat_id = query.message.chat.id  # group chat ID
    user_clicking_id = query.from_user.id  # the user who clicked

    # CASH OUT flow
    if data[0] == 'cashout':
        user_id = int(data[1])

        # Restrict access to board owner
        if user_clicking_id != user_id:
            await query.answer("You can't cash out another player's game!", show_alert=True)
            return

        game = user_games.get(chat_id, {}).get(user_id)
        if not game:
            await query.edit_message_text("❌ Game session expired!")
            return

        # Calculate and award winnings
        win_amount = int(game.bet_amount * game.current_multiplier)
        db.add_balance(user_id, win_amount)

        # Finish the game
        await handle_game_over(
            update=update,
            chat_id=chat_id,
            user_id=user_id,
            game=game,
            won=True,
            context=context
        )
        return

    # REVEAL TILE flow
    if data[0] == 'reveal':
        row = int(data[1])
        col = int(data[2])
        user_id = int(data[3])

        # Restrict access to board owner
        if user_clicking_id != user_id:
            await query.answer("You can't play someone else's board!", show_alert=True)
            return

        game = user_games.get(chat_id, {}).get(user_id)
        if not game:
            await query.edit_message_text("❌ Game session expired!")
            return

        success, result = game.reveal_tile(row, col)

        if success:
            # Rebuild entire keyboard from game state
            keyboard = []
            for i in range(5):
                kb_row = []
                for j in range(5):
                    tile = game.board[i][j]
                    text = tile.value if tile.revealed else "🟦"
                    kb_row.append(
                        InlineKeyboardButton(
                            text,
                            callback_data=f"reveal_{i}_{j}_{user_id}"
                        )
                    )
                keyboard.append(kb_row)

            # Add cash-out button if at least 2 gems revealed
            if game.gems_revealed >= 2 and not game.game_over:
                keyboard.append([
                    InlineKeyboardButton(
                        f"💰 Cash Out ({game.current_multiplier:.2f}x)",
                        callback_data=f"cashout_{user_id}"
                    )
                ])

            # Update message
            new_text = (
                f"💎 Mines Game 💣\n"
                f"Bet: {game.bet_amount} Hiwa\n"
                f"Mines: {game.mines_count}\n"
                f"Gems Found: {game.gems_revealed}\n"
                f"Multiplier: {game.current_multiplier:.2f}x"
            )

            await query.edit_message_text(
                text=new_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        # Bomb was revealed — game over
        if result == 'bomb':
            await handle_game_over(
                update=update,
                chat_id=chat_id,
                user_id=user_id,
                game=game,
                won=False,
                exploded_row=row,
                exploded_col=col,
                context=context
            )
            return

async def handle_game_over(
    update: Update,
    chat_id: int,
    user_id: int,
    game: MinesGame,
    won: bool,
    exploded_row: int = -1,
    exploded_col: int = -1,
    context: ContextTypes.DEFAULT_TYPE = None
) -> None:
    """Handle game conclusion with group chat support"""
    # 1. Mark exploded bomb if applicable
    if not won and 0 <= exploded_row < 5 and 0 <= exploded_col < 5:
        game.board[exploded_row][exploded_col].value = "💥"

    # 2. Reveal all tiles with player's emoji
    for row in game.board:
        for tile in row:
            tile.revealed = True
            if tile.value not in ["💣", "💥"]:
                tile.value = game.player_emoji

    # 3. Build final keyboard
    keyboard = []
    for i in range(5):
        row = []
        for j in range(5):
            tile = game.board[i][j]
            row.append(InlineKeyboardButton(tile.value, callback_data="ignore"))
        keyboard.append(row)
    
    # 4. Add play again button only if won
    if won:
        keyboard.append([InlineKeyboardButton("🎮 Play Again", callback_data=f"newgame_{user_id}")])

    # 5. Prepare result message
    balance = db.get_balance(user_id)
    if won:
        win_amount = int(game.bet_amount * game.current_multiplier)
        message = (
            f"🎉 {update.effective_user.first_name} Cashed Out!\n"
            f"Won: {win_amount} Hiwa\n"
            f"New Balance: {balance} Hiwa"
        )
    else:
        message = (
            f"💥 {update.effective_user.first_name} Hit a Mine!\n"
            f"Lost: {game.bet_amount} Hiwa\n"
            f"New Balance: {balance} Hiwa"
        )

    # 6. Edit original message
    try:
        await update.callback_query.edit_message_text(
            text=message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Game over error: {e}")

    # 7. Cleanup game state
    try:
        del user_games[chat_id][user_id]
        if not user_games[chat_id]:
            del user_games[chat_id]
    except KeyError:
        pass

async def bet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if len(context.args) != 1 or not context.args[0].isdigit():
        return await update.message.reply_text("Usage: /bet <amount>")
    amount = int(context.args[0])
    if amount < 100 or not db.has_sufficient_balance(user.id, amount):
        return await update.message.reply_text("Insufficient balance or minimum is 100 Hiwa.")

    db.deduct_balance(user.id, amount)

    keyboard = [
        [InlineKeyboardButton("Play with Bot", callback_data=f"ttt_bot_{amount}")],
        [InlineKeyboardButton("Invite a Player", callback_data=f"ttt_invite_{amount}")]
    ]
    await update.message.reply_text(
        f"Challenge issued for {amount} Hiwa! Who do you want to play against?",
        reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def tictactoe_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('_')
    challenger = query.from_user
    chat_id = query.message.chat.id

    if data[1] == 'bot':
        amount = int(data[2])
        # Create bot User object
        bot_user = User(id=config.BOT_ID, first_name="Bot", is_bot=True)
        game = TicTacToeGame(
            player1=challenger,
            player2=bot_user,
            bet=amount,
            is_bot=True
        )
        active_ttt.setdefault(chat_id, {})[challenger.id] = game
        
        # Deduct balance and calculate fee
        db.deduct_balance(challenger.id, amount)
        fee = (2 * amount) * 10 // 100
        pool = 2 * amount - fee
        db.add_balance(config.OWNER_ID, fee)
        
        # Bot makes first move if needed
        if game.current_player.id == config.BOT_ID:
            i, j = game.bot_move()
            game.make_move(i, j, config.BOT_ID)
        
        # Send board
        await query.edit_message_text(
            f"❌: {challenger.full_name}\n⭕: Bot\nPool: {pool} Hiwa\nCurrent: {game.current_player.full_name}",
            reply_markup=game.build_board_markup()
        )

    elif data[1] == 'invite':
        amount = int(data[2])
        # Store invitation under challenger's ID
        pending_ttt.setdefault(chat_id, {})[challenger.id] = {
            'amount': amount,
            'message_id': query.message.message_id,
            'inviter': challenger,
            'expiry_time': datetime.datetime.now() + datetime.timedelta(minutes=2)
        }
        # Create accept button
        keyboard = [[InlineKeyboardButton(
            "Accept Challenge", 
            callback_data=f"ttt_accept_{challenger.id}_{amount}"
        )]]
        await query.edit_message_text(
            f"{challenger.full_name} bets {amount} Hiwa! Who dares accept?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data[1] == 'accept':
        inviter_id = int(data[2])
        amount = int(data[3])
        invitation = pending_ttt.get(chat_id, {}).get(inviter_id)
        
        if not invitation:
            await query.answer("Challenge expired.", show_alert=True)
            return
        
        opponent = query.from_user
        inviter = invitation['inviter']
        
        # Validate
        if opponent.id == inviter.id:
            await query.answer("Can't accept your own challenge.", show_alert=True)
            return
        if not db.has_sufficient_balance(opponent.id, amount):
            await query.answer("Insufficient balance.", show_alert=True)
            return
        
        # Deduct balances
        db.deduct_balance(opponent.id, amount)
        fee = (2 * amount) * 10 // 100
        pool = 2 * amount - fee
        db.add_balance(config.OWNER_ID, fee)
        
        # Create game
        game = TicTacToeGame(
            player1=inviter,
            player2=opponent,
            bet=amount
        )
        active_ttt.setdefault(chat_id, {})[inviter.id] = game
        
        # Remove invitation
        del pending_ttt[chat_id][inviter_id]
        
        # Send board
        await query.edit_message_text(
            f"❌: {inviter.full_name}\n⭕: {opponent.full_name}\nPool: {pool} Hiwa",
            reply_markup=game.build_board_markup()
    )

async def handle_game_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('_')
    i, j, player1_id = int(data[2]), int(data[3]), int(data[4])
    chat_id = query.message.chat_id
    user = query.from_user

    game = active_ttt.get(chat_id, {}).get(player1_id)
    if not game or game.winner:
        return await query.answer("Game over.", show_alert=True)
    
    if user.id != game.current_player.id:
        return await query.answer("Not your turn!", show_alert=True)
    
    # Human move
    if not game.make_move(i, j, user.id):
        return await query.answer("Invalid move", show_alert=True)
    
    # Check win
    if game.winner:
        if game.winner == 'draw':
            db.add_balance(game.player1.id, game.bet)
            db.add_balance(game.player2.id, game.bet)
            text = "Draw! Refunded bets."
        else:
            winner = game.player1 if game.winner == game.player1.id else game.player2
            winnings = (2 * game.bet) - ((2 * game.bet) * 10 // 100)
            db.add_balance(winner.id, winnings)
            text = f"{winner.full_name} wins {winnings} Hiwa!"
        await query.edit_message_text(text, reply_markup=None)
        del active_ttt[chat_id][player1_id]
        return
    
    # Bot move if applicable
    if game.is_bot and game.current_player.id == config.BOT_ID:
        i, j = game.bot_move()
        game.make_move(i, j, config.BOT_ID)
        if game.winner:
            await query.edit_message_text("Bot wins!", reply_markup=None)
            del active_ttt[chat_id][player1_id]
            return
    
    # Update board
    await query.edit_message_text(
        f"❌: {game.player1.full_name}\n⭕: {game.player2.full_name}\nCurrent: {game.current_player.full_name}",
        reply_markup=game.build_board_markup()
    )

async def cleanup_invitations(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.now()
    for chat_id in list(pending_ttt):
        for inviter_id in list(pending_ttt[chat_id]):
            inv = pending_ttt[chat_id][inviter_id]
            if now > inv['expiry_time']:
                del pending_ttt[chat_id][inviter_id]

# Modify the store command (remove keyboard)
async def store(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the emoji store."""
    store_items = db.get_emoji_store()
    if not store_items:
        await update.message.reply_text("🏪 The store is currently empty. Check back later!")
        return
        
    text = "🏪 *Emoji Store* 💎\n\n"
    for idx, item in enumerate(store_items, 1):
        text += (
            f"{idx}. {item['emoji']} — *{item['description']}*\n"
            f"Price: {item['price']} Hiwa\n"
            f"Use /buy {item['emoji']} to purchase\n\n"
        )
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def buy_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /buy command"""
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /buy <emoji>\nExample: /buy 👑")
        return
        
    emoji = ' '.join(context.args)
    store_items = db.get_emoji_store()
    item = next((i for i in store_items if i['emoji'] == emoji), None)
    
    if not item:
        await update.message.reply_text("❌ This emoji is not available in the store!")
        return
        
    if emoji in db.get_user_emojis(user.id):
        await update.message.reply_text("❌ You already own this emoji!")
        return
        
    if not db.has_sufficient_balance(user.id, item['price']):
        await update.message.reply_text(f"❌ You need {item['price']} Hiwa to buy this!")
        return
        
    db.deduct_balance(user.id, item['price'])
    db.add_emoji(user.id, emoji)
    await update.message.reply_text(
        f"✅ Successfully purchased {emoji}!\n"
        f"New balance: {db.get_balance(user.id)} Hiwa\n"
        "Use /collection to view your emojis"
    )

async def set_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /set command"""
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /set <emoji>\nExample: /set 👑")
        return
        
    emoji = ' '.join(context.args)
    owned_emojis = db.get_user_emojis(user.id)
    
    if emoji not in owned_emojis:
        await update.message.reply_text("❌ You don't own this emoji! Check /collection")
        return
        
    db.set_selected_emoji(user.id, emoji)
    await update.message.reply_text(f"✅ Game emoji set to {emoji}!")

# Collection command
async def collection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's emoji collection"""
    user_id = update.effective_user.id
    emojis = db.get_user_emojis(user_id)
    selected = db.get_selected_emoji(user_id)
    
    text = (
        f"📚 Your Collection\n"
        f"Current Emoji: {selected}\n\n"
        f"Owned Emojis:\n{' '.join(emojis) if emojis else 'No emojis yet!'}\n\n"
        "Use /set <emoji> to change your active emoji\n"
        "Use /give <emoji> (reply to user) to gift an emoji"
    )
    await update.message.reply_text(text)

# ---- emoji gifting (/give) ----
async def emoji_gift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to a message to gift an emoji you own."""
    user = update.effective_user
    reply = update.message.reply_to_message

    if not reply or not reply.from_user:
        return await update.message.reply_text("❌ Reply to someone’s message to gift an emoji!")

    target = reply.from_user
    if target.id == user.id:
        return await update.message.reply_text("❌ You can’t gift yourself!")

    try:
        emoji = context.args[0]
    except IndexError:
        return await update.message.reply_text("Usage: /give [emoji] (in reply to a user)")

    if emoji not in db.get_user_emojis(user.id):
        return await update.message.reply_text("❌ You don’t own that emoji!")

    db.remove_emoji(user.id, emoji)
    db.add_emoji(target.id, emoji)

    await update.message.reply_text(f"✅ You gifted {emoji} to {target.first_name}!")
    await context.bot.send_message(
        chat_id=target.id,
        text=f"🎁 You received {emoji} from {user.first_name}!"
    )

async def cashout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cashout command with group-chat support."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Check nested dict: chat → user
    if chat_id not in user_games or user_id not in user_games[chat_id]:
        await update.message.reply_text("❌ You don't have an active game to cash out.")
        return

    game = user_games[chat_id][user_id]
    if game.gems_revealed < 2:
        await update.message.reply_text("❌ You need at least 2 gems to cash out.")
        return

    # Perform cashout
    game.game_over = True
    win_amount = int(game.bet_amount * game.current_multiplier)
    db.add_balance(user_id, win_amount)
    # Reuse your existing handle_game_over
    await handle_game_over(update, chat_id, user_id, game, won=True, context=context)

async def end_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /end — cancel an ongoing game and refund the bet."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # No active game?
    if chat_id not in user_games or user_id not in user_games[chat_id]:
        await update.message.reply_text("❌ You don’t have an active game to end.")
        return

    game = user_games[chat_id][user_id]

    # If the game already finished, disallow
    if game.game_over:
        await update.message.reply_text("❌ This game has already ended.")
        return

    # Refund original bet
    db.add_balance(user_id, game.bet_amount)
    new_balance = db.get_balance(user_id)

    # Clean up state exactly as in handle_game_over
    del user_games[chat_id][user_id]
    if not user_games[chat_id]:
        del user_games[chat_id]

    # Let the user know
    await update.message.reply_text(
        f"🛑 Game cancelled. Your bet of {game.bet_amount} Hiwa has been refunded.\n"
        f"Current balance: {new_balance} Hiwa"
    )

async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /daily command."""
    user_id = update.effective_user.id
    last_daily = db.get_last_daily(user_id)
    
    if last_daily and (datetime.datetime.now() - last_daily).total_seconds() < 24 * 3600:
        next_claim = last_daily + datetime.timedelta(hours=24)
        await update.message.reply_text(
            f"You've already claimed your daily bonus today.\n"
            f"Next claim available at {next_claim.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return
    
    amount = 50  # Daily bonus amount
    db.add_balance(user_id, amount)
    db.set_last_daily(user_id, datetime.datetime.now())
    await update.message.reply_text(
        f"🎁 You claimed your daily bonus of {amount} Hiwa!\n"
        f"New balance: {db.get_balance(user_id)} Hiwa"
    )

async def weekly_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /weekly command."""
    user_id = update.effective_user.id
    last_weekly = db.get_last_weekly(user_id)
    
    if last_weekly and (datetime.datetime.now() - last_weekly).total_seconds() < 7 * 24 * 3600:
        next_claim = last_weekly + datetime.timedelta(days=7)
        await update.message.reply_text(
            f"You've already claimed your weekly bonus this week.\n"
            f"Next claim available at {next_claim.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return
    
    amount = 200  # Weekly bonus amount
    db.add_balance(user_id, amount)
    db.set_last_weekly(user_id, datetime.datetime.now())
    await update.message.reply_text(
        f"🎁 You claimed your weekly bonus of {amount} Hiwa!\n"
        f"New balance: {db.get_balance(user_id)} Hiwa"
    )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        top = db.get_top_users(10)
        if not top:
            await update.message.reply_text("🏆 Leaderboard is empty!")
            return

        lines = ["🏆 <b>TOP PLAYERS</b> 🏆\n"]
        medals = ["🥇", "🥈", "🥉"]

        for i, (uid, username, first_name, balance) in enumerate(top, start=1):
            prefix = medals[i - 1] if i <= 3 else f"{i}."
            safe_name = html.escape(first_name or "Unknown")  # Extra safety
            mention = f'<a href="tg://user?id={uid}">{safe_name}</a>'
            lines.append(f"{prefix} {mention} — <b>{balance:,}</b> Hiwa")

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        await update.message.reply_text("❌ Failed to load leaderboard. Please try again!")

async def gift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /gift command."""
    if len(context.args) < 2:
        await update.message.reply_text("sage: /gift @username <amount>")
        return
    
    try:
        recipient_username = context.args[0].lstrip('@')
        amount = int(context.args[1])
    except (ValueError, IndexError):
        await update.message.reply_text("Usage: /gift @username <amount>")
        return
    
    if amount < 1:
        await update.message.reply_text("Amount must be at least 1 Hiwa.")
        return
    
    sender_id = update.effective_user.id
    recipient_id = db.get_user_id_by_username(recipient_username)
    
    if not recipient_id:
        await update.message.reply_text(f"User @{recipient_username} not found.")
        return
    
    if sender_id == recipient_id:
        await update.message.reply_text("You can't gift yourself!")
        return
    
    if not db.has_sufficient_balance(sender_id, amount):
        await update.message.reply_text("Insufficient balance for this gift.")
        return
    
    db.deduct_balance(sender_id, amount)
    db.add_balance(recipient_id, amount)
    
    sender_balance = db.get_balance(sender_id)
    recipient_balance = db.get_balance(recipient_id)
    
    await update.message.reply_text(
        f"🎁 You gifted {amount} Hiwa to @{recipient_username}!\n"
        f"Your new balance: {sender_balance} Hiwa"
    )
    
    # Notify recipient
    await context.bot.send_message(
        chat_id=recipient_id,
        text=f"🎁 You received {amount} Hiwa from @{update.effective_user.username}!\n"
             f"New balance: {recipient_balance} Hiwa"
    )

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to broadcast a message to all users and groups."""
    user_id = update.effective_user.id
    if user_id not in config.ADMINS:
        await update.message.reply_text("This command is for admins only.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    
    message = " ".join(context.args)
    users = db.get_all_users()
    groups = db.get_all_groups()  # Ensure this function exists in your database handler
    all_chats = users + groups

    # Create invisible mention using the admin's ID
    admin_id = user_id
    invisible_mention = f'<a href="tg://user?id={admin_id}">&#8203;</a>'  # Zero-width space
    broadcast_text = f"📢 Admin Broadcast:\n\n{message}{invisible_mention}"

    # Send to all chats (users + groups)
    for chat_id in all_chats:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=broadcast_text,
                parse_mode="HTML"  # Required for HTML formatting
            )
        except Exception as e:
            logger.error(f"Failed to send broadcast to {chat_id}: {e}")
    
    await update.message.reply_text(f"Broadcast sent to {len(all_chats)} chats (users and groups).")

async def admin_reset_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to reset all users’ balances to 100."""
    user_id = update.effective_user.id
    if user_id not in config.ADMINS:
        await update.message.reply_text("This command is for admins only.")
        return

    # Call the new method that preserves all user data but sets balance = 100
    db.reset_all_balances_to_100()
    await update.message.reply_text("All users’ balances have been reset to 100.")

async def admin_set_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to set a user's balance."""
    user_id = update.effective_user.id
    if user_id not in config.ADMINS:
        await update.message.reply_text("This command is for admins only.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setbalance @username <amount>")
        return
    
    try:
        username = context.args[0].lstrip('@')
        amount = int(context.args[1])
    except (ValueError, IndexError):
        await update.message.reply_text("Usage: /setbalance @username <amount>")
        return
    
    target_id = db.get_user_id_by_username(username)
    if not target_id:
        await update.message.reply_text(f"User @{username} not found.")
        return
    
    db.set_balance(target_id, amount)
    await update.message.reply_text(f"Set @{username}'s balance to {amount} Hiwa.")

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(config.TOKEN).build()

    # Message Handler
    application.add_handler(
    MessageHandler(filters.ALL, auto_sync_user),
    group=-1
    )
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, track_groups))
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("mine", start_game))
    application.add_handler(CommandHandler("bet", bet_command))
    application.add_handler(CommandHandler("cashout", cashout_command))
    application.add_handler(CommandHandler("end", end_game))
    application.add_handler(CommandHandler("daily", daily_bonus))
    application.add_handler(CommandHandler("weekly", weekly_bonus))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("store", store))
    application.add_handler(CommandHandler("buy", buy_emoji))
    application.add_handler(CommandHandler("set", set_emoji))
    application.add_handler(CommandHandler("collection", collection))
    application.add_handler(CommandHandler("give", emoji_gift))
    application.add_handler(CommandHandler("gift", gift))

    #TicTacToe Time run out for invitation
    application.job_queue.run_repeating(cleanup_invitations, interval=60)
    
    # Admin commands
    application.add_handler(CommandHandler("broadcast", admin_broadcast))
    application.add_handler(CommandHandler("reset", admin_reset_data))
    application.add_handler(CommandHandler("setbalance", admin_set_balance))
    
    # Button click handler
    application.add_handler(CommandHandler("bet", bet_command))
    application.add_handler(CallbackQueryHandler(tictactoe_button, pattern=r"^ttt_(bot|invite|accept)_"))
    application.add_handler(CallbackQueryHandler(handle_game_move, pattern=r"^ttt_move_"))
    application.add_handler(CallbackQueryHandler(button_click))                                 
    
    # Run the bot
    application.run_polling()

if __name__ == '__main__':
    main()
    
