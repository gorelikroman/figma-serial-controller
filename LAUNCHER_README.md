# Serial Controller Launcher

Есть несколько способов запуска агента:

## 1. 📁 Двойной клик (самый простой)

**Файл:** `start_agent.command`

Просто дважды кликните на этот файл - откроется Terminal и запустится агент.

Можно перетащить этот файл на рабочий стол или в Dock для быстрого доступа.

---

## 2. 🍎 AppleScript приложение

**Файл:** `Start Serial Controller.scpt`

1. Откройте файл в **Script Editor** (Редактор сценариев)
2. Меню **File → Export...**
3. File Format: **Application**
4. Сохраните как `Serial Controller.app` где удобно
5. Теперь можно запускать как обычное приложение

Можно добавить свою иконку:
- Найдите нужную картинку
- Get Info (⌘I) на картинке → копируйте превью
- Get Info на .app → вставьте в иконку вверху

---

## 3. 🚀 Автозапуск (Launch Agent)

Агент будет запускаться автоматически при входе в систему и перезапускаться при падении.

### Установка:

```bash
./install_autostart.sh
launchctl load ~/Library/LaunchAgents/com.figma.serial-controller.plist
```

### Управление:

Запустить:
```bash
launchctl start com.figma.serial-controller
```

Остановить:
```bash
launchctl stop com.figma.serial-controller
```

Отключить автозапуск:
```bash
launchctl unload ~/Library/LaunchAgents/com.figma.serial-controller.plist
```

Посмотреть логи:
```bash
tail -f ~/Library/Logs/figma-serial-controller.log
```

Удалить:
```bash
launchctl unload ~/Library/LaunchAgents/com.figma.serial-controller.plist
rm ~/Library/LaunchAgents/com.figma.serial-controller.plist
```

---

## 4. 🔌 Установка плагина в Figma

Плагин — это связующее звено между агентом и Figma. Без него контроллер не будет управлять интерфейсом.

### Установка:

1. Откройте **Figma Desktop** (плагин работает только в десктопной версии)
2. Откройте любой файл
3. Меню **Plugins → Development → Import plugin from manifest…**
4. Выберите файл `plugin/manifest.json` из папки проекта:
   ```
   figma_serial_controller/plugin/manifest.json
   ```
5. Плагин **Figma Serial Controller** появится в меню **Plugins → Development**

### Запуск:

1. Убедитесь, что **агент запущен** (см. выше)
2. В Figma: **Plugins → Development → Figma Serial Controller → 🎛 Serial Controller**
3. Откроется окно плагина — оно подключится к агенту по WebSocket
4. Готово! Крутите энкодеры, нажимайте кнопки — Figma будет реагировать

### Важно:

- Плагин нужно устанавливать **один раз** — он сохраняется в Figma
- При изменении кода плагина (`code.js`) достаточно перезапустить его в Figma (⌘⇧P → "Run last plugin")
- Плагин работает только пока открыто его окно в Figma

---

## Рекомендация

Для разработки и тестирования используйте **start_agent.command** - видно все логи и легко остановить.

Для постоянной работы используйте **Launch Agent** - работает в фоне, автоматически запускается.
