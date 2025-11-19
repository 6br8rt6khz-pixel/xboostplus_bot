# xboostplus_bot_complete.py
import logging
import aiosqlite
import asyncio
import nest_asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

# --- CONFIG (REPLACE THESE) ---
BOT_TOKEN = "7993515747:AAGu9tHn4bnGc8PqEKnw07tlRbdaCHTvq3c"   # <-- paste BotFather token here
ADMIN_ID = 5520772144                      # <-- replace with your Telegram numeric ID
ETH_ADDRESS = "0x2eEf07a5728cABC9D9448C028108f163c7B5fb62"
BNB_ADDRESS = "0x2eEf07a5728cABC9D9448C028108f163c7B5fb62"
SOL_ADDRESS = "4jPJjozoYxB8R64Nxygvg255vvyRREnzXr5WZ5742eJN"
DB_PATH = "xboostplus.db"

# --- Setup event loop fix for macOS / interactive environments ---
nest_asyncio.apply()

# --- LOGGING ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CALLBACK DATA ---
CB_SUBSCRIBE = "subscribe"
CB_FOLLOWERS = "followers"
CB_ORDERS = "orders"
CB_REFERRAL = "referral"
CB_HOW_WORKS = "how_works"
CB_REF_HOW = "ref_how"
CB_SUPPORT = "support"
CB_BACK = "back"
CB_MAIN_MENU = "main_menu"
CB_ADD_ACCOUNT = "add_account"

# --- SERVICES & PACKAGES ---
SERVICES = {
    "subscribe": {
        "name": "Subscribe / Boost Tweets",
        "packages": [
            ("turbo", "TURBO — $449/Week", 449, "1 Week"),
            ("low", "Low Tier — $399/Month", 399, "1 Month"),
            ("tier1", "Tier 1 — $599/Month", 599, "1 Month"),
            ("tier2", "Tier 2 — $1049/Month", 1049, "1 Month"),
            ("tier3", "Tier 3 — $1549/Month", 1549, "1 Month"),
            ("tier4", "Tier 4 — $2499/Month", 2499, "1 Month")
        ]
    },
    "followers": {
        "name": "Buy X Followers",
        "packages": [
            ("blue50", "Starter — 50 Blue Tick Followers — $399", 399, "Instant"),
            ("blue100", "Pro — 100 Blue Tick Followers — $799", 799, "Instant"),
            ("blue200", "Elite — 200 Blue Tick Followers — $1399", 1399, "Instant"),
            ("std500", "Starter — 500 Standard Followers — $249", 249, "Instant"),
            ("std1000", "Growth — 1,000 Standard Followers — $449", 449, "Instant"),
            ("std1500", "Pro — 1,500 Standard Followers — $599", 599, "Instant"),
            ("std2000", "Max — 2,000 Standard Followers — $799", 799, "Instant")
        ]
    }
}

# --- DATABASE SETUP ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                x_handle TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                account_id INTEGER,
                service TEXT,
                package TEXT,
                price REAL,
                duration TEXT,
                chain TEXT,
                tx_hash TEXT,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(account_id) REFERENCES accounts(id)
            )
        """)
        await db.commit()

# --- KEYBOARDS HELPERS ---
def main_menu_keyboard():
    kb = [
        [InlineKeyboardButton("Subscribe", callback_data=CB_SUBSCRIBE)],
        [InlineKeyboardButton("Buy X Followers", callback_data=CB_FOLLOWERS)],
        [InlineKeyboardButton("Orders", callback_data=CB_ORDERS)],
        [InlineKeyboardButton("How XBoostPlus Works", callback_data=CB_HOW_WORKS)],
        [InlineKeyboardButton("Referral", callback_data=CB_REF_HOW)],
        [InlineKeyboardButton("Support", callback_data=CB_SUPPORT)]
    ]
    return InlineKeyboardMarkup(kb)

def back_and_menu_keyboard():
    kb = [
        [InlineKeyboardButton("Back", callback_data=CB_BACK)],
        [InlineKeyboardButton("Main Menu", callback_data=CB_MAIN_MENU)]
    ]
    return InlineKeyboardMarkup(kb)

def payment_chain_keyboard():
    kb = [
        [InlineKeyboardButton("Ethereum", callback_data="pay_eth")],
        [InlineKeyboardButton("BNB Smart Chain", callback_data="pay_bnb")],
        [InlineKeyboardButton("Solana", callback_data="pay_sol")],
        [InlineKeyboardButton("Back", callback_data=CB_BACK)]
    ]
    return InlineKeyboardMarkup(kb)

# --- UTILS ---
async def get_or_create_user(tid, username):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM users WHERE telegram_id = ?", (tid,))
        row = await cur.fetchone()
        if row:
            return row[0]
        cur = await db.execute("INSERT INTO users (telegram_id, username) VALUES (?, ?)", (tid, username))
        await db.commit()
        return cur.lastrowid

def push_nav(context: ContextTypes.DEFAULT_TYPE, page_id: str, payload: dict = None):
    """Push a page onto the user's navigation stack."""
    stack = context.user_data.get("nav_stack", [])
    stack.append({"page": page_id, "payload": payload})
    context.user_data["nav_stack"] = stack

def pop_nav(context: ContextTypes.DEFAULT_TYPE):
    """Pop current page and return previous entry or None."""
    stack = context.user_data.get("nav_stack", [])
    if stack:
        stack.pop()  # remove current
    if stack:
        return stack[-1]
    return None

def current_nav(context: ContextTypes.DEFAULT_TYPE):
    stack = context.user_data.get("nav_stack", [])
    return stack[-1] if stack else None

# --- START HANDLER ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Clear nav stack and push main menu as first page
    context.user_data["nav_stack"] = []
    push_nav(context, "main_menu")
    msg = (
        "Welcome to XBoostPlus! 🚀\n\n"
        "Automatic tweet boosts and followers packages for Projects, KOLs, Creators, and Brands.\n\n"
        "Choose an option below to get started."
    )
    await update.message.reply_text(msg, reply_markup=main_menu_keyboard())

# --- CALLBACK ROUTER (central) ---
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user
    await get_or_create_user(user.id, user.username)  # ensure user exists

    # MAIN / BACK navigation
    if data == CB_MAIN_MENU:
        context.user_data["nav_stack"] = []
        push_nav(context, "main_menu")
        await query.edit_message_text("Main Menu:", reply_markup=main_menu_keyboard())
        return

    if data == CB_BACK:
        prev = pop_nav(context)
        if not prev:
            # no previous: show main menu
            context.user_data["nav_stack"] = []
            push_nav(context, "main_menu")
            await query.edit_message_text("Main Menu:", reply_markup=main_menu_keyboard())
            return
        # route to previous page
        page = prev["page"]
        payload = prev.get("payload")
        # call renderer based on page id
        if page == "select_account_for_service":
            await show_user_accounts_for_service(query, context, payload["service_key"], push_stack=False)
            return
        if page == "service_packages":
            await show_service_packages(query, context, payload["service_key"], push_stack=False)
            return
        if page == "orders_accounts":
            await show_accounts_for_orders(query, context, push_stack=False)
            return
        # fallback to main menu
        context.user_data["nav_stack"] = []
        push_nav(context, "main_menu")
        await query.edit_message_text("Main Menu:", reply_markup=main_menu_keyboard())
        return

    # Add account entry
    if data == CB_ADD_ACCOUNT:
        # push a page so Back returns here while adding
        push_nav(context, "adding_account")
        context.user_data["adding_account"] = True
        await query.edit_message_text("Please send your X (Twitter) handle (without @):", reply_markup=back_and_menu_keyboard())
        return

    # Services: show accounts to choose from
    if data in (CB_SUBSCRIBE, CB_FOLLOWERS):
        service_key = "subscribe" if data == CB_SUBSCRIBE else "followers"
        await show_user_accounts_for_service(query, context, service_key)
        return

    # Account selected for service -> show packages
    if data.startswith("acctsvc|"):
        _, service_key, acct_id = data.split("|")
        context.user_data["selected_account"] = acct_id
        await show_service_packages(query, context, service_key)
        return

    # Package selected
    if data.startswith("pkg|"):
        _, service_key, package_id = data.split("|")
        await handle_package_selected(query, context, service_key, package_id)
        return

    # Payment chain selection
    if data.startswith("pay_"):
        chain = data.split("_")[1]
        await show_payment_page(query, context, chain)
        return

    # I've Paid button
    if data == "paid":
        # push a 'awaiting_proof' page
        push_nav(context, "awaiting_proof", payload=context.user_data.get("last_package"))
        await query.edit_message_text("Please upload the transaction hash as text or a screenshot as proof of payment.", reply_markup=back_and_menu_keyboard())
        return

    # Orders flow
    if data == CB_ORDERS:
        await show_accounts_for_orders(query, context)
        return

    if data.startswith("orders_acct|"):
        _, account_id = data.split("|")
        await show_orders_for_account(query, context, account_id)
        return

# --- SHOW / RENDER FUNCTIONS ---
async def show_user_accounts_for_service(query, context, service_key, push_stack=True):
    # list user's saved X accounts or show Add Account
    user = query.from_user
    user_rowid = await get_or_create_user(user.id, user.username)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, x_handle FROM accounts WHERE user_id = ?", (user_rowid,))
        rows = await cur.fetchall()
    kb = []
    if rows:
        for rid, handle in rows:
            cb = f"acctsvc|{service_key}|{rid}"
            kb.append([InlineKeyboardButton(str(handle), callback_data=cb)])
    kb.append([InlineKeyboardButton("Add X Account", callback_data=CB_ADD_ACCOUNT)])
    kb.append([InlineKeyboardButton("Back", callback_data=CB_BACK)])
    if push_stack:
        push_nav(context, "select_account_for_service", payload={"service_key": service_key})
    await query.edit_message_text("📋 Select X Account to use for this service:", reply_markup=InlineKeyboardMarkup(kb))

async def show_service_packages(query, context, service_key, push_stack=True):
    svc = SERVICES.get(service_key)
    kb = [[InlineKeyboardButton(p[1], callback_data=f"pkg|{service_key}|{p[0]}")] for p in svc["packages"]]
    kb.append([InlineKeyboardButton("Back", callback_data=CB_BACK)])
    if push_stack:
        push_nav(context, "service_packages", payload={"service_key": service_key})
    await query.edit_message_text(f"Select a package for {svc['name']}:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_package_selected(query, context, service_key, package_id):
    svc = SERVICES.get(service_key)
    pkg = next((p for p in svc["packages"] if p[0] == package_id), None)
    last_account = context.user_data.get("selected_account")
    context.user_data["last_package"] = {
        "service_key": service_key,
        "package_id": package_id,
        "package_name": pkg[1],
        "price_usd": pkg[2],
        "duration": pkg[3],
        "account_id": last_account
    }
    # push package selection page so Back returns here if needed
    push_nav(context, "package_selected", payload={"service_key": service_key, "package_id": package_id})
    # show chain options
    msg = (
        f"📦 *{pkg[1]}*\n"
        f"⏰ Duration: {pkg[3]}\n"
        f"💲 Price: `${pkg[2]}`\n\n"
        "Choose which blockchain to pay with:"
    )
    await query.edit_message_text(msg, reply_markup=payment_chain_keyboard(), parse_mode="Markdown")

async def show_payment_page(query, context, chain):
    last_package = context.user_data.get("last_package")
    if not last_package:
        await query.edit_message_text("No package selected.", reply_markup=main_menu_keyboard())
        return

    # choose address and icon
    if chain == "eth":
        address = ETH_ADDRESS
        chain_name = "Ethereum (ETH)"
        chain_icon = "🟦"
    elif chain == "bnb":
        address = BNB_ADDRESS
        chain_name = "BNB Smart Chain (BNB)"
        chain_icon = "🟨"
    else:
        address = SOL_ADDRESS
        chain_name = "Solana (SOL)"
        chain_icon = "🟪"

    # push payment page to nav
    push_nav(context, "payment_page", payload={"chain": chain, "package": last_package})

    # professional payment message with monospace block
    msg = (
        f"💳 *Payment Required*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 *Package:*  {last_package['package_name']}\n"
        f"📆 *Duration:* {last_package['duration']}\n"
        f"💲 *Amount:*   `${last_package['price_usd']}`\n"
        f"{chain_icon} *Chain:* {chain_name}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 *Payment Address*\n"
        f"Send the exact amount to the address below:\n"
        f"```\n{address}\n```\n\n"
        f"⚠️ *Make sure the network you select matches the chain above.*\n"
        f"After payment, click *I've Paid* and upload your TX hash or a screenshot."
    )

    # store selected chain for verification later
    context.user_data["payment_chain"] = chain

    kb = [
        [InlineKeyboardButton("I've Paid", callback_data="paid")],
        [InlineKeyboardButton("Back", callback_data=CB_BACK)]
    ]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# --- ORDERS ---
async def show_accounts_for_orders(query, context, push_stack=True):
    user = query.from_user
    user_rowid = await get_or_create_user(user.id, user.username)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, x_handle FROM accounts WHERE user_id = ?", (user_rowid,))
        rows = await cur.fetchall()
    if not rows:
        await query.edit_message_text("No X accounts found. Add one first.", reply_markup=main_menu_keyboard())
        return
    kb = [[InlineKeyboardButton(str(h), callback_data=f"orders_acct|{rid}")] for rid, h in rows]
    kb.append([InlineKeyboardButton("Back", callback_data=CB_BACK)])
    if push_stack:
        push_nav(context, "orders_accounts")
    await query.edit_message_text("📋 Select X Account to view orders:", reply_markup=InlineKeyboardMarkup(kb))

async def show_orders_for_account(query, context, account_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT service, package, price, duration, chain, status
            FROM orders WHERE account_id = ?
            ORDER BY id DESC
        """, (account_id,))
        orders = await cur.fetchall()
    if not orders:
        await query.edit_message_text("No orders found for this account.", reply_markup=back_and_menu_keyboard())
        return
    msg_lines = ["📋 Orders for this X account:\n"]
    for idx, (service, package, price, duration, chain, status) in enumerate(orders, 1):
        msg_lines.append(f"{idx}. {package}\n   Service: {service}\n   Price: ${price}\n   Duration: {duration}\n   Chain: {chain}\n   Status: {status}\n")
    msg_text = "\n".join(msg_lines)
    await query.edit_message_text(msg_text, reply_markup=back_and_menu_keyboard())

# --- ADD ACCOUNT HANDLER (text) ---
async def handle_add_account_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("adding_account"):
        return  # ignore if not in add-account mode
    x_handle = update.message.text.strip().replace("@", "")
    user_rowid = await get_or_create_user(update.message.from_user.id, update.message.from_user.username)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO accounts (user_id, x_handle) VALUES (?, ?)", (user_rowid, x_handle))
        await db.commit()
    context.user_data["adding_account"] = False
    # pop adding_account from nav and go back to previous page
    pop_nav(context)
    await update.message.reply_text(f"✅ X account @{x_handle} added successfully!", reply_markup=main_menu_keyboard())

# --- PAYMENT PROOF HANDLING (text TX) ---
async def handle_tx_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # if user text is a tx hash after clicking I've Paid
    last_package = context.user_data.get("last_package")
    if not last_package:
        # if not in payment flow, check if adding account
        await handle_add_account_text(update, context)
        return
    # find payment_chain stored earlier
    chain = context.user_data.get("payment_chain")
    tx_hash = update.message.text.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO orders (user_id, account_id, service, package, price, duration, chain, tx_hash, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            update.message.from_user.id,
            last_package.get("account_id"),
            last_package.get("service_key"),
            last_package.get("package_name"),
            last_package.get("price_usd"),
            last_package.get("duration"),
            chain,
            tx_hash,
            "pending"
        ))
        await db.commit()

    # notify admin
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"💰 New payment submitted\n"
                f"User: @{update.message.from_user.username} ({update.message.from_user.id})\n"
                f"Package: {last_package['package_name']}\n"
                f"Amount: ${last_package['price_usd']}\n"
                f"Chain: {chain}\n"
                f"TX: `{tx_hash}`"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.exception("Failed to notify admin: %s", e)

    # clear last_package and payment_chain, pop nav
    context.user_data.pop("last_package", None)
    context.user_data.pop("payment_chain", None)
    pop_nav(context)  # remove awaiting_proof or payment page

    await update.message.reply_text("✅ Payment submitted. Admin will verify it shortly.", reply_markup=main_menu_keyboard())

# --- PAYMENT PROOF HANDLING (photo) ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last_package = context.user_data.get("last_package")
    if not last_package:
        # maybe user sending photo while adding account
        await update.message.reply_text("No active payment found. Use the menus to place an order.", reply_markup=main_menu_keyboard())
        return
    file_id = update.message.photo[-1].file_id
    chain = context.user_data.get("payment_chain")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO orders (user_id, account_id, service, package, price, duration, chain, tx_hash, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            update.message.from_user.id,
            last_package.get("account_id"),
            last_package.get("service_key"),
            last_package.get("package_name"),
            last_package.get("price_usd"),
            last_package.get("duration"),
            chain,
            file_id,
            "pending"
        ))
        await db.commit()

    # notify admin with photo
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"💰 New payment screenshot submitted\n"
                f"User: @{update.message.from_user.username} ({update.message.from_user.id})\n"
                f"Package: {last_package['package_name']}\n"
                f"Amount: ${last_package['price_usd']}\n"
                f"Chain: {chain}\n"
                f"File ID: {file_id}"
            )
        )
        # forward the photo for admin convenience
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=file_id, caption=f"Screenshot from @{update.message.from_user.username}")
    except Exception:
        logger.exception("Failed to notify admin about photo")

    # clear state
    context.user_data.pop("last_package", None)
    context.user_data.pop("payment_chain", None)
    pop_nav(context)
    await update.message.reply_text("✅ Payment submitted. Admin will verify it shortly.", reply_markup=main_menu_keyboard())

# --- GENERIC MESSAGE HANDLER ---
async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # priority: adding account -> tx text -> general
    if context.user_data.get("adding_account"):
        await handle_add_account_text(update, context)
        return
    # if awaiting payment proof (we treat any text as TX hash)
    nav = current_nav(context)
    if nav and nav.get("page") in ("awaiting_proof", "payment_page", "package_selected"):
        await handle_tx_text(update, context)
        return
    # otherwise, ignore or show main menu
    await update.message.reply_text("Please use the menu buttons.", reply_markup=main_menu_keyboard())

# --- MAIN & SETUP ---
async def main():
    await init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))

    logger.info("Starting bot...")
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")