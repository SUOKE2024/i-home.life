import requests, json, sys

BASE = "http://118.31.223.213:8081"
results = []
def ok(name, cond, detail=""):
    results.append((name, cond, detail))
    ch = "PASS" if cond else "FAIL"
    print("  [%s] %s: %s" % (ch, name, detail))

print("=" * 60)
print("v1.1.26 Web AR card E2E")
print("=" * 60)

print("\n[1/4] Web deployment")
r = requests.get(BASE + "/workbench.html", timeout=10)
html = r.text
ok("HTTP 200", r.status_code == 200, str(r.status_code))
ok("cardMessageType var", "let cardMessageType = null" in html, "declared")
ok("meta message_type", "data.message_type" in html, "captured")
ok("done card replace", "cardMessageType && fullContent" in html, "replaced")
count = html.count("resp.message_type || 'text'")
ok("non-stream message_type", count >= 2, "count=%d" % count)

print("\n[2/4] message-renderers.js")
r = requests.get(BASE + "/assets/js/message-renderers.js", timeout=10)
js = r.text
ok("renderArScanTriggerCard", "renderArScanTriggerCard" in js, "defined")
ok("case ar_scan_trigger", "case 'ar_scan_trigger'" in js, "registered")

print("\n[3/4] Non-streaming API")
r = requests.post(BASE + "/api/auth/login",
    json={"phone": "13900000099", "password": "Test123456!"}, timeout=10)
token = r.json().get("access_token", "")
ok("login", bool(token), "len=%d" % len(token))
h = {"Authorization": "Bearer " + token}

r = requests.post(BASE + "/api/agents/chat",
    json={"message": "AR"}, headers=h, timeout=30)
d = r.json()
ok("agent_type", d.get("agent_type") == "ar_measurement", str(d.get("agent_type")))
ok("message_type", d.get("message_type") == "ar_scan_trigger", str(d.get("message_type")))
cp = d.get("card_payload", {})
ok("card title", cp.get("title") == "📏 AR空间测量", str(cp.get("title")))
ok("sensor_type", cp.get("sensor_type") == "LiDAR", str(cp.get("sensor_type")))
ok("features", len(cp.get("supported_features", [])) == 5, str(len(cp.get("supported_features", []))))

print("\n[4/4] SSE streaming API")
r = requests.post(BASE + "/api/agents/chat/stream",
    json={"message": "量房"}, headers=h, stream=True, timeout=30)
meta, tokens = False, 0
for line in r.iter_lines():
    if not line: continue
    line = line.decode("utf-8")
    if line.startswith("data: "):
        data = line[6:]
        if data == "[DONE]": break
        try:
            obj = json.loads(data)
            if obj.get("event") == "meta" and not meta:
                meta = True
                ok("SSE meta agent_type", obj.get("agent_type") == "ar_measurement", str(obj.get("agent_type")))
                ok("SSE meta message_type", obj.get("message_type") == "ar_scan_trigger", str(obj.get("message_type")))
                mcp = obj.get("card_payload", {})
                ok("SSE card title", mcp.get("title") == "\U0001f4cf AR\u7a7a\u95f4\u6d4b\u91cf", str(mcp.get("title")))
            elif obj.get("event") == "token":
                tokens += 1
        except: pass
ok("SSE meta received", meta, "")
ok("SSE tokens", tokens > 0, "count=%d" % tokens)

print("\n" + "=" * 60)
passed = sum(1 for _, c, _ in results if c)
failed = sum(1 for _, c, _ in results if not c)
print("Result: %d/%d passed%s" % (passed, len(results), ", %d failed" % failed if failed else ""))
if failed:
    for n, c, d in results:
        if not c: print("  FAIL: %s - %s" % (n, d))
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
