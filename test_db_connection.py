from dotenv import load_dotenv
import os
import libsql_client

load_dotenv()

URL = os.getenv('TURSO_DATABASE_URL')
TOKEN = os.getenv('TURSO_AUTH_TOKEN')

# Convert to HTTPS
if URL.startswith('libsql://'):
    HTTP_URL = URL.replace('libsql://', 'https://')
else:
    HTTP_URL = URL

print("=" * 60)
print("Testing Turso Connection")
print("=" * 60)
print(f"URL: {HTTP_URL}")
print(f"Token (first 30 chars): {TOKEN[:30]}...")
print("=" * 60)

try:
    print("\n🔄 Connecting...")
    client = libsql_client.create_client_sync(url=HTTP_URL, auth_token=TOKEN)
    
    print("✅ Connected successfully!")
    
    print("\n🧪 Running test query...")
    result = client.execute("SELECT 1 as test")
    print(f"✅ Test query successful: {result.rows}")
    
    print("\n✅ Everything looks good! Ready to migrate.")
    
except Exception as e:
    print(f"\n❌ Connection failed: {e}")
    print("\nPlease check:")
    print("1. Your .env file has the correct token")
    print("2. The token has no extra spaces or quotes")
    print("3. The token is valid and not expired")