#!/usr/bin/env python3
"""
Simple MongoDB connection test script
Run this to test your MongoDB connection before starting the bot
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_mongodb_connection():
    """Test MongoDB connection with different configurations"""
    mongo_uri = os.getenv('MONGO_URI') or os.getenv('MONGODB_URI')
    
    if not mongo_uri:
        print("❌ No MongoDB URI found in environment variables")
        print("Please check your .env file")
        return False
    
    print(f"🔗 Testing connection to: {mongo_uri[:50]}...")
    
    # Test different connection configurations
    configs = [
        {
            "name": "Default SSL",
            "config": {
                "serverSelectionTimeoutMS": 30000,
                "connectTimeoutMS": 30000,
                "socketTimeoutMS": 30000,
                "maxPoolSize": 10,
                "minPoolSize": 1,
                "retryWrites": True,
                "retryReads": True,
            }
        },
        {
            "name": "No SSL",
            "config": {
                "serverSelectionTimeoutMS": 30000,
                "connectTimeoutMS": 30000,
                "socketTimeoutMS": 30000,
                "maxPoolSize": 10,
                "minPoolSize": 1,
                "retryWrites": True,
                "retryReads": True,
                "tls": False,
            }
        },
        {
            "name": "Relaxed SSL",
            "config": {
                "serverSelectionTimeoutMS": 30000,
                "connectTimeoutMS": 30000,
                "socketTimeoutMS": 30000,
                "maxPoolSize": 10,
                "minPoolSize": 1,
                "retryWrites": True,
                "retryReads": True,
                "tls": True,
                "tlsAllowInvalidCertificates": True,
                "tlsAllowInvalidHostnames": True,
            }
        }
    ]
    
    for config in configs:
        print(f"\n🧪 Testing {config['name']} configuration...")
        try:
            client = AsyncIOMotorClient(mongo_uri, **config['config'])
            
            # Test connection
            await client.admin.command('ping')
            print(f"✅ {config['name']}: Connection successful!")
            
            # Test database access
            db = client.get_database()
            collections = await db.list_collection_names()
            print(f"📊 Available collections: {collections}")
            
            await client.close()
            return True
            
        except Exception as e:
            print(f"❌ {config['name']}: Connection failed - {e}")
            continue
    
    print("\n❌ All connection attempts failed")
    print("\n🔧 Troubleshooting tips:")
    print("1. Check your MongoDB URI in .env file")
    print("2. Verify your IP is whitelisted in MongoDB Atlas")
    print("3. Check if your MongoDB cluster is running")
    print("4. Try connecting from MongoDB Compass to verify credentials")
    print("5. Check if your MongoDB version supports the connection string format")
    
    return False

if __name__ == "__main__":
    print("🚀 MongoDB Connection Test")
    print("=" * 40)
    
    try:
        result = asyncio.run(test_mongodb_connection())
        if result:
            print("\n🎉 MongoDB connection test successful!")
            print("Your bot should be able to connect to MongoDB.")
        else:
            print("\n💥 MongoDB connection test failed!")
            print("Please fix the connection issues before starting your bot.")
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
