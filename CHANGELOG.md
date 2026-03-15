# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project aims to follow Semantic Versioning.

## [Unreleased]

### Added
- No changes yet.

## [2.0.0] - 2026-03-16

### Added
- **Menubar app** (`tray_app.py`) — полноценное macOS-приложение в трее.
  - 🟢🟡🔴 иконка статуса в menubar.
  - Статусы Device / WebSocket / Figma Plugin прямо в меню.
  - «Open Config Editor» — открывает index.html в браузере.
  - «Reconnect Device» — переподключение Arduino.
  - Авто-переподключение при потере связи.
- `Launch Agent.command` — скрипт первого запуска, снимает macOS quarantine и запускает .app.
- Standalone `.app` (14 МБ) с упакованным Python — работает на любом Mac без установки Python.

### Changed
- `build_app.sh` — пересобирает menubar-приложение вместо headless-агента.
  - Добавлены hidden-imports: `rumps`, `objc`, `Foundation`, `AppKit`.
  - Добавлен `index.html` в бандл для config editor.
- `README.md` — реструктурирован на два варианта:
  - **Вариант 1** — Простой (без Python, .app, 3 шага).
  - **Вариант 2** — Для разработчиков (из исходников).
  - Документация (архитектура, железо, протокол, маппинг) вынесена в отдельный раздел.
  - Таблица «Устранение проблем» сжата в компактный формат.

### Fixed
- Deprecation warning `websockets.server.serve` — добавлен fallback на `websockets.asyncio.server`.

## [1.1.0] - 2026-03-15

### Added
- Git tracking setup for the project.
- Improved `.gitignore` for macOS, Python, Arduino artifacts, and editor temp files.
- GitHub release notes template at `.github/release.yml`.
- Project changelog.

## [0.1.0] - 2026-03-15

### Added
- Initial public version of the Figma Serial Controller.
- Arduino firmware (`figma_serial_controller.ino`).
- Web configuration UI (`index.html`).
- Python serial/WebSocket bridge (`agent/agent.py`).
- Figma plugin runtime (`plugin/code.js`).
- Launch scripts and setup documentation.

[Unreleased]: https://github.com/gorelikroman/figma-serial-controller/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/gorelikroman/figma-serial-controller/releases/tag/v2.0.0
[1.1.0]: https://github.com/gorelikroman/figma-serial-controller/releases/tag/v1.1.0
[0.1.0]: https://github.com/gorelikroman/figma-serial-controller/releases/tag/v0.1.0
