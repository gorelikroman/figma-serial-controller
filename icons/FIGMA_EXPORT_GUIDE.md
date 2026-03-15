# 🎨 Как экспортировать иконки из Figma

## Шаг 1: Подготовка иконки в Figma

1. **Размер**: Создайте frame 24×24px
2. **Иконка внутри**: Нарисуйте иконку, используя:
   - Vector/Shape layers (не Text, не Images)
   - Mono-color дизайн (один цвет)
   - Stroke или Fill — не важно
3. **Именование**: Назовите frame по имени команды, например:
   - `openGapInput`
   - `toggleDirection`
   - `alignCenter`

## Шаг 2: Настройка цвета для CSS

**ВАЖНО**: Чтобы иконка перекрашивалась через CSS:

### Вариант А (рекомендуется):
1. Выделите все векторные объекты внутри иконки
2. В панели Fill выберите `#FFFFFF` (белый) или любой цвет
3. Это будет заменено на `currentColor` в SVG

### Вариант Б:
После экспорта вручную замените все `fill="#какой-то-цвет"` на `fill="currentColor"` в коде SVG

## Шаг 3: Экспорт

1. Выделите frame с иконкой
2. В правой панели найдите **Export**
3. Нажмите **+ (плюс)**
4. Настройки экспорта:
   ```
   Format: SVG
   ☑ Include "id" attribute
   ☑ Outline text (если есть текст)
   ☐ Simplify stroke (обычно не нужно)
   ```
5. Нажмите **Export [название]**

## Шаг 4: Извлечение SVG кода

1. Откройте экспортированный файл `.svg` в **текстовом редакторе** (VS Code, Sublime, etc.)
2. Скопируйте весь код от `<svg` до `</svg>` включительно
3. Пример того, что вы должны увидеть:
   ```xml
   <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
     <rect x="4" y="8" width="6" height="8" fill="#FFFFFF"/>
     <rect x="14" y="8" width="6" height="8" fill="#FFFFFF"/>
     <path d="M11 10v4..." stroke="#FFFFFF" stroke-width="1.5"/>
   </svg>
   ```

## Шаг 5: Подготовка для вставки в код

### Обязательные изменения:

1. **Замените цвета на `currentColor`**:
   ```xml
   <!-- Было: -->
   fill="#FFFFFF"
   stroke="#FFFFFF"
   
   <!-- Стало: -->
   fill="currentColor"
   stroke="currentColor"
   ```

2. **Удалите xmlns** (не обязательно, но чище):
   ```xml
   <!-- Было: -->
   <svg ... xmlns="http://www.w3.org/2000/svg">
   
   <!-- Стало: -->
   <svg ...>
   ```

3. **Минимизируйте** (опционально):
   - Уберите лишние пробелы
   - Все на одной строке

### Финальный пример:
```xml
<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><rect x="4" y="8" width="6" height="8" fill="currentColor"/><rect x="14" y="8" width="6" height="8" fill="currentColor"/></svg>
```

## Шаг 6: Вставка в index.html

1. Откройте `figma_serial_controller/index.html`
2. Найдите объект `COMMAND_ICONS` (около строки 432)
3. Замените placeholder код:
   ```javascript
   const COMMAND_ICONS = {
     openGapInput: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><rect x="4" y="8" width="6" height="8" fill="currentColor"/>...</svg>',
     // ... остальные иконки
   };
   ```

## Быстрый чеклист ✅

- [ ] Иконка 24×24px
- [ ] Mono-color (один цвет)
- [ ] Экспортировано как SVG
- [ ] Заменил все цвета на `currentColor`
- [ ] Удалил `xmlns` (опционально)
- [ ] Вставил в `COMMAND_ICONS`
- [ ] Обновил страницу в браузере (Cmd+R)

## Troubleshooting

**Иконка не видна:**
- Проверьте `viewBox="0 0 24 24"`
- Убедитесь что есть `fill="currentColor"` или `stroke="currentColor"`

**Иконка не меняет цвет:**
- Замените все `fill="#цвет"` на `fill="currentColor"`

**Иконка слишком большая/маленькая:**
- Настройте размер в CSS классах `.cmd-icon` (48×48px) или `.enc-icon` (20×20px)

## Пример полного workflow:

1. Figma: создал `alignCenter` icon 24×24px
2. Export → SVG
3. Открыл в VS Code → скопировал код
4. Заменил `fill="#000000"` на `fill="currentColor"`
5. Вставил в `COMMAND_ICONS`:
   ```javascript
   alignCenter: '<svg viewBox="0 0 24 24" fill="none"><rect x="9.5" y="9.5" width="5" height="5" fill="currentColor"/><rect x="5" y="5" width="14" height="14" stroke="currentColor" stroke-width="1" fill="none"/></svg>'
   ```
6. Сохранил → обновил браузер → готово! 🎉
