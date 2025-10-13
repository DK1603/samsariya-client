from __future__ import annotations

import os
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from config import (
    MONGO_URI,
    MONGO_DB_NAME,
    MONGO_COLLECTION_ORDERS,
    MONGO_COLLECTION_REVIEWS,
    MONGO_COLLECTION_AVAILABILITY,
    MONGO_COLLECTION_PRODUCTS,
    MONGO_COLLECTION_NOTIFICATIONS,
    MONGO_COLLECTION_TEMP_CARTS,
    DATA_DIR,
    ORDERS_DB,
    REVIEWS_FILE,
    AVAILABILITY_FILE,
)
from .catalog import PRICES, DISPLAY_NAMES, SHORT_NAMES, SAMSA_KEYS, ALL_KEYS

_client: Optional[AsyncIOMotorClient] = None


def close_client():
    """Close MongoDB client connection."""
    global _client
    if _client:
        try:
            _client.close()
        except:
            pass
        _client = None


def _get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        if not MONGO_URI:
            raise RuntimeError("MONGO_URI is not configured in environment")
        
        # Try multiple connection strategies for MongoDB Atlas
        connection_strategies = [
            # Strategy 1: Minimal connection (most compatible)
            {
                "serverSelectionTimeoutMS": 5000,
                "connectTimeoutMS": 5000,
                "socketTimeoutMS": 5000,
            },
            # Strategy 2: Standard Atlas connection
            {
                "serverSelectionTimeoutMS": 10000,
                "connectTimeoutMS": 10000,
                "socketTimeoutMS": 10000,
                "maxPoolSize": 10,
                "minPoolSize": 1,
                "retryWrites": True,
                "retryReads": True,
            },
            # Strategy 3: Atlas with custom SSL context
            {
                "serverSelectionTimeoutMS": 15000,
                "connectTimeoutMS": 15000,
                "socketTimeoutMS": 15000,
                "maxPoolSize": 5,
                "minPoolSize": 1,
                "retryWrites": True,
                "retryReads": True,
            }
        ]
        
        last_error = None
        for i, strategy in enumerate(connection_strategies):
            try:
                print(f"🧪 Trying MongoDB connection strategy {i+1}...")
                _client = AsyncIOMotorClient(MONGO_URI, **strategy)
                
                # Test the connection without creating new event loops
                import asyncio
                try:
                    # Simple connection test - don't create new loops
                    # Just create the client and let it connect naturally
                    print(f"✅ MongoDB client created with strategy {i+1}")
                    break
                except Exception as e:
                    last_error = e
                    print(f"❌ Strategy {i+1} failed: {e}")
                    if _client:
                        try:
                            _client.close()
                        except:
                            pass
                        _client = None
                    
            except Exception as e:
                last_error = e
                print(f"❌ Strategy {i+1} failed: {e}")
                continue
        
        if _client is None:
            print("⚠️ All MongoDB connection strategies failed, will use fallback mode")
            raise RuntimeError(f"All MongoDB connection strategies failed: {last_error}")
            
    return _client


def get_db():
    return _get_client()[MONGO_DB_NAME]


def get_orders_collection() -> AsyncIOMotorCollection:
    return get_db()[MONGO_COLLECTION_ORDERS]


def get_reviews_collection() -> AsyncIOMotorCollection:
    return get_db()[MONGO_COLLECTION_REVIEWS]


def get_availability_collection() -> AsyncIOMotorCollection:
    return get_db()[MONGO_COLLECTION_AVAILABILITY]

def get_products_collection() -> AsyncIOMotorCollection:
    return get_db()[MONGO_COLLECTION_PRODUCTS]

def get_notifications_collection() -> AsyncIOMotorCollection:
    return get_db()[MONGO_COLLECTION_NOTIFICATIONS]


def get_temp_carts_collection() -> AsyncIOMotorCollection:
    """Get temporary carts collection."""
    return get_db()[MONGO_COLLECTION_TEMP_CARTS]


async def test_connection() -> bool:
    """Test MongoDB connection and return True if successful"""
    try:
        client = _get_client()
        # Test the connection by running a simple command
        await client.admin.command('ping')
        print("MongoDB connection successful")
        return True
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        return False


async def ensure_indexes() -> None:
    try:
        # Test connection first
        if not await test_connection():
            print("Cannot create indexes - MongoDB connection failed")
            return
            
        orders = get_orders_collection()
        await orders.create_index("user_id")
        await orders.create_index("created_at")
        products = get_products_collection()
        await products.create_index("key", unique=True)
        notifications = get_notifications_collection()
        await notifications.create_index("user_id")
        await notifications.create_index("sent")
        await notifications.create_index("created_at")
        print("MongoDB indexes created successfully")
    except Exception as e:
        print(f"Error creating indexes: {e}")
        raise


async def seed_reviews_if_needed() -> None:
    col = get_reviews_collection()
    count = await col.estimated_document_count()
    if count > 0:
        return
    path = REVIEWS_FILE
    if not os.path.exists(path):
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            reviews = json.load(f)
        if isinstance(reviews, list) and reviews:
            # Normalize
            docs = []
            for r in reviews:
                if not isinstance(r, dict):
                    continue
                docs.append({
                    'user': r.get('user', ''),
                    'text': r.get('text', ''),
                    'migrated_at': datetime.now(timezone.utc),
                })
            if docs:
                await col.insert_many(docs)
    except Exception:
        # Best-effort seed; ignore errors
        return


async def seed_availability_if_needed() -> None:
    col = get_availability_collection()
    existing = await col.find_one({'_id': 'availability'})
    if existing:
        return
    path = AVAILABILITY_FILE
    if not os.path.exists(path):
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            avail = json.load(f)
        if isinstance(avail, dict):
            await col.insert_one({'_id': 'availability', 'items': avail, 'migrated_at': datetime.now(timezone.utc)})
    except Exception:
        return


async def seed_inventory_from_catalog() -> None:
    avail_col = get_availability_collection()
    prod_col = get_products_collection()
    # Ensure a baseline availability doc exists
    doc = await avail_col.find_one({'_id': 'availability'})
    if not doc or not isinstance(doc, dict):
        await avail_col.replace_one(
            {'_id': 'availability'},
            {'_id': 'availability', 'items': {}, 'migrated_at': datetime.now(timezone.utc)},
            upsert=True,
        )
        doc = {'_id': 'availability', 'items': {}}
    items_map = doc.get('items', {}) if isinstance(doc, dict) else {}
    if isinstance(items_map, bool):
        # Fix bad type if previously written incorrectly
        items_map = {}
    # Sync products collection (one doc per product) - include all items
    for key in ALL_KEYS:
        display_name = DISPLAY_NAMES.get(key, key)
        price = PRICES.get(key, 0)
        short_name = SHORT_NAMES.get(key, key)
        await prod_col.update_one(
            {'key': key},
            {'$set': {
                'key': key,
                'display_name': display_name,
                'short_name': short_name,
                'price': price,
                'category': 'samsa' if key in SAMSA_KEYS else 'packaging',
                'updated_at': datetime.now(timezone.utc),
            }, '$setOnInsert': {
                'created_at': datetime.now(timezone.utc)
            }},
            upsert=True
        )
        if key not in items_map:
            items_map[key] = True
    # Write back availability map
    await avail_col.update_one({'_id': 'availability'}, {
        '$set': {
            'items': items_map,
            'synced_at': datetime.now(timezone.utc)
        }
    })


async def seed_orders_if_needed() -> None:
    col = get_orders_collection()
    count = await col.estimated_document_count()
    if count > 0:
        return
    path = ORDERS_DB
    if not os.path.exists(path):
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            orders_by_user = json.load(f)
        if not isinstance(orders_by_user, dict):
            return
        docs: List[Dict[str, Any]] = []
        for user_id_str, orders in orders_by_user.items():
            if not isinstance(orders, list):
                continue
            for order in orders:
                if not isinstance(order, dict):
                    continue
                try:
                    user_id: Any = int(user_id_str)
                except Exception:
                    user_id = user_id_str
                docs.append({
                    'user_id': user_id,
                    'items': order.get('items', {}),
                    'total': order.get('total', 0),
                    'contact': order.get('contact'),
                    'delivery': order.get('delivery'),
                    'time': order.get('time'),
                    'method': order.get('method'),
                    'summary': order.get('summary'),
                    'created_at': datetime.now(timezone.utc),
                    'migrated_at': datetime.now(timezone.utc),
                    'source': 'orders.json',
                })
        if docs:
            # Insert in chunks to avoid large batch
            chunk_size = 1000
            for i in range(0, len(docs), chunk_size):
                await col.insert_many(docs[i:i+chunk_size])
    except Exception:
        return


async def initialize_temp_carts() -> None:
    """Initialize temp_carts collection with indexes"""
    try:
        temp_carts_col = get_temp_carts_collection()
        # Create index on user_id for fast lookups
        await temp_carts_col.create_index("user_id", unique=True)
        # Create TTL index to auto-delete old carts after 7 days
        await temp_carts_col.create_index("created_at", expireAfterSeconds=7*24*60*60)
        logging.info("✅ Temp carts collection initialized")
    except Exception as e:
        logging.error(f"❌ Error initializing temp_carts: {e}")


async def initialize_database() -> None:
    await ensure_indexes()
    await seed_availability_if_needed()
    await seed_inventory_from_catalog()
    await seed_reviews_if_needed()
    await seed_orders_if_needed()
    await initialize_temp_carts()


async def get_availability_dict() -> Dict[str, bool]:
    doc = await get_availability_collection().find_one({'_id': 'availability'})
    if doc and isinstance(doc.get('items'), dict):
        return {k: bool(v) for k, v in doc['items'].items()}
    # Fallback to file if any
    path = AVAILABILITY_FILE
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                avail = json.load(f)
            if isinstance(avail, dict):
                return {k: bool(v) for k, v in avail.items()}
        except Exception:
            pass
    return {}


