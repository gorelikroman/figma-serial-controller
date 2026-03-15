# 🎛 Figma Serial Controller

Аппаратный контроллер для Figma. Arduino Micro отправляет события по USB Serial,
Python-агент обрабатывает их (акселерация энкодеров, маппинг кнопок) и отправляет
в Figma-плагин по WebSocket. Все маппинги в `config.json` — без перепрошивки.

> **Статус**: в разработке. Прошивка и агент работают, плагин требует тестирования.

---

## Старт без терминала (контроллер уже прошит)

Если контроллер уже прошит, **Arduino CLI и перепрошивка не нужны**.

1. Открой репозиторий в браузере: `https://github.com/gorelikroman/figma-serial-controller`
2. Нажми **Code → Download ZIP**
3. Распакуй ZIP в удобную папку
4. Один раз на этом Mac установи **Figma Desktop** (само приложение Figma).
5. Один раз установи **Python 3**:
    1. Открой `https://www.python.org/downloads/macos/`
    2. Скачай актуальный **Python 3.x**: `macOS 64-bit universal2 installer (.pkg)`
    3. Открой скачанный `.pkg` и пройди установку (`Continue` → `Install`)
    4. После установки открой папку `Applications/Python 3.x/` и дважды кликни `Install Certificates.command`
    5. Если окно Terminal было открыто, закрой и открой его заново
    Если Python 3 уже установлен, пропусти этот шаг.
6. В распакованной папке дважды кликни `install_requirements.command`.
    Это установка библиотек проекта (`pyserial`, `websockets`) в установленный Python.
7. Дважды кликни `start_agent.command` (запустит агент через Python)
8. В Figma Desktop: **Plugins → Development → Import plugin from manifest...**
9. Выбери `figma_serial_controller/plugin/manifest.json`
10. Запусти плагин: **Plugins → Development → Figma Serial Controller → 🎛 Serial Controller**

Если macOS блокирует запуск `.command`: сделай **правый клик → Open** (или **Ctrl+Click → Open**) и подтверди запуск один раз.

Проверка: в окне плагина должен быть статус `Connected`.

---

## Содержание

- [Старт без терминала (контроллер уже прошит)](#старт-без-терминала-контроллер-уже-прошит)
- [Архитектура](#архитектура)
- [Железо](#железо)
- [Структура проекта](#структура-проекта)
- [Передать другу (быстрый пакет)](#передать-другу-быстрый-пакет)
- [Установка на новый компьютер](#установка-на-новый-компьютер)
- [Быстрый старт (ежедневный запуск)](#быстрый-старт-ежедневный-запуск)
- [Протокол Serial](#протокол-serial)
- [Маппинг](#маппинг-configjson)
- [Переназначение](#переназначение)
- [Устранение проблем](#устранение-проблем)
- [Текущий статус и TODO](#текущий-статус-и-todo)

---

## Архитектура

```
┌─────────────────────┐    USB Serial    ┌────────────────┐   WebSocket    ┌────────────────┐
│   Arduino Micro     │  ─────────────►  │  Python Agent  │  ──────────►  │  Figma Plugin  │
│   (ATmega32U4)      │   115200 baud    │   agent.py     │  ws://        │   code.js      │
│                     │   "E1:+1\n"      │   config.json  │  127.0.0.1    │                │
│  MCP23017 (I2C)     │   "M3:down\n"    │                │  :8765        │                │
│  6 энкодеров        │   "JX:tl\n"      │  + AppleScript │               │                │
│  4×4 матрица        │                  │    hotkeys     │               │                │
│  джойстик           │                  │  + акселерация │               │                │
└─────────────────────┘                  └────────────────┘               └────────────────┘
```

### Поток данных:
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
├── figma_serial_controller.ino  ← прошивка Arduino (356 строк)
├── agent/
│   ├── agent.py                 ← Python мост Serial→WebSocket (478 строк)
│   ├── config.json              ← маппинг всех элементов
│   └── requirements.txt         ← pyserial, websockets
└── plugin/
    ├── code.js                  ← Figma плагин (907 строк)
    └── manifest.json            ← манифест плагина (id: figma-serial-controller-2026)
```

---

## Передать другу (быстрый пакет)

Если нужно просто дать контроллер другу на другой Mac, удобнее всего отправить весь каталог:

```text
figma_serial_controller/
```

Минимально достаточно этого набора:

```text
figma_serial_controller/
├── install_requirements.command
├── start_agent.command
├── figma_serial_controller.ino
├── index.html
├── agent/
│   ├── agent.py
│   ├── config.json
│   └── requirements.txt
└── plugin/
    ├── code.js
    └── manifest.json
```

Быстрый способ упаковать:

```bash
cd /путь/к/QMK_arduino
zip -r figma_serial_controller_bundle.zip figma_serial_controller
```

### Другу: 5 команд для запуска

```bash
cd /путь/к/figma_serial_controller/agent
python3 -m pip install -r requirements.txt
python3 -c "import serial, websockets; print('deps OK')"
python3 agent.py
# (отдельно в Figma Desktop: Import plugin from manifest -> plugin/manifest.json)
```

Если плата ещё не прошита, добавить один раз:

```bash
arduino-cli core install arduino:avr
arduino-cli compile --fqbn arduino:avr:micro /путь/к/figma_serial_controller/
arduino-cli upload --fqbn arduino:avr:micro -p /dev/cu.usbmodemXXXXX /путь/к/figma_serial_controller/
```

---

## Установка на новый компьютер

### Шаг 1: Скопировать проект

```bash
# Весь репозиторий (если нужны и другие тесты)
git clone <repo-url>
# Или копируй только папку figma_serial_controller/
```

Минимально нужны файлы:
```
figma_serial_controller/
├── figma_serial_controller.ino
├── agent/
│   ├── agent.py
│   ├── config.json
│   └── requirements.txt
└── plugin/
    ├── code.js
    └── manifest.json
```

### Шаг 2: Установить Arduino CLI

```bash
# macOS (Homebrew)
brew install arduino-cli

# Или скачай с https://arduino.github.io/arduino-cli/latest/installation/

# Установить ядро для Arduino Micro
arduino-cli core install arduino:avr

# Проверить — подключи Arduino и:
arduino-cli board list
# Должен появиться порт вроде /dev/cu.usbmodemXXXXX
```

### Шаг 3: Скомпилировать и залить прошивку

```bash
cd /путь/к/проекту

# Компиляция
arduino-cli compile --fqbn arduino:avr:micro figma_serial_controller/

# Залить (замени порт на свой!)
arduino-cli upload --fqbn arduino:avr:micro -p /dev/cu.usbmodemXXXXX figma_serial_controller/
```

> **Примечание**: Arduino Micro имеет CDC (виртуальный COM порт). Порт может поменяться после заливки. Просто заново сделай `arduino-cli board list`.

### Шаг 4: Установить Python и зависимости

```bash
# macOS — Python 3 обычно уже есть, или через Homebrew:
brew install python3

# Установить зависимости
cd figma_serial_controller/agent
pip3 install -r requirements.txt

# Проверить что установилось:
python3 -c "import serial; import websockets; print('OK')"
```

> **Важно**: если у тебя несколько версий Python, убедись что pyserial и websockets установлены в ту, которую используешь:
> ```bash
> /usr/local/bin/python3 -m pip install -r requirements.txt
> # или
> python3 -m pip install --break-system-packages pyserial websockets
> ```

### Шаг 5: Импортировать Figma плагин

1. Открой **Figma Desktop** (не браузер!)
2. В любом файле: **Plugins** → **Development** → **Import plugin from manifest...**
3. Выбери файл: `.../figma_serial_controller/plugin/manifest.json`
4. Плагин появится в **Plugins** → **Development** → **Figma Serial Controller**

> ⚠️ **ВАЖНО**: ID плагина = `figma-serial-controller-2026`. Если у тебя уже был старый плагин "Auto Layout Helper" с другим code.js — удали его из Development, чтобы не было конфликта.

### Шаг 6: Проверить что всё работает

```bash
# Терминал 1 — проверить Serial от Arduino
cd figma_serial_controller/agent
python3 -c "
import serial, serial.tools.list_ports, time
ports = [p for p in serial.tools.list_ports.comports() if 'usbmodem' in p.device]
print('Ports:', [p.device for p in ports])
if ports:
    s = serial.Serial(ports[0].device, 115200, timeout=0.5)
    print('Connected! Покрути энкодер...')
    for _ in range(40):
        line = s.readline().decode('utf-8', errors='replace').strip()
        if line: print(f'  > {line}')
    s.close()
"
```

---

## Быстрый старт (ежедневный запуск)

Каждый раз когда садишься работать:

```bash
# 1. Запустить агент (он сам найдёт Arduino)
cd figma_serial_controller/agent
python3 agent.py

# Увидишь:
#   ═══ Figma Serial Controller Agent ═══
#   WebSocket: ws://127.0.0.1:8765
#   Connected to /dev/cu.usbmodemXXXXX
#   WebSocket server started

# 2. В Figma открыть плагин:
#    Plugins → Development → Figma Serial Controller → 🎛 Serial Controller
#    В окне плагина увидишь "Connected ✓"

# 3. Готово! Выдели элемент в Figma и крути энкодеры
```

### Остановить
- `Ctrl+C` в терминале агента

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

Редактируй `agent/config.json` и перезапускай агент (`Ctrl+C` → `python3 agent.py`). **Перепрошивка Arduino не нужна!**

### Поменять действие энкодера:
```json
"E4": { "action": "cornerRadius", "step": 1, "accelerate": true }
```

### Поменять кнопку матрицы на hotkey:
```json
"M16": { "type": "hotkey", "keys": ["command", "z"] }
```

### Поменять кнопку на команду плагина:
```json
"M16": { "type": "plugin", "command": "toggleDirection" }
```

### Сделать кнопку матрицы hold-слоем:
```json
"M13": { "type": "layer_hold", "layer": "encoder_alt" }
```

### Переопределить энкодер только внутри слоя:
```json
"layers": {
    "encoder_alt": {
        "encoders": {
            "E6": { "action": "cornerRadius", "step": 1, "accelerate": true }
        }
    }
}
```

### Отключить кнопку:
```json
"M16": { "type": "none" }
```

### Доступные actions для энкодеров:
`gap`, `paddingX`, `paddingY`, `width`, `height`, `fontSize`, `opacity`, `cornerRadius`, `strokeWidth`

### Доступные команды для кнопок (type: "plugin"):
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

### Доступные модификаторы для hotkey:
`ctrl` / `control`, `option` / `alt`, `command` / `cmd`, `shift` + любая клавиша

### Типы кнопок (`buttons.Mx.type`):
`plugin`, `hotkey`, `layer_hold`, `none`

---

## Устранение проблем

### Arduino не найден
```bash
# Проверить подключение
arduino-cli board list

# Если порт не виден — переподключи USB кабель
# Arduino Micro иногда меняет порт после заливки
```

### Serial порт занят (screen/minicom)
```bash
# Найти процесс, который держит порт
lsof /dev/cu.usbmodem*

# Убить его
kill -9 <PID>
```

### Агент не находит Arduino
- Убедись что нет другого процесса на Serial (screen, Arduino IDE Monitor)
- Агент ищет порты по паттерну `cu.usbmodem` — если твой порт другой, поменяй в `config.json`:
  ```json
  "serial": { "port_patterns": ["cu.usbmodem", "ttyACM"] }
  ```

### Плагин показывает "Connecting..." но не подключается
- Убедись что агент запущен (`python3 agent.py`)
- В консоли агента должно быть `WebSocket server started`
- Figma должна быть десктопная (не браузер) — WebSocket к localhost работает только в десктопе

### Плагин получает команды, но ничего не происходит
- Выдели элемент в Figma перед использованием
- Энкодеры gap/padding работают только с Auto Layout фреймами
- Width/Height работают с любыми элементами
- Font Size работает только с текстовыми слоями

### Все энкодеры меняют одно и то же свойство
- **Убедись что ID плагина = `figma-serial-controller-2026`** (проверь `plugin/manifest.json`)
- Удали старый плагин из Figma (Plugins → Development → правый клик → Remove)
- Заново импортируй: Plugins → Development → Import plugin from manifest

### Конфликт плагинов
Если у тебя был старый плагин "Auto Layout Helper" — он мог иметь тот же ID. Нужно:
1. Удалить старый плагин из Figma Development
2. Импортировать новый manifest.json (с id `figma-serial-controller-2026`)

### macOS Accessibility (для hotkey кнопок)
Hotkeys через AppleScript требуют разрешения:
1. System Settings → Privacy & Security → Accessibility
2. Добавь Terminal.app (или iTerm) в список

---

## Текущий статус и TODO

### ✅ Готово
- [x] Прошивка Arduino — компилируется, работает (31% Flash, 20% RAM)
- [x] Serial протокол — проверен, события приходят корректно
- [x] Python агент — подключается к Serial и запускает WebSocket сервер
- [x] Акселерация энкодеров — работает (×1/×2/×4/×6)
- [x] Батчинг — ~30fps, объединяет тики энкодеров
- [x] Config.json — 43 элемента замаплены
- [x] Figma плагин — WebSocket UI + все команды
- [x] Auto Layout Helper функции — все сохранены

### ⏳ В процессе / TODO
- [ ] End-to-end тест (энкодер → агент → WebSocket → плагин → изменение в Figma)
- [ ] Проверить все кнопки матрицы
- [ ] Проверить джойстик → alignment
- [ ] Тест hotkey кнопок (M9, M10, M12)
- [ ] Визуальный фидбек в плагине (показывать текущие значения)
- [ ] Hot-reload config.json без перезапуска агента (кнопка в плагине)
- [ ] Поддержка второго MCP23017 (0x21) для расширения
- [ ] Обдумать Windows/Linux совместимость (сейчас AppleScript = macOS only)

---

## Зависимости и версии

| Компонент | Версия / Требования |
|-----------|-------------------|
| Arduino Micro | ATmega32U4 (arduino:avr:micro) |
| arduino-cli | любая актуальная |
| Arduino core | arduino:avr |
| Wire.h | встроена в core |
| Python | 3.9+ (тестировалось на 3.14) |
| pyserial | ≥ 3.5 |
| websockets | ≥ 12.0 |
| Figma | Desktop app (не браузер!) |
| macOS | для AppleScript hotkeys |

---

## Лицензия

Внутренний проект. Свободное использование.
