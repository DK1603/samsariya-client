# Client Bot Availability System

## Overview

The client bot now fully supports the admin-controlled availability system. When an admin enables/disables items (samsa types or packaging) in the admin bot, the changes are automatically reflected in the client bot within 30 seconds.

## How It Works

### 1. MongoDB Structure

The availability is stored in a single document with ID `"availability"` in the `availability` collection:

```json
{
  "_id": "availability",
  "картошка": true,
  "тыква": true,
  "зелень": false,
  "мясо": true,
  "курица_с_сыром": true,
  "пакет": true,
  "коробка": true,
  "items": {
    "картошка": true,
    "тыква": true,
    "зелень": false,
    "мясо": true,
    "курица_с_сыром": true,
    "пакет": true,
    "коробка": true
  },
  "migrated_at": ISODate("..."),
  "synced_at": ISODate("...")
}
```

### 2. Reading Availability

The client bot reads availability in this priority order:

1. **Root-level fields** (preferred) - e.g., `"картошка": true`
2. **`items` subdocument** (fallback) - e.g., `items.картошка: true`
3. **Local file** (emergency fallback) - `data/availability.json`

This is handled by the `get_availability_dict()` function in `handlers/mongo.py`.

### 3. Automatic Refresh

The availability data is automatically refreshed every **30 seconds** by the `NotificationChecker` background task. This ensures that admin changes are picked up without restarting the bot.

**Files modified:**
- `handlers/notification.py` - Added availability refresh to `NotificationChecker._run()`
- `bot.py` - Pass `bot_data` to `NotificationChecker` constructor

### 4. UI Filtering

Unavailable items are automatically hidden from the user interface:

#### Samsa Menu
When a user starts an order (`/order`), only available samsa types are shown:

```python
available_items = [
    [InlineKeyboardButton(f"{get_short_name(context, k)} - {PRICES[k]:,} сум", callback_data=f'samsa:{k}')]
    for k in SAMSA_KEYS if context.bot_data['avail'].get(k, False)
]
```

**Locations in `handlers/order.py`:**
- `order_start()` - Line ~240
- `start_new_cart()` - Line ~458
- `back_to_menu()` - Line ~655

#### Packaging Menu
When a user selects packaging, only available packaging options are shown:

```python
for key in PACKAGING_KEYS:
    if context.bot_data['avail'].get(key, False):
        packaging_buttons.append([...])
```

**Location in `handlers/order.py`:**
- `show_packaging_menu()` - Line ~771

### 5. Runtime Validation

Even if a user somehow bypasses the UI (e.g., using cached buttons or during an availability change), the bot validates availability when they select an item:

#### Samsa Selection
```python
# Check if item is available
if not context.bot_data.get('avail', {}).get(key, False):
    await q.answer(
        get_lang_text(
            context,
            "❌ Этот товар временно недоступен",
            "❌ Bu mahsulot vaqtincha mavjud emas"
        ),
        show_alert=True
    )
    return ITEM_SELECT
```

**Location in `handlers/order.py`:**
- `select_samsa()` - Line ~319

#### Packaging Selection
```python
# Check if packaging is available
if not context.bot_data.get('avail', {}).get(key, False):
    await q.answer(
        get_lang_text(
            context,
            "❌ Эта упаковка временно недоступна",
            "❌ Bu qadoqlash vaqtincha mavjud emas"
        ),
        show_alert=True
    )
    return PACKAGING_SELECT
```

**Location in `handlers/order.py`:**
- `select_packaging()` - Line ~851

## User Experience

### When an Item is Disabled

1. **Immediate Effect (within 30 seconds):**
   - Item disappears from the order menu
   - Existing buttons become non-functional with an alert message

2. **User Feedback:**
   - If user clicks a disabled item: Shows alert "❌ Этот товар временно недоступен" / "❌ Bu mahsulot vaqtincha mavjud emas"
   - If no items are available: Shows message "❌ В данный момент самса недоступна" / "❌ Hozircha somsa mavjud emas"

### When an Item is Re-enabled

1. **Immediate Effect (within 30 seconds):**
   - Item reappears in the order menu
   - Users can select and order it normally

## Admin Workflow

1. Admin opens admin bot and runs `/inventory`
2. Admin clicks "Отключить · зелень" to disable зелень
3. Admin bot updates MongoDB:
   ```javascript
   {
     "зелень": false,
     "items.зелень": false,
     "synced_at": new Date()
   }
   ```
4. Within 30 seconds, client bot refreshes availability
5. Users no longer see зелень in their order menu

## Technical Implementation

### Key Functions

#### `handlers/mongo.py`

**`get_availability_dict() -> Dict[str, bool]`**
- Fetches availability from MongoDB
- Returns dict like `{"картошка": True, "зелень": False}`
- Default is `True` if item not found (fail-safe)

**`is_item_available(key: str) -> bool`**
- Checks if a specific item is available
- Returns `True` if available or not found (default)
- Returns `False` if explicitly disabled

#### `handlers/notification.py`

**`NotificationChecker._run()`**
- Runs every 30 seconds
- Sends pending notifications
- **NEW:** Refreshes availability from MongoDB
- Updates `context.bot_data['avail']` automatically

#### `handlers/order.py`

**Menu Building Functions:**
- `order_start()` - Filters samsa menu
- `start_new_cart()` - Filters samsa menu
- `back_to_menu()` - Filters samsa menu
- `show_packaging_menu()` - Filters packaging menu

**Validation Functions:**
- `select_samsa()` - Validates samsa availability
- `select_packaging()` - Validates packaging availability

## Synchronization Flow

```
Admin Bot                    MongoDB                     Client Bot
─────────                    ───────                     ──────────
1. Admin clicks              2. Update:                  3. Background task
   "Отключить · зелень"         зелень: false               runs every 30s
                                items.зелень: false          
                                synced_at: now           4. Fetch availability
                                                            from MongoDB
                                                         
                                                         5. Update bot_data
                                                            avail['зелень'] = False
                                                         
                                                         6. User opens /order
                                                            зелень not shown
```

## Testing Checklist

- [x] Unavailable samsa types are hidden from order menu
- [x] Unavailable packaging is hidden from packaging menu
- [x] Clicking a disabled item shows alert message
- [x] Availability refreshes automatically (30s interval)
- [x] Changes persist after bot restart
- [x] Default behavior is to show items if availability data fails to load
- [x] Both Russian and Uzbek error messages work
- [x] Root-level fields are read first, then `items` subdocument

## Troubleshooting

### Items not updating after admin changes

**Symptom:** Admin disables an item, but it still appears in client bot after 1+ minute

**Solutions:**
1. Check MongoDB connection in client bot logs
2. Verify `NotificationChecker` is running (look for "✅ Notification checker started")
3. Check that `synced_at` timestamp is updating in MongoDB
4. Restart client bot to force immediate refresh

### All items showing as unavailable

**Symptom:** No items appear in order menu

**Solutions:**
1. Check `availability` collection exists in MongoDB
2. Verify at least one item has `true` value
3. Check client bot logs for availability loading errors
4. Verify `context.bot_data['avail']` is populated (check logs)

### Items showing despite being disabled

**Symptom:** Disabled items still appear in menu

**Solutions:**
1. Verify admin bot is updating **both** root-level and `items.{key}` fields
2. Check that `synced_at` is being updated
3. Restart client bot to force refresh
4. Check that `get_availability_dict()` is reading from correct fields

## Notes

- **Default behavior:** If availability data fails to load, items are shown by default (fail-safe)
- **Refresh interval:** 30 seconds (configurable in `bot.py` line ~261)
- **Backward compatibility:** Supports both root-level fields and `items` subdocument
- **No restart required:** Changes take effect automatically within 30 seconds
- **Multilingual:** All error messages support Russian and Uzbek

