#!/usr/bin/env python3
"""Quick test of the fixed starlink_client."""

from starlink_client import StarlinkClient
import logging

logging.basicConfig(level=logging.INFO)

client = StarlinkClient()
client.connect()

print("\nTesting get_status():")
status = client.get_status()
print(f"  pop_ping_drop_rate: {status['pop_ping_drop_rate']}")
print(f"  pop_ping_latency_ms: {status['pop_ping_latency_ms']}")
print(f"  uptime_s: {status['uptime_s']}")

client.close()
print("\n✓ Success!")
