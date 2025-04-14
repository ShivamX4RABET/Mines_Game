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
from typing import Optional

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize database
db = UserDatabase('users.json')

# Game states
user_games: dict[int, MinesGame] = {}

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

async def send_game_board(update: Update, user_id: int, game: MinesGame, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the interactive game board."""
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
    
    if game.gems_revealed >= 2:
        keyboard.append([
            InlineKeyboardButton(
                f"💰 Cash Out ({game.current_multiplier:.2f}x)", 
                callback_data="cashout"
            )
        ])
    
    text = (
        f"💎 Mines Game 💣\n\n"
        f"Bet: {game.bet_amount} Hiwa\n"
        f"Mines: {game.mines_count}\n"
        f"Gems Found: {game.gems_revealed}/3\n"
        f"Multiplier: {game.current_multiplier:.2f}x\n"
        f"Potential Win: {int(game.bet_amount * game.current_multiplier)} Hiwa"
    )
    
    try:
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            msg = await context.bot.send_message(user_id, text, reply_markup=InlineKeyboardMarkup(keyboard))
            game.message_id = msg.message_id
    except Exception as e:
        logger.error(f"Error updating board: {e}")
    
    # Add cashout button if eligible
    if game.gems_revealed >= 2:
        keyboard.append([InlineKeyboardButton(
            f"💰 Cash Out ({game.current_multiplier:.2f}x)", 
            callback_data="cashout"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"💎 Mines Game 💣\n\n"
        f"Bet: {game.bet_amount} Hiwa\n"
        f"Mines: {game.mines_count}\n"
        f"Gems Found: {game.gems_revealed}/3\n"
        f"Current Multiplier: {game.current_multiplier:.2f}x\n"
        f"Potential Win: {game.bet_amount * game.current_multiplier:.2f} Hiwa\n\n"
        "Click tiles to reveal them!"
    )
    
    try:
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            message = await context.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=reply_markup
            )
            game.message_id = message.message_id
    except Exception as e:
        logger.error(f"Error sending game board: {e}")

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
    await send_game_board(update, user_id, game, context)

async def update_game_board(update: Update, game: MinesGame, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Refresh the game board display"""
    keyboard = []
    for i in range(5):
        row = []
        for j in range(5):
            tile = game.board[i][j]
            text = tile.value if tile.revealed else "🟦"
            row.append(InlineKeyboardButton(text, callback_data=f"reveal_{i}_{j}"))
        keyboard.append(row)
    
    if game.gems_revealed >= 2:
        keyboard.append([InlineKeyboardButton(
            f"💰 Cash Out ({game.current_multiplier:.2f}x)", 
            callback_data="cashout"
        )])
    
    text = (
        f"💎 Mines Game 💣\n"
        f"Bet: {game.bet_amount} Hiwa\n"
        f"Mines: {game.mines_count}\n"
        f"Gems Found: {game.gems_revealed}/25\n"
        f"Multiplier: {game.current_multiplier:.2f}x\n"
        f"Potential Win: {int(game.bet_amount * game.current_multiplier)} Hiwa"
    )
    
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except:
        await context.bot.edit_message_text(text, user_id, game.message_id, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_game_over(update: Update, user_id: int, game: MinesGame, won: bool, context: ContextTypes.DEFAULT_TYPE):
    """Handle game conclusion"""
    # Remove game from active sessions
    if user_id in user_games:
        del user_games[user_id]
    
    # Show final board
    keyboard = []
    for row in game.board:
        keyboard_row = []
        for tile in row:
            keyboard_row.append(InlineKeyboardButton(tile.value, callback_data="ignore"))
        keyboard.append(keyboard_row)
    
    if won:
        msg = f"🎉 Cashout Successful!\nWon: {int(game.bet_amount * game.current_multiplier)} Hiwa"
    else:
        msg = f"💥 Game Over!\nLost: {game.bet_amount} Hiwa"
    
    await update.callback_query.edit_message_text(
        f"{msg}\nNew Balance: {db.get_balance(user_id)} Hiwa",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all button interactions"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Check if user has an active game
    if user_id not in user_games:
        await query.edit_message_text("🚫 No active game! Use /mine to start")
        return
    
    game = user_games[user_id]
    
    # Handle cashout button
    if query.data == "cashout":
        if game.gems_revealed >= 2:
            win_amount = int(game.bet_amount * game.current_multiplier)
            db.add_balance(user_id, win_amount)
            await handle_game_over(update, user_id, game, won=True, context=context)
        else:
            await query.answer("❌ You need at least 2 gems to cash out!", show_alert=True)
    
    # Handle tile reveals (THIS MUST BE AT SAME LEVEL AS CASHOUT IF)
    elif query.data.startswith("reveal_"):  # Properly aligned with parent 'if'
        _, row, col = query.data.split("_")
        row = int(row)
        col = int(col)
        
        if game.reveal_tile(row, col):
            await update_game_board(update, game, context)
        else:
            await handle_game_over(update, user_id, game, won=False, context=context)

async def cashout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cashout command"""
    user_id = update.effective_user.id
    if user_id not in user_games:
        await update.message.reply_text("No active game! Start with /mine")
        return
    
    game = user_games[user_id]
    if game.gems_revealed >= 2:
        winnings = int(game.bet_amount * game.current_multiplier)
        db.add_balance(user_id, winnings)
        await handle_game_over(update, user_id, game, won=True, context=context)
    else:
        await update.message.reply_text("You need at least 2 gems to cash out!")
        
        # Tile reveal handling
    elif query.data.startswith("reveal_"):  # Now properly connected to parent 'if'
        _, row, col = query.data.split("_")
        row = int(row)
        col = int(col)
        
        if game.reveal_tile(row, col):
            await update_game_board(update, game, context)
        else:
            await handle_game_over(update, user_id, game, won=False, context=context)
                
    except Exception as e:
        logger.error(f"Button click error: {e}")
        await query.edit_message_text("❌ Error processing action. Try again.")
    
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

async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle daily bonus with proper cooldown message"""
    user_id = update.effective_user.id
    
    try:
        last_claim = db.get_last_daily(user_id)
        now = datetime.datetime.now()
        
        if last_claim:
            next_available = last_claim + datetime.timedelta(hours=24)
            if now < next_available:
                remaining = next_available - now
                hours, remainder = divmod(remaining.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                await update.message.reply_text(
                    f"⏳ *Daily Bonus Already Claimed!*\n\n"
                    f"You've already collected your daily bonus.\n"
                    f"Next available in: *{hours}h {minutes}m*\n"
                    f"Reset time: {next_available.strftime('%Y-%m-%d %H:%M:%S')}",
                    parse_mode='Markdown'
                )
                return
        
        # Grant bonus if not claimed or cooldown passed
        amount = 50
        db.add_balance(user_id, amount)
        db.set_last_daily(user_id, now)
        
        await update.message.reply_text(
            f"🎁 *Daily Bonus Collected!*\n\n"
            f"+{amount} Hiwa added to your balance\n"
            f"New balance: *{db.get_balance(user_id)} Hiwa*\n\n"
            f"Next bonus available in 24 hours",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Daily bonus error: {e}")
        await update.message.reply_text("❌ Error processing daily bonus. Please try again.")

async def weekly_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle weekly bonus with proper cooldown message"""
    user_id = update.effective_user.id
    
    try:
        last_claim = db.get_last_weekly(user_id)
        now = datetime.datetime.now()
        
        if last_claim:
            next_available = last_claim + datetime.timedelta(days=7)
            if now < next_available:
                remaining = next_available - now
                days = remaining.days
                hours, remainder = divmod(remaining.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                await update.message.reply_text(
                    f"⏳ *Weekly Bonus Already Claimed!*\n\n"
                    f"You've already collected your weekly bonus.\n"
                    f"Next available in: *{days}d {hours}h {minutes}m*\n"
                    f"Reset time: {next_available.strftime('%Y-%m-%d %H:%M:%S')}",
                    parse_mode='Markdown'
                )
                return
        
        # Grant bonus if not claimed or cooldown passed
        amount = 200
        db.add_balance(user_id, amount)
        db.set_last_weekly(user_id, now)
        
        await update.message.reply_text(
            f"🎁 *Weekly Bonus Collected!*\n\n"
            f"+{amount} Hiwa added to your balance\n"
            f"New balance: *{db.get_balance(user_id)} Hiwa*\n\n"
            f"Next bonus available in 7 days",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Weekly bonus error: {e}")
        await update.message.reply_text("❌ Error processing weekly bonus. Please try again.")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debugged leaderboard command"""
    try:
        top_users = db.get_top_users(10)
        logger.info(f"Leaderboard data fetched: {top_users}")  # Debug logging
        
        if not top_users:
            await update.message.reply_text("🏆 Leaderboard is empty! Be the first to play!")
            return

        message = ["🏆 <b>TOP PLAYERS</b> 🏆", "", "<pre>"]
        headers = ["Rank", "Player", "Balance"]
        message.append(f"{headers[0]:<5} {headers[1]:<15} {headers[2]:>10}")
        message.append("-"*35)
        
        for rank, (user_id, username, balance) in enumerate(top_users, 1):
            display_name = username if username else f"User{str(user_id)[:4]}"
            message.append(f"{rank:<5} {display_name[:15]:<15} {balance:>10} Hiwa")
        
        message.extend(["</pre>", "", "Play /mine to climb ranks!"])
        await update.message.reply_text("\n".join(message), parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        await update.message.reply_text("⚠️ Couldn't fetch leaderboard. Please try later.")

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
