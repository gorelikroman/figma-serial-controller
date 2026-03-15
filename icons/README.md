# Icons Guide

## Structure
- `commands/` - SVG иконки для команд плагина (inline в index.html)

## Naming Convention
Имя файла = имя команды:
- `openGapInput.svg`
- `toggleDirection.svg`
- `alignCenter.svg`
- etc.

## Export Settings (Figma)
1. Size: 24×24px
2. Format: SVG
3. Settings:
   - ☑ Include 'id' attribute
   - ☑ Outline text
   - ☑ Simplify stroke

## Integration
После экспорта SVG из Figma:
1. Откройте файл в текстовом редакторе
2. Скопируйте содержимое `<svg>...</svg>`
3. Добавьте в объект `COMMAND_ICONS` в index.html
4. Убедитесь что `fill="currentColor"` для автоматической перекраски через CSS

## Example
```javascript
const COMMAND_ICONS = {
  openGapInput: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="..." fill="currentColor"/></svg>',
  // ...
};
```
