# Admin Bot Integration Guide

## Problem
Card payment orders were not appearing in the admin bot because they had `status = 'pending_admin_confirmation'` while the admin bot was only querying for `status = 'new'`.

## Solution Implemented (Client Bot)
Changed card payment orders to use `status = 'new'` (same as cash orders) but added a special flag `requires_payment_check` to distinguish them.

## Changes Made to Client Bot

### 1. Order Status
- **Before**: Card payment orders → `status = 'pending_admin_confirmation'`
- **After**: Card payment orders → `status = 'new'` (same as cash orders)

### 2. New Field Added
Added `requires_payment_check` field to order documents:
- `true` for card payment orders that need manual verification
- `false` or absent for cash orders

## What Admin Bot Needs to Do

### 1. Query for New Orders
Your admin bot should query for orders with `status = 'new'`:

```python
# Example query
orders = await orders_collection.find({'status': 'new'}).sort('created_at', -1).to_list(length=100)
```

### 2. Display Payment Verification Flag
When displaying orders, check the `requires_payment_check` field:

```python
for order in orders:
    if order.get('requires_payment_check', False):
        # Show special indicator: ⚠️ ТРЕБУЕТ ПРОВЕРКИ ОПЛАТЫ
        # Display with card payment icon: 💳
        # Show payment amount: order['payment_amount']
        # Highlight that admin needs to manually verify payment within 10 minutes
        pass
```

### 3. Order Display Format
For card payment orders, display something like:

```
⚠️ ТРЕБУЕТ ПРОВЕРКИ ОПЛАТЫ

👤 {customer_name}
🆔 {order_id}
💰 {total:,} сум
💳 Оплата картой
📞 {customer_phone}
📍 {customer_address}
🚚 {delivery_type}
⏰ {delivery_time}

📦 Заказ:
• мясо: 2 шт
• пакет: 1 шт

⚠️ Клиент указал, что оплатил {payment_amount:,} сум
⏰ Проверьте оплату в течение 10 минут
```

### 4. Admin Actions
The admin bot should provide buttons to:
- ✅ **Подтвердить оплату** → Update `status` to `confirmed`, set `payment_verified` to `true`
- ❌ **Отклонить** → Update `status` to `payment_failed`, notify customer
- 🔍 **Проверить позже** → Keep in queue

### 5. Order Fields Reference

All orders now have these fields:
```python
{
    'user_id': int,
    'items': dict,  # {'meat': 2, 'package': 1}
    'total': int,
    'customer_name': str,
    'customer_phone': str,
    'customer_address': str,
    'contact': str,  # 'Позвонить' or 'Написать'
    'delivery': str,  # 'Доставка' or 'Самовывоз'
    'time': str,  # 'Как можно скорее' or specific time
    'method': str,  # '💵 Наличные' or '💳 Оплатить по карте'
    'summary': str,  # Full formatted summary
    'status': str,  # 'new', 'confirmed', 'in_progress', 'ready', 'completed', 'cancelled', 'payment_failed'
    'payment_verified': bool,  # True if user submitted payment proof
    'payment_amount': int,  # Amount user claims to have paid
    'is_preorder': bool,  # True if ordered between 22:00-06:00
    'requires_payment_check': bool,  # NEW: True if admin needs to verify card payment
    'created_at': datetime
}
```

### 6. Filtering Orders

To separate card payment orders from cash orders:

```python
# Card payment orders requiring verification
card_orders = await orders_collection.find({
    'status': 'new',
    'requires_payment_check': True
}).sort('created_at', -1).to_list(length=100)

# Regular cash orders
cash_orders = await orders_collection.find({
    'status': 'new',
    '$or': [
        {'requires_payment_check': False},
        {'requires_payment_check': {'$exists': False}}
    ]
}).sort('created_at', -1).to_list(length=100)

# All new orders together
all_new_orders = await orders_collection.find({
    'status': 'new'
}).sort('created_at', -1).to_list(length=100)
```

## Testing

1. **Test Card Payment Flow**:
   - Client selects card payment
   - Client submits payment proof
   - Order should appear in admin bot with `requires_payment_check: true`
   - Admin can verify and approve

2. **Test Cash Payment Flow**:
   - Client selects cash payment
   - Order should appear in admin bot with `requires_payment_check: false` or field absent
   - Admin processes normally

## Notes

- The 10-minute timer is tracked on the client side via `payment_start_time` in `context.user_data`
- The `payment_amount` field stores what the user claims to have paid
- The `payment_verified` field indicates if the user submitted payment proof (not admin verification)
- Admin verification should update the `status` field to `confirmed` or `payment_failed`

