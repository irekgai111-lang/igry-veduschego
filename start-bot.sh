#!/bin/bash
# Запуск/перезапуск бота архива игр (с PID-файлом)
cd /home/agent/projects/igry-veduschego

PIDFILE="/home/agent/projects/igry-veduschego/bot.pid"

# Убить старый процесс по PID-файлу
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID"
        sleep 1
    fi
    rm -f "$PIDFILE"
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
echo $! > "$PIDFILE"
echo "Бот запущен, PID: $(cat $PIDFILE)"
