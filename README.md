# 🎛 Figma Serial Controller

Аппаратный контроллер для Figma. Arduino Micro отправляет события по USB Serial,
агент обрабатывает их (акселерация энкодеров, маппинг кнопок) и передаёт
в Figma-плагин по WebSocket. Все маппинги в `config.json` — без перепрошивки.

---

## Содержание

**Установка:**
- [Вариант 1 — Рекомендуемый (Python + start_agent.command)](#вариант-1--рекомендуемый-python--start_agentcommand)
- [Вариант 2 — Простой (без Python, .app)](#вариант-2--простой-без-python-app)
- [Вариант 3 — Для разработчиков (из исходников)](#вариант-3--для-разработчиков-из-исходников)

**Документация:**
- [Архитектура](#архитектура)
- [Железо](#железо)
- [Протокол Serial](#протокол-serial)
- [Маппинг (config.json)](#маппинг-configjson)
- [Переназначение](#переназначение)
- [Устранение проблем](#устранение-проблем)
- [Текущий статус и TODO](#текущий-статус-и-todo)

---

# Вариант 1 — Рекомендуемый (Python + start_agent.command)

> Лучший вариант для установки с GitHub. Контроллер уже прошит, перепрошивка не нужна.

### Что нужно

- macOS 12+
- Arduino Micro подключён по USB
- Figma Desktop
- Python 3 (скачать: [python.org for macOS](https://www.python.org/downloads/macos/))

> VS Code и Copilot для использования контроллера не обязательны.

### Шаг 1: Скачать проект

Открой [gorelikroman/figma-serial-controller](https://github.com/gorelikroman/figma-serial-controller)
→ **Code → Download ZIP** → распакуй.

### Шаг 2: Установить Python

1. Открой [python.org for macOS](https://www.python.org/downloads/macos/)
2. Скачай **Python 3.x macOS 64-bit universal2 installer (.pkg)**
3. Установи `.pkg` (обычный мастер установки)
4. Если Python уже установлен, этот шаг пропусти

### Шаг 3: Установить зависимости агента

Двойной клик по `install_requirements.command` в корне проекта.

Если macOS блокирует запуск `.command`:
- правый клик по файлу → **Open** → подтвердить запуск

### Шаг 4: Запустить агент

Двойной клик по `start_agent.command`.

### Шаг 5: Установить и запустить плагин

1. В **Figma Desktop** открой любой файл
2. **Plugins → Development → Import plugin from manifest…**
3. Выбери `plugin/manifest.json` из папки проекта
4. Запусти: **Plugins → Development → Figma Serial Controller → 🎛 Serial Controller**
5. В окне плагина должен быть статус **Connected ✓**

### Что может запросить служба безопасности

- Доступ к USB serial-устройству (`/dev/cu.usbmodem*`)
- Локальный WebSocket на loopback (`ws://127.0.0.1:8765`)
- macOS permissions для Terminal/iTerm:
    - **Privacy & Security → Accessibility**
    - **Privacy & Security → Automation** (Terminal/iTerm → Figma)

---

# Вариант 2 — Простой (без Python, .app)

> Если у вас есть готовый standalone `.app`, Python ставить не нужно.

1. Открой **Figma Serial Agent.app**
2. В Figma импортируй `plugin/manifest.json`
3. Запусти **Plugins → Development → Figma Serial Controller → 🎛 Serial Controller**

Если macOS блокирует `.app`: правый клик → **Open** → подтвердить запуск.

---

# Вариант 3 — Для разработчиков (из исходников)

> Нужен Python 3 и терминал. Подходит для разработки, отладки и перепрошивки Arduino.

### 3.1 Клонировать проект

```bash
git clone https://github.com/gorelikroman/figma-serial-controller.git
cd figma-serial-controller
```

### 3.2 Установить Python-зависимости

```bash
pip3 install pyserial websockets rumps
# Проверить:
python3 -c "import serial, websockets, rumps; print('OK')"
```

> Если несколько версий Python: `python3 -m pip install pyserial websockets rumps`

### 3.3 Запустить агент

**Menubar-приложение (рекомендуется):**
```bash
cd agent && python3 tray_app.py
```

**Headless-режим (без menubar, для серверов/CI):**
```bash
cd agent && python3 agent.py
```

Или двойной клик на `start_agent.command`
(если macOS блокирует: `chmod +x start_agent.command`)

### 3.4 Установить плагин в Figma

1. **Figma Desktop** → любой файл
2. **Plugins → Development → Import plugin from manifest…**
3. Выбрать `plugin/manifest.json`
4. Запустить: **Plugins → Development → Figma Serial Controller → 🎛 Serial Controller**

### 3.5 Прошивка Arduino (если нужно)

```bash
# Установить Arduino CLI
brew install arduino-cli
arduino-cli core install arduino:avr

# Компиляция
arduino-cli compile --fqbn arduino:avr:micro figma_serial_controller/

# Залить (замени порт на свой!)
arduino-cli board list
arduino-cli upload --fqbn arduino:avr:micro -p /dev/cu.usbmodemXXXXX figma_serial_controller/
```

> Arduino Micro имеет виртуальный COM порт — он может поменяться после заливки.
> Просто заново сделай `arduino-cli board list`.

### 3.6 Сборка standalone .app

```bash
./build_app.sh
```

Результат — `Figma Serial Agent.app` (~14 МБ) с menubar-иконкой. Копируйте на любой Mac, Python не нужен.

### 3.7 Автозапуск при входе в систему

```bash
./install_autostart.sh
launchctl load ~/Library/LaunchAgents/com.figma.serial-controller.plist
```

### 3.8 Ежедневный запуск

```bash
cd agent && python3 tray_app.py
# Или: open "Figma Serial Agent.app"
# В Figma: ⌘⇧P → Run last plugin
# Остановить: клик по иконке в menubar → Quit
```

---

# Документация

## Архитектура

```
┌─────────────────────┐    USB Serial    ┌────────────────┐   WebSocket    ┌────────────────┐
│   Arduino Micro     │  ─────────────►  │  Menubar App   │  ──────────►  │  Figma Plugin  │
│   (ATmega32U4)      │   115200 baud    │  tray_app.py   │  ws://        │   code.js      │
│                     │   "E1:+1\n"      │   config.json  │  127.0.0.1    │                │
│  MCP23017 (I2C)     │   "M3:down\n"    │                │  :8765        │                │
│  6 энкодеров        │   "JX:tl\n"      │  + AppleScript │               │                │
│  4×4 матрица        │                  │    hotkeys     │               │                │
│  джойстик           │                  │  + акселерация │               │                │
└─────────────────────┘                  └────────────────┘               └────────────────┘
```

### Поток данных
1. **Arduino** считывает энкодеры/кнопки/джойстик → отправляет текстовые события по Serial
2. **Agent** читает Serial, применяет акселерацию к энкодерам, ищет маппинг в config.json
3. **Энкодеры** → WebSocket → Plugin (плавное изменение свойств, ~30fps батчинг)
4. **Кнопки** → либо WebSocket команда плагину, либо AppleScript hotkey (macOS)
5. **Plugin** получает JSON сообщения и меняет свойства выделенных элементов в Figma

---

## Железо

### Микроконтроллер
- **Arduino Micro** (ATmega32U4, USB-native)
- Чистый Serial — никакого HID клавиатуры

### I/O расширитель
- **MCP23017** по I2C (адрес `0x20`)
- SDA = **D2**, SCL = **D3** (фиксированные на ATmega32U4, нельзя менять!)
- Все 16 пинов (Port A + Port B) настроены как INPUT_PULLUP

### Энкодеры (6 штук, rotary encoders с кнопкой)
| # | CLK | DT | SW | Подключение |
|---|-----|----|----|-------------|
| E1 | MCP A0 | MCP A1 | MCP A2 | MCP23017 |
| E2 | MCP A3 | MCP A4 | MCP A5 | MCP23017 |
| E3 | MCP A6 | MCP A7 | MCP B0 | MCP23017 |
| E4 | MCP B1 | MCP B2 | MCP B3 | MCP23017 |
| E5 | MCP B4 | MCP B5 | MCP B6 | MCP23017 |
| E6 | **MCU D4** | **MCU D5** | MCP B7 | MCU + MCP |

> E6 подключён к MCU напрямую (CLK/DT) потому что на MCP23017 не хватило пинов (16 пинов = 5×3 + 1sw = 16).

### Джойстик (аналоговый, 2 оси + кнопка)
| Сигнал | Пин Arduino |
|--------|-------------|
| VRX | **A3** |
| VRY | **A2** |
| SW  | **A1** |
| VCC | 5V |
| GND | GND |

### Кнопочная матрица 4×4
| | Col 0 (D6) | Col 1 (D7) | Col 2 (D8) | Col 3 (D9) |
|---|---|---|---|---|
| Row 0 (D15) | M1 | M2 | M3 | M4 |
| Row 1 (D14) | M5 | M6 | M7 | M8 |
| Row 2 (D16) | M9 | M10 | M11 | M12 |
| Row 3 (D10) | M13 | M14 | M15 | M16 |

### Подключение MCP23017
| Пин MCP | Куда |
|---------|------|
| VDD (pin 9) | 5V |
| VSS (pin 10) | GND |
| SDA (pin 13) | Arduino D2 |
| SCL (pin 12) | Arduino D3 |
| A0, A1, A2 (pins 15-17) | все на GND → адрес 0x20 |
| RESET (pin 18) | 5V (через резистор 10kΩ или напрямую) |

> **Обязательно**: конденсатор 0.1µF (104) между VDD и GND рядом с чипом!
> **Pull-up резисторы**: 4.7kΩ на SDA и SCL к 5V (если длина I2C > 10 см)

---

## Структура проекта

```
figma_serial_controller/
├── README.md                    ← этот файл
├── CHANGELOG.md                 ← история версий
├── LAUNCHER_README.md           ← краткий гайд по запуску
├── figma_serial_controller.ino  ← прошивка Arduino
├── build_app.sh                 ← сборка standalone .app
├── Launch Agent.command         ← первый запуск (снимает карантин)
├── start_agent.command          ← запуск агента двойным кликом
├── install_autostart.sh         ← автозапуск при входе в систему
├── index.html                   ← визуальный редактор конфига
├── agent/
│   ├── tray_app.py              ← menubar-приложение (основной)
│   ├── agent.py                 ← headless-агент (без menubar)
│   ├── config.json              ← маппинг всех элементов
│   └── requirements.txt         ← pyserial, websockets
└── plugin/
    ├── code.js                  ← Figma плагин
    └── manifest.json            ← манифест (id: figma-serial-controller-2026)
```

---

## Протокол Serial

Прошивка отправляет текстовые строки с `\n` на скорости **115200 baud**:

| Событие | Формат | Пример |
|---------|--------|--------|
| Энкодер CW | `E{n}:+1` | `E1:+1` |
| Энкодер CCW | `E{n}:-1` | `E3:-1` |
| Кнопка энкодера | `E{n}:sw` | `E2:sw` |
| Джойстик направление | `JX:{dir}` | `JX:tl` (Top-Left) |
| Кнопка джойстика | `JX:sw` | `JX:sw` |
| Матрица нажатие | `M{n}:down` | `M5:down` |
| Матрица отпускание | `M{n}:up` | `M5:up` |
| Инициализация | `READY` | Один раз при старте |
| Статус MCP | `MCP:OK` / `MCP:FAIL` | |
| Статус джойстика | `JOY:OK` / `JOY:FAIL` | |

Направления джойстика (9 зон): `tl` `tc` `tr` `cl` `cr` `bl` `bc` `br` + `sw` (кнопка)

---

## Маппинг (config.json)

### Энкодеры → WebSocket → Plugin (плавно, с акселерацией)

Агент считает скорость вращения и умножает шаг:
- < 4 тиков/сек → ×1
- 4-8 тиков/сек → ×2
- 8-14 тиков/сек → ×4
- > 14 тиков/сек → ×6

| Энкодер | Действие | Базовый шаг | При быстром вращении |
|---------|----------|-------------|---------------------|
| E1 | Gap (itemSpacing) | ±1 | ±6 |
| E2 | Padding Horizontal | ±1 | ±6 |
| E3 | Padding Vertical | ±1 | ±6 |
| E4 | Width | ±2 | ±12 |
| E5 | Height | ±2 | ±12 |
| E6 | Font Size | ±2 | ±12 |

### Кнопки энкодеров → открывают диалог ввода точного значения
| Кнопка | Действие |
|--------|----------|
| E1 sw | Open Gap input |
| E2 sw | Open Padding H input |
| E3 sw | Open Padding V input |
| E4 sw | Open Width input |
| E5 sw | Open Height input |
| E6 sw | Open Font Size input |

### Джойстик → Auto Layout Alignment
```
   ↖ tl    ⬆ tc    ↗ tr
   ⬅ cl    🔘 sw    ➡ cr
   ↙ bl    ⬇ bc    ↘ br
```

### Матрица 4×4 → Команды/Хоткеи
| Кнопка | Действие | Тип |
|--------|----------|-----|
| M1 | Set Padding All (диалог) | plugin |
| M2 | Auto Gap (SPACE_BETWEEN) | plugin |
| M3 | Toggle Auto Layout Direction | plugin |
| M4 | Wrap in Auto Layout | plugin |
| M5 | Hug Width | plugin |
| M6 | Fill Width | plugin |
| M7 | Hug Height | plugin |
| M8 | Fill Height | plugin |
| M9 | ⌥⌘B (Detach Instance) | hotkey |
| M10 | ⌥⌘K (Create Component) | hotkey |
| M11 | Create Multiple Components | plugin |
| M12 | ⌃⌥⌘K (Create Component Set) | hotkey |
| M13 | Hold Layer `encoder_alt` (пока зажата) | layer_hold |
| M14 | Align Left Text | plugin |
| M15 | Align Center Text | plugin |
| M16 | Split Text Lines | plugin |

### Hold-слой (пока держишь кнопку)
- При `M13:down` активируется слой `encoder_alt`.
- Пока слой активен, `E6` переключается с `fontSize` на `cornerRadius`.
- При `M13:up` слой отключается, и `E6` снова меняет `fontSize`.

---

## Переназначение

Редактируй `agent/config.json` и перезапускай агент (`Ctrl+C` → `python3 tray_app.py`). **Перепрошивка Arduino не нужна!**

Или: menubar → ⚙️ Open Config Editor — визуальный редактор в браузере.

### Поменять действие энкодера
```json
"E4": { "action": "cornerRadius", "step": 1, "accelerate": true }
```

### Поменять кнопку матрицы на hotkey
```json
"M16": { "type": "hotkey", "keys": ["command", "z"] }
```

### Поменять кнопку на команду плагина
```json
"M16": { "type": "plugin", "command": "toggleDirection" }
```

### Сделать кнопку матрицы hold-слоем
```json
"M13": { "type": "layer_hold", "layer": "encoder_alt" }
```

### Переопределить энкодер только внутри слоя
```json
"layers": {
    "encoder_alt": {
        "encoders": {
            "E6": { "action": "cornerRadius", "step": 1, "accelerate": true }
        }
    }
}
```

### Отключить кнопку
```json
"M16": { "type": "none" }
```

### Доступные actions для энкодеров
`gap`, `paddingX`, `paddingY`, `width`, `height`, `fontSize`, `opacity`, `cornerRadius`, `strokeWidth`

### Доступные команды для кнопок (type: "plugin")
| Команда | Описание |
|---------|----------|
| `toggleDirection` | Переключить H↔V |
| `hugContentWidth` / `hugContentHeight` | Hug по оси |
| `fillContentWidth` / `fillContentHeight` | Fill по оси |
| `fixedWidth` / `fixedHeight` | Fixed по оси |
| `gapAuto` | Gap = Auto (SPACE_BETWEEN) |
| `wrapEachInAutoLayout` | Обернуть каждый в Auto Layout |
| `alignTopLeft`...`alignBottomRight` | 9 вариантов alignment |
| `alignHorizontalCenter` / `alignVerticalCenter` | Выровнять по оси |
| `createMultipleComponents` | Сделать компоненты из выделения |
| `createComponentSet` | Объединить компоненты в набор |
| `splitTextLines` | Разбить текст по строкам |
| `alignCenterText` / `alignLeftText` | Выравнивание текста |
| `toggleTextResizing` | Авторазмер текста |
| `openPadXInput`...`openFontSizeInput` | Диалоги ввода значений |

### Доступные модификаторы для hotkey
`ctrl` / `control`, `option` / `alt`, `command` / `cmd`, `shift` + любая клавиша

### Типы кнопок (`buttons.Mx.type`)
`plugin`, `hotkey`, `layer_hold`, `none`

---

## Устранение проблем

| Проблема | Решение |
|----------|---------|
| «Не удаётся проверить разработчика» | Правый клик → **Открыть** → **Открыть** (один раз) |
| «Apple could not verify» у `.command` | `xattr -dr com.apple.quarantine .` в папке проекта |
| «Нет прав доступа» | `chmod +x *.command *.sh` |
| Arduino не найден | Переподключи USB, проверь `arduino-cli board list` |
| Serial порт занят | `lsof /dev/cu.usbmodem*` → `kill -9 <PID>` |
| Агент не видит Arduino | Нет ли `screen`/Arduino IDE Monitor? Проверь `config.json` → `port_patterns` |
| Плагин «Connecting…» | Убедись что агент запущен, порт 8765 свободен |
| Плагин не реагирует | Выдели элемент в Figma. Gap/padding — только Auto Layout фреймы |
| Энкодеры меняют одно свойство | Удали старый плагин, импортируй `manifest.json` заново |
| Hotkey не работают | System Settings → Privacy → Accessibility → добавь Terminal.app |

---

## Текущий статус и TODO

### ✅ Готово
- [x] Прошивка Arduino — компилируется, работает (31% Flash, 20% RAM)
- [x] Serial протокол — проверен, события приходят корректно
- [x] Python агент — Serial → WebSocket мост
- [x] Акселерация энкодеров — ×1/×2/×4/×6
- [x] Батчинг — ~30fps, объединяет тики энкодеров
- [x] Config.json — 43 элемента замаплены
- [x] Figma плагин — WebSocket UI + все команды
- [x] Standalone .app — menubar с статусами, работает без Python
- [x] Config editor — визуальный редактор маппинга

### ⏳ TODO
- [ ] End-to-end тест всей цепочки
- [ ] Проверить все кнопки матрицы
- [ ] Проверить джойстик → alignment
- [ ] Тест hotkey кнопок (M9, M10, M12)
- [ ] Визуальный фидбек в плагине
- [ ] Hot-reload config.json без перезапуска
- [ ] Поддержка второго MCP23017 (0x21)
- [ ] Windows/Linux совместимость

---

## Зависимости

| Компонент | Версия |
|-----------|--------|
| Arduino Micro | ATmega32U4 (arduino:avr:micro) |
| Python | 3.9+ |
| pyserial | ≥ 3.5 |
| websockets | ≥ 12.0 |
| rumps | ≥ 0.4.0 |
| Figma | Desktop app (не браузер!) |
| macOS | 12+ (для AppleScript hotkeys) |

---

## Лицензия

Внутренний проект. Свободное использование.
