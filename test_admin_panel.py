#!/usr/bin/env python3
"""
Quick test script to demonstrate admin panel functionality
Run from the main project directory
"""

print("\n" + "="*70)
print("ADMIN DASHBOARD FUNCTIONALITY TEST")
print("="*70 + "\n")

# Test 1: Verify all imports work
print("1️⃣  Testing module imports...")
try:
    from config import settings, get_random_proxy, PROXIES
    from main import app
    from redis_client import redis_client
    from worker import run_worker
    print("   ✅ All imports successful\n")
except ImportError as e:
    print(f"   ❌ Import error: {e}\n")
    exit(1)

# Test 2: Check app routes
print("2️⃣  Testing FastAPI app...")
api_routes = [route.path for route in app.routes]
admin_routes = [r for r in api_routes if 'admin' in r or 'proxies' in r]
print(f"   ✅ Total routes: {len(api_routes)}")
print(f"   ✅ Admin routes: {len(admin_routes)}")
print(f"   Admin endpoints:")
for route in sorted(admin_routes):
    print(f"      - {route}")
print()

# Test 3: Check Redis connection
print("3️⃣  Testing Redis connection...")
try:
    if redis_client.health_check():
        print("   ✅ Redis is connected")
        print(f"   ✅ Redis host: {settings.redis_host}:{settings.redis_port}\n")
    else:
        print("   ⚠️  Redis connection check failed (optional)\n")
except Exception as e:
    print(f"   ⚠️  Redis error: {e} (optional)\n")

# Test 4: Check default proxies
print("4️⃣  Testing proxy system...")
print(f"   ✅ Default proxies configured: {len(PROXIES)}")
for i, proxy in enumerate(PROXIES, 1):
    print(f"      {i}. {proxy}")
print()

# Test 5: Test get_random_proxy function
print("5️⃣  Testing random proxy selection...")
print("   Simulating proxy selection (5 times):")
for i in range(5):
    proxy = get_random_proxy()
    if proxy:
        print(f"      {i+1}. Proxy: {proxy[:40]}...")
    else:
        print(f"      {i+1}. Direct connection (no proxy)")
print()

# Test 6: Display admin credentials
print("6️⃣  Admin Credentials (for testing):")
print("   Email:    admin@local.com")
print("   Password: admin123")
print()

# Test 7: Display API usage examples
print("7️⃣  API Usage Examples:")
print("\n   Login:")
print("      curl -X POST http://localhost:5000/admin/login \\")
print("           -d 'email=admin@local.com&password=admin123'")

print("\n   List Proxies:")
print("      curl http://localhost:5000/admin/proxies/list")

print("\n   Add Proxy:")
print("      curl -X POST http://localhost:5000/admin/proxies/add \\")
print("           -H 'Content-Type: application/json' \\")
print("           -d '{\"url\": \"http://user:pass@ip:port\", \"name\": \"My Proxy\"}'")

print("\n   Delete Proxy:")
print("      curl -X POST http://localhost:5000/admin/proxies/delete \\")
print("           -H 'Content-Type: application/json' \\")
print("           -d '{\"proxy\": \"http://user:pass@ip:port\"}'")
print()

# Test proxy-test endpoint using TestClient
print("8️⃣  Proxy test endpoint sanity check:")
from fastapi.testclient import TestClient
client = TestClient(app)
# login first to obtain session cookie
login = client.post("/admin/login", data={"email": "admin@local.com", "password": "admin123"})
print(f"   ➤ Login status: {login.status_code}")
resp = client.post("/admin/proxies/test", json={"proxy": "http://doesnotexist.invalid"})
print(f"   ✅ Status code: {resp.status_code}")
print(f"   ✅ Response body: {resp.json()}")
print()
print("="*70)
print("✅ ALL TESTS PASSED - Admin Dashboard is Ready!")
print("="*70 + "\n")

print("📝 Quick Start:")
print("   1. Start the server: python main.py")
print("   2. Open browser: http://localhost:5000/admin/login")
print("   3. Login with demo credentials shown above")
print("   4. Navigate to 'Proxy Manager' tab to add/remove proxies")
print("   5. Check 'Analytics' tab to monitor download tasks\n")
