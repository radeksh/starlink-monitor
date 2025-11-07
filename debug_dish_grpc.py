#!/usr/bin/env python3
"""Debug script to inspect available fields in Starlink response."""

from starlink_client import StarlinkClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    client = StarlinkClient()
    client.connect()

    # Test get_history
    print("\n=== Testing get_history ===")
    request_class = client.reflector.message_class("SpaceX.API.Device.Request")
    request = request_class()
    request.get_history.SetInParent()

    response = client.device_stub.Handle(request, timeout=10)
    history = response.dish_get_history

    print(f"Type: {type(history)}")

    print("\n=== ListFields() output (actual fields present) ===")
    for field_descriptor, value in history.ListFields():
        if hasattr(value, '__len__') and not isinstance(value, str):
            print(f"  {field_descriptor.name}: <list/array with {len(value)} items>")
        else:
            print(f"  {field_descriptor.name}: {value}")

    print("\n=== Checking specific fields ===")
    fields_to_check = [
        "current_index",
        "pop_ping_drop_rate",
    ]

    for field in fields_to_check:
        try:
            value = getattr(history, field)
            if hasattr(value, '__len__') and not isinstance(value, str):
                print(f"  {field}: <{len(value)} items> ✓")
            else:
                print(f"  {field}: {value} ✓")
        except AttributeError:
            print(f"  {field}: NOT FOUND ✗")

    client.close()

except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
