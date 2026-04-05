import requests
from concurrent.futures import ThreadPoolExecutor

# =========================
# YOUR PROXIES LIST
# =========================
new_proxies = [
    {"host": "31.59.20.176", "port": 6754, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "23.95.150.145", "port": 6114, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "198.23.239.134", "port": 6540, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "45.38.107.97", "port": 6014, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "107.172.163.27", "port": 6543, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "198.105.121.200", "port": 6462, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "216.10.27.159", "port": 6837, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "142.111.67.146", "port": 5611, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "191.96.254.138", "port": 6185, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "31.58.9.4", "port": 6077, "username": "atjoplnk", "password": "g5so8c2amqv1"},
]

# =========================
# TEST FUNCTION
# =========================
def test_proxy(proxy):
    proxy_url = f"http://{proxy['username']}:{proxy['password']}@{proxy['host']}:{proxy['port']}"
    
    proxies = {
        "http": proxy_url,
        "https": proxy_url
    }

    try:
        print(f"\n🔍 Testing {proxy['host']}:{proxy['port']}")

        response = requests.get(
            "https://httpbin.org/ip",
            proxies=proxies,
            timeout=10
        )

        if response.status_code == 200:
            print(f"✅ WORKING: {proxy['host']}")
            print(f"🌍 IP Response: {response.text}")
        else:
            print(f"⚠️ BAD STATUS ({response.status_code}): {proxy['host']}")

    except Exception as e:
        print(f"❌ FAILED: {proxy['host']}")
        print(f"💥 ERROR: {str(e)}")


# =========================
# RUN ALL TESTS (MULTI THREAD)
# =========================
if __name__ == "__main__":
    print("🚀 Starting proxy tests...\n")

    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(test_proxy, new_proxies)

    print("\n🏁 Testing completed.")