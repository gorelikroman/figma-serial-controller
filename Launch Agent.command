#!/bin/bash
# ═══════════════════════════════════════
# Первый запуск — снимает карантин macOS
# и запускает приложение
# ═══════════════════════════════════════
DIR="$(cd "$(dirname "$0")" && pwd)"
APP="$DIR/Figma Serial Agent.app"

if [ ! -d "$APP" ]; then
    echo "❌ Figma Serial Agent.app не найден в $DIR"
    echo "   Скачайте его или соберите: ./build_app.sh"
    read -p "Нажмите Enter..."
    exit 1
fi

# Снимаем quarantine (macOS ставит при скачивании из интернета)
echo "🔓 Снимаем карантин macOS..."
xattr -cr "$APP" 2>/dev/null

# Запускаем
echo "🚀 Запускаем Figma Serial Agent..."
open "$APP"

echo ""
echo "✅ Готово! Иконка появится в menubar (вверху экрана)"
echo "   Это окно можно закрыть."
echo ""
