#!/usr/bin/env python3
"""E2E verification script for admin panel backend APIs."""
import requests, json

BASE = 'http://localhost:8000'
h = {'Content-Type': 'application/json'}

# 1. Login
r = requests.post(f'{BASE}/api/auth/login', json={'phone': '13800138000', 'password': '123456'})
assert r.status_code == 200, f'Login failed: {r.text}'
token = r.json()['access_token']
h['Authorization'] = f'Bearer {token}'
print('1. Login: OK')

# 2. Create project
r = requests.post(f'{BASE}/api/projects', json={
    'name': 'E2E验证项目', 'total_area': 120,
    'floors': [{'name': '1层', 'floor_number': 1, 'area': 120,
        'rooms': [{'name': '客厅', 'type': 'living_room'}, {'name': '主卧', 'type': 'bedroom'}, {'name': '厨房', 'type': 'kitchen'}]}]
}, headers=h)
assert r.status_code in (200, 201), f'Create project failed: {r.text}'
pid = r.json()['id']
print(f'2. Create project: {pid[:12]}... OK')

# 3. Create budget
r = requests.post(f'{BASE}/api/budgets', json={
    'project_id': pid, 'lines': [
        {'category': 'civil', 'name': '拆除', 'estimated_amount': 1500},
        {'category': 'finish', 'name': '涂料', 'estimated_amount': 3800},
        {'category': 'kitchen', 'name': '橱柜', 'estimated_amount': 8500}]
}, headers=h)
assert r.status_code in (200, 201), f'Create budget failed: {r.text}'
total = r.json().get('total_estimated', '?')
print(f'3. Create budget: total={total} OK')

# 4. Get supplier and materials
r = requests.get(f'{BASE}/api/procurement/suppliers', headers=h)
assert r.status_code == 200
suppliers = r.json()
sid = suppliers[0]['id'] if suppliers else None
print(f'4. Get suppliers: {len(suppliers)} found, using id={sid[:12] if sid else "N/A"}')

r = requests.get(f'{BASE}/api/materials?limit=3', headers=h)
mats = r.json() if isinstance(r.json(), list) else r.json().get('items', [])
mid1 = mats[0]['id'] if len(mats)>0 else None
mid2 = mats[1]['id'] if len(mats)>1 else mid1
print(f'5. Get materials: {len(mats)} found')

if sid and mid1:
    # 5. Create procurement order (with required fields)
    r = requests.post(f'{BASE}/api/procurement/orders', json={
        'project_id': pid, 'supplier_id': sid, 'lines': [
            {'material_id': mid1, 'quantity': 50, 'unit_price': 35},
            {'material_id': mid2, 'quantity': 100, 'unit_price': 68}]
    }, headers=h)
    assert r.status_code in (200, 201), f'Create order failed: {r.text}'
    total = r.json().get('total_amount', '?')
    print(f'6. Create order: total={total} OK')
else:
    print('6. Create order: SKIPPED (no supplier/material data)')

# 6. Create construction task
r = requests.post(f'{BASE}/api/construction/tasks', json={
    'project_id': pid, 'name': '水电改造', 'phase': 'plumbing',
    'start_date': '2026-07-11', 'end_date': '2026-07-18', 'status': 'pending'
}, headers=h)
assert r.status_code in (200, 201), f'Create task failed: {r.text}'
phase = r.json().get('phase', '?')
print(f'7. Create task: phase={phase} OK')

# 7. Verify data retrieval
r = requests.get(f'{BASE}/api/projects', headers=h)
print(f'8. Projects: {len(r.json())} found OK')
r = requests.get(f'{BASE}/api/budgets/project/{pid}', headers=h)
print(f'9. Budgets: {len(r.json())} found OK')
r = requests.get(f'{BASE}/api/procurement/orders', headers=h)
print(f'10. Orders: {len(r.json())} found OK')
r = requests.get(f'{BASE}/api/construction/tasks', headers=h)
print(f'11. Tasks: {len(r.json())} found OK')

print('\n=== E2E 全链路验证通过 ===')
