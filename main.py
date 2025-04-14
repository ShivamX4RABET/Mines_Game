import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from game_logic import MinesGame
from database import UserDatabase
import config
import datetime
from typing import Dict

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize database
db = UserDatabase('users.json')

# Game states
user_games: Dict[int, MinesGame] = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    if not db.user_exists(user.id):
        db.add_user(user.id, user.username or user.first_name, 100)
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

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a new Mines game."""
    user = update.effective_user
    user_id = user.id
    
    # Check if user is already in a game
    if user_id in user_games:
        await update.message.reply_text("You already have an active game! Finish it first.")
        return
    
    # Validate arguments
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /mine <amount> <mines>\nExample: /mine 10 5")
        return
    
    try:
        amount = int(context.args[0])
        mines = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Please enter valid numbers for amount and mines.")
        return
    
    # Validate amount and mines
    if amount < 1:
        await update.message.reply_text("Amount must be at least 1 Hiwa.")
        return
    
    if mines < 3 or mines > 24:
        await update.message.reply_text("Number of mines must be between 3 and 24.")
        return
    
    # Check balance
    if not db.has_sufficient_balance(user_id, amount):
        await update.message.reply_text("Insufficient balance for this bet.")
        return
    
    # Deduct balance and start game
    db.deduct_balance(user_id, amount)
    game = MinesGame(amount, mines)
    user_games[user_id] = game
    
    # Show initial game board
    await send_game_board(update, user_id, game)

async def send_game_board(update: Update, user_id: int, game: MinesGame) -> None:
    """Send or update the game board."""
    keyboard = []
    for i in range(5):
        row = []
        for j in range(5):
            tile = game.board[i][j]
            if tile.revealed:
                row.append(InlineKeyboardButton(tile.value, callback_data=f"ignore_{i}_{j}"))
            else:
                row.append(InlineKeyboardButton("🟦", callback_data=f"reveal_{i}_{j}"))
        keyboard.append(row)
    
    # Add cashout button if eligible
    if game.gems_revealed >= 2:
        keyboard.append([InlineKeyboardButton(f"💰 Cash Out ({game.current_multiplier:.2f}x)", callback_data="cashout")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Calculate potential win
    potential_win = game.bet_amount * game.current_multiplier
    
    text = (
        f"💎 Mines Game 💣\n\n"
        f"Bet: {game.bet_amount} Hiwa\n"
        f"Mines: {game.mines_count}\n"
        f"Gems Found: {game.gems_revealed}/3\n"
        f"Current Multiplier: {game.current_multiplier:.2f}x\n"
        f"Potential Win: {potential_win:.2f} Hiwa\n\n"
        "Click tiles to reveal them!"
    )
    
    if game.message_id:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        message = await context.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup
        )
        game.message_id = message.message_id

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks (tile reveals and cashout)."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id not in user_games:
        await query.edit_message_text("Your game session has expired. Start a new game with /mine")
        return
    
    game = user_games[user_id]
    
    if query.data.startswith("reveal_"):
        # Tile reveal logic
        _, i, j = query.data.split("_")
        i, j = int(i), int(j)
        
        if game.reveal_tile(i, j):
            # Tile was a gem
            await send_game_board(update, user_id, game)
        else:
            # Tile was a bomb - game over
            await handle_game_over(update, user_id, game, won=False)
    elif query.data == "cashout":
        # Cashout logic
        if game.gems_revealed >= 2:
            await handle_game_over(update, user_id, game, won=True)
        else:
            await query.answer("You need at least 2 gems to cash out!", show_alert=True)

async def handle_game_over(update: Update, user_id: int, game: MinesGame, won: bool) -> None:
    """Handle game over (win or loss)."""
    if won:
        win_amount = game.bet_amount * game.current_multiplier
        db.add_balance(user_id, win_amount)
        message = (
            f"🎉 You cashed out and won {win_amount:.2f} Hiwa!\n\n"
            f"Final Multiplier: {game.current_multiplier:.2f}x\n"
            f"New Balance: {db.get_balance(user_id)} Hiwa\n\n"
            "Play again with /mine"
        )
    else:
        message = (
            f"💥 Boom! You hit a bomb and lost {game.bet_amount} Hiwa.\n\n"
            f"Gems Found: {game.gems_revealed}\n"
            f"New Balance: {db.get_balance(user_id)} Hiwa\n\n"
            "Try again with /mine"
        )
    
    # Show final board
    keyboard = []
    for i in range(5):
        row = []
        for j in range(5):
            tile = game.board[i][j]
            row.append(InlineKeyboardButton(tile.value, callback_data=f"ignore_{i}_{j}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🎮 Play Again", callback_data="new_game")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup)
    del user_games[user_id]

async def cashout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cashout command."""
    user_id = update.effective_user.id
    if user_id not in user_games:
        await update.message.reply_text("You don't have an active game to cash out.")
        return
    
    game = user_games[user_id]
    if game.gems_revealed < 2:
        await update.message.reply_text("You need at least 2 gems revealed to cash out!")
        return
    
    await handle_game_over(update, user_id, game, won=True)

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
    """Show the leaderboard."""
    top_users = db.get_top_users(10)
    message = "🏆 *Top Players Leaderboard* 🏆\n\n"
    
    for i, (user_id, username, balance) in enumerate(top_users, 1):
        message += f"{i}. {username}: {balance} Hiwa\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def gift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /gift command."""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /gift @username <amount>")
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
    """Admin command to broadcast a message to all users."""
    user_id = update.effective_user.id
    if user_id not in config.ADMINS:
        await update.message.reply_text("This command is for admins only.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    
    message = " ".join(context.args)
    users = db.get_all_users()
    
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 Admin Broadcast:\n\n{message}")
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
    
    await update.message.reply_text(f"Broadcast sent to {len(users)} users.")

async def admin_reset_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to reset all user data."""
    user_id = update.effective_user.id
    if user_id not in config.ADMINS:
        await update.message.reply_text("This command is for admins only.")
        return
    
    db.reset_all_data()
    await update.message.reply_text("All user data has been reset.")

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
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("mine", start_game))
    application.add_handler(CommandHandler("cashout", cashout_command))
    application.add_handler(CommandHandler("daily", daily_bonus))
    application.add_handler(CommandHandler("weekly", weekly_bonus))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("gift", gift))
    
    # Admin commands
    application.add_handler(CommandHandler("broadcast", admin_broadcast))
    application.add_handler(CommandHandler("resetdata", admin_reset_data))
    application.add_handler(CommandHandler("setbalance", admin_set_balance))
    
    # Button click handler
    application.add_handler(CallbackQueryHandler(button_click))
    
    # Run the bot
    application.run_polling()

if __name__ == '__main__':
    main()