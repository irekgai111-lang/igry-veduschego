#!/bin/bash
# Запуск/перезапуск бота архива игр
cd /home/agent/projects/igry-veduschego

# Убить старый процесс если есть
OLD=$(pgrep -f "igry-veduschego/bot.py")
if [ -n "$OLD" ]; then
    kill "$OLD" 2>/dev/null
    sleep 1
fi

# Запустить
IGRY_BOT_TOKEN=$(python3 -c "
with open('.env') as f:
    for l in f:
        if 'IGRY_BOT_TOKEN' in l:
            print(l.split('=',1)[1].strip())
")
export IGRY_BOT_TOKEN
nohup python3 bot.py >> bot.log 2>&1 &
echo "Бот запущен, PID: $!"
