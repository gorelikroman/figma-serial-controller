#!/bin/bash
# ═══════════════════════════════════════════════════
# Сборка standalone macOS .app
# Результат работает на любом Mac БЕЗ установки Python
# ═══════════════════════════════════════════════════
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_DIR="$SCRIPT_DIR/agent"
APP_NAME="Figma Serial Agent"
BUNDLE_ID="com.figma.serial-agent"

echo ""
echo "═══════════════════════════════════════"
echo "  📦 Building: $APP_NAME.app"
echo "═══════════════════════════════════════"
echo ""

# 1. Зависимости для сборки
echo "1/4  Installing build dependencies..."
pip3 install --quiet pyinstaller pyserial websockets

# 2. Сборка через PyInstaller
echo "2/4  Compiling standalone binary..."
cd "$AGENT_DIR"

# Удаляем старые артефакты
rm -rf build dist *.spec

pyinstaller \
  --noconfirm \
  --onedir \
  --windowed \
  --name "$APP_NAME" \
  --osx-bundle-identifier "$BUNDLE_ID" \
  --add-data "config.json:." \
  --hidden-import websockets \
  --hidden-import websockets.server \
  --hidden-import websockets.legacy \
  --hidden-import websockets.legacy.server \
  --hidden-import serial \
  --hidden-import serial.tools \
  --hidden-import serial.tools.list_ports \
  --hidden-import json \
  --hidden-import asyncio \
  agent.py

APP_PATH="$AGENT_DIR/dist/$APP_NAME.app"

# Скрываем иконку из Dock — агент работает как фоновый сервис
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$APP_PATH/Contents/Info.plist" 2>/dev/null || \
/usr/libexec/PlistBuddy -c "Set :LSUIElement true" "$APP_PATH/Contents/Info.plist"

# 3. Встраиваем config.json внутрь .app
echo "3/4  Embedding config..."
RESOURCES="$APP_PATH/Contents/Resources"
cp "$AGENT_DIR/config.json" "$RESOURCES/"

# 4. Подписываем ad hoc
echo "4/4  Code signing (ad hoc)..."
codesign --force --deep --sign - "$APP_PATH"

# Копируем в корень проекта
cp -R "$APP_PATH" "$SCRIPT_DIR/"

# Чистим артефакты сборки
rm -rf "$AGENT_DIR/build" "$AGENT_DIR/dist" "$AGENT_DIR"/*.spec

echo ""
echo "═══════════════════════════════════════"
echo "  ✅ Ready: $SCRIPT_DIR/$APP_NAME.app"
echo "═══════════════════════════════════════"
echo ""
echo "  На новом Mac:"
echo "  1. Скопируйте '$APP_NAME.app' на компьютер"
echo "  2. Правый клик → Открыть → Открыть"
echo "     (только первый раз, потом macOS запомнит)"
echo "  3. Готово!"
echo ""
