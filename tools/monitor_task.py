#!/usr/bin/env python3
import requests
import time

for i in range(30):
    time.sleep(2)
    status = requests.get("http://localhost:8000/api/v1/tasks/by-name/test_realtime_save/status").json()['status']
    conv = requests.get("http://localhost:8000/api/v1/tasks/by-name/test_realtime_save/conversation").json()
    interactions = len(conv['conversation'])
    print(f"[{i+1}] Status: {status}, Interactions: {interactions}")
    if status != "RUNNING":
        print("\nFinal conversation:")
        for inter in conv['conversation'][:10]:
            print(f"  - [{inter['type']}]: {inter['content'][:80]}...")
        break
