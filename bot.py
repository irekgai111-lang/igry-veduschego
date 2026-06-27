#!/usr/bin/env python3
"""Бот архива игр ведущего Ирека."""

import json
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

TOKEN = os.getenv('IGRY_BOT_TOKEN', '')
GAMES_FILE = os.path.join(os.path.dirname(__file__), 'games.json')
PAGE_SIZE = 5

EVENT_ALIASES = {
    'свадьб': 'свадьба', 'свадьба': 'свадьба',
    'юбилей': 'юбилей', 'юбил': 'юбилей',
    'выпускной': 'выпускной', 'выпускн': 'выпускной', 'выпуск': 'выпускной',
    'корпоратив': 'корпоратив', 'корпорат': 'корпоратив', 'корпор': 'корпоратив',
    'день рождения': 'день рождения', 'дн рожд': 'день рождения',
    'семейный': 'семейный праздник',
}

FORMAT_ALIASES = {
    'командн': 'командная', 'команд': 'командная',
    'массов': 'массовая',
    'застольн': 'застольная', 'застол': 'застольная',
    'парн': 'одиночная/парная', 'одиночн': 'одиночная/парная',
}


def load_games():
    with open(GAMES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_query(text):
    """Извлекает фильтры из текста."""
    t = text.lower()
    filters_found = {'events': None, 'format': None, 'audio': None, 'screen': None, 'text': text}

    for alias, event in EVENT_ALIASES.items():
        if alias in t:
            filters_found['events'] = event
            break

    for alias, fmt in FORMAT_ALIASES.items():
        if alias in t:
            filters_found['format'] = fmt
            break

    if 'аудио' in t or 'музык' in t or 'с аудио' in t:
        filters_found['audio'] = True
    if 'без аудио' in t or 'без музыки' in t:
        filters_found['audio'] = False

    if 'без экран' in t:
        filters_found['screen'] = 'без экрана'
    elif 'экран' in t or 'проектор' in t:
        filters_found['screen'] = 'обязательный'

    return filters_found


def filter_games(games, f, hide_dups=True):
    result = []
    for g in games:
        if hide_dups and g.get('duplicate_of'):
            continue
        if f['events'] and f['events'] not in g.get('events', []):
            continue
        if f['format'] and f['format'] not in g.get('format', []):
            continue
        if f['audio'] is not None and g.get('audio') != f['audio']:
            continue
        if f['screen'] and g.get('screen') != f['screen']:
            continue
        result.append(g)
    return result


def fmt_card(g, short=True):
    """Форматирует карточку игры для Telegram."""
    icons = []
    if g.get('audio'):
        icons.append('🎵')
    scr = g.get('screen', '')
    if scr == 'обязательный':
        icons.append('📺')
    elif scr == 'без экрана':
        pass
    else:
        icons.append('📺/💬')
    if g.get('players'):
        icons.append(f"👥 {g['players']}")
    if g.get('duration'):
        icons.append(f"⏱ {g['duration']} мин")

    events = ', '.join(g.get('events', []))
    fmts = ', '.join(g.get('format', []))

    lines = [f"🎭 <b>{g['name']}</b>"]
    if icons:
        lines.append(' · '.join(icons))
    if events:
        lines.append(f"📌 {events}")
    if fmts:
        lines.append(f"🎯 {fmts}")

    if not short and g.get('description'):
        lines.append('')
        lines.append(g['description'])

    if not short and g.get('notes') and not g['notes'].startswith(('📄', '⚙️')):
        lines.append(f"💡 {g['notes']}")

    if g.get('folder'):
        lines.append(f"📁 G:\\...\\{g['folder']}")

    return '\n'.join(lines)


def paginate_keyboard(page, total_pages, prefix):
    """Кнопки пагинации."""
    btns = []
    if page > 0:
        btns.append(InlineKeyboardButton('◀ Назад', callback_data=f'{prefix}:{page-1}'))
    btns.append(InlineKeyboardButton(f'{page+1}/{total_pages}', callback_data='noop'))
    if page < total_pages - 1:
        btns.append(InlineKeyboardButton('Вперёд ▶', callback_data=f'{prefix}:{page+1}'))
    return InlineKeyboardMarkup([btns])


# ── хранилище сессий ──
sessions = {}


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        '🎭 <b>Архив игр ведущего — Ирек</b>\n\n'
        'Напиши что нужно:\n'
        '• <code>игры на свадьбу</code>\n'
        '• <code>командные игры на юбилей</code>\n'
        '• <code>игры без экрана для выпускного</code>\n'
        '• <code>застольные игры на корпоратив</code>\n\n'
        'Команды:\n'
        '/svadba · /yubiley · /vypusknoj · /korporativ\n'
        '/vse — все игры\n'
        '/dubli — повторы в архиве',
        parse_mode='HTML'
    )


async def cmd_event(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cmd = update.message.text.lstrip('/').split('@')[0]
    aliases = {
        'svadba': 'свадьба',
        'yubiley': 'юбилей',
        'vypusknoj': 'выпускной',
        'korporativ': 'корпоратив',
    }
    event = aliases.get(cmd)
    if event:
        await show_event(update, ctx, event, page=0)


async def cmd_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    games = load_games()
    unique = [g for g in games if not g.get('duplicate_of')]
    await send_page(update, ctx, unique, 0, 'all')


async def cmd_dups(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    games = load_games()
    dups = [g for g in games if g.get('duplicate_of')]
    if not dups:
        await update.message.reply_text('✅ Дублей в архиве нет.')
        return
    lines = [f'⚠️ <b>Дубли ({len(dups)} шт.):</b>\n']
    for g in dups:
        orig = next((x for x in games if x['id'] == g['duplicate_of']), None)
        orig_name = orig['name'] if orig else f"#{g['duplicate_of']}"
        lines.append(f"• <b>{g['name']}</b> → дубль «{orig_name}»")
    await update.message.reply_html('\n'.join(lines))


async def show_event(update, ctx, event, page):
    games = load_games()
    f = {'events': event, 'format': None, 'audio': None, 'screen': None, 'text': ''}
    found = filter_games(games, f)
    uid = update.effective_user.id
    sessions[uid] = {'games': found, 'query': event}
    await send_page(update, ctx, found, page, f'ev:{event}')


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    games = load_games()
    f = parse_query(text)

    # Если нет ни одного фильтра — поиск по названию
    no_filter = not f['events'] and f['format'] is None and f['audio'] is None and f['screen'] is None
    if no_filter:
        q = text.lower()
        found = [g for g in games if not g.get('duplicate_of') and
                 (q in g['name'].lower() or q in g.get('description', '').lower())]
    else:
        found = filter_games(games, f)

    uid = update.effective_user.id
    sessions[uid] = {'games': found, 'query': text}

    if not found:
        await update.message.reply_text(
            '🔍 Игры не найдены.\n\nПопробуй: <code>игры на свадьбу</code> '
            'или /все чтобы увидеть весь архив.',
            parse_mode='HTML'
        )
        return

    prefix = f'q:{uid}'
    await send_page(update, ctx, found, 0, prefix)


async def send_page(update_or_query, ctx, games, page, prefix):
    total = len(games)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    slice_ = games[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    header = f'<b>Найдено игр: {total}</b> · страница {page+1}/{total_pages}\n\n'
    cards = '\n\n─────────────\n\n'.join(fmt_card(g, short=True) for g in slice_)
    text = header + cards

    if total_pages > 1:
        kb = paginate_keyboard(page, total_pages, prefix)
    else:
        kb = None

    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_html(text, reply_markup=kb)
    else:
        await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=kb)


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'noop':
        return

    if data.startswith('ev:'):
        _, event, page = data.split(':', 2)
        games = load_games()
        f = {'events': event, 'format': None, 'audio': None, 'screen': None, 'text': ''}
        found = filter_games(games, f)
        await send_page(query, ctx, found, int(page), data.rsplit(':', 1)[0])

    elif data.startswith('q:'):
        parts = data.split(':', 2)
        uid = int(parts[1])
        page = int(parts[2])
        sess = sessions.get(uid)
        if sess:
            await send_page(query, ctx, sess['games'], page, f'q:{uid}')

    elif data.startswith('all:'):
        page = int(data.split(':', 1)[1])
        games = load_games()
        unique = [g for g in games if not g.get('duplicate_of')]
        await send_page(query, ctx, unique, page, 'all')


def main():
    if not TOKEN:
        raise RuntimeError('IGRY_BOT_TOKEN не задан. Добавь в .env файл.')

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('svadba', cmd_event))
    app.add_handler(CommandHandler('yubiley', cmd_event))
    app.add_handler(CommandHandler('vypusknoj', cmd_event))
    app.add_handler(CommandHandler('korporativ', cmd_event))
    app.add_handler(CommandHandler('vse', cmd_all))
    app.add_handler(CommandHandler('dubli', cmd_dups))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info('Бот архива запущен')
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
