# Figma Serial Controller — Setup Guide

## 📋 Что нужно

- macOS 12+
- Arduino Micro подключён по USB
- Figma Desktop

---

## 🚀 Быстрый старт (новый компьютер, без Python)

### Шаг 1: Запустите агент

Откройте **Figma Serial Agent.app**

> ⚠️ **Первый запуск:** macOS покажет предупреждение.
> Нажмите **правой кнопкой** → **Открыть** → **Открыть**.
> Нужно сделать только один раз — macOS запомнит.

Агент запустится и будет слушать контроллер через USB.

### Шаг 2: Установите плагин в Figma

1. Откройте **Figma Desktop**
2. Откройте любой файл
3. **Plugins → Development → Import plugin from manifest…**
4. Выберите `plugin/manifest.json` из папки проекта
5. Плагин появится в **Plugins → Development**

### Шаг 3: Запустите плагин

1. В Figma: **Plugins → Development → Figma Serial Controller → 🎛 Serial Controller**
2. Окно плагина подключится к агенту
3. Готово! Крутите энкодеры, нажимайте кнопки 🎛

> Плагин устанавливается **один раз** и сохраняется в Figma.
> Перезапуск: **⌘⇧P** → *Run last plugin*

---

## 🔧 Для разработчиков

### Запуск из исходников (нужен Python 3)

```bash
# Установить зависимости (один раз)
pip3 install pyserial websockets

# Запустить агент
cd agent && python3 agent.py
```

Или двойной клик на `start_agent.command`
(если macOS блокирует: `chmod +x start_agent.command`)

### Сборка standalone .app

```bash
./build_app.sh
```

Результат — `Figma Serial Agent.app` (~12 МБ). Копируйте на любой Mac, Python не нужен.

### Автозапуск при входе в систему

```bash
./install_autostart.sh
launchctl load ~/Library/LaunchAgents/com.figma.serial-controller.plist
```

---

## ❓ Проблемы

| Проблема | Решение |
|----------|---------|
| «Не удаётся проверить разработчика» | Правый клик → **Открыть** → **Открыть** (один раз) |
| «Apple could not verify» у `.command` | `xattr -dr com.apple.quarantine .` в папке проекта |
| «Нет прав доступа» | `chmod +x *.command *.sh` |
| Агент не видит контроллер | Переподключите USB, проверьте прошивку Arduino |
| Плагин не подключается | Убедитесь что агент запущен, порт 8765 свободен |
