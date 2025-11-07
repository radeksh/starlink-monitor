#!/usr/bin/env python3
"""
Starlink gRPC client for ping drop monitoring.
Simplified client focused on fetching ping_drop metrics.
"""

import grpc
import logging
from typing import Dict, List, Optional, Tuple
from yagrc import reflector


logger = logging.getLogger(__name__)


class StarlinkClient:
    """Client for communicating with Starlink dish via gRPC."""

    def __init__(self, target: str = "192.168.100.1:9200"):
        """
        Initialize Starlink gRPC client.

        Args:
            target: Starlink dish address (IP:port)
        """
        self.target = target
        self.channel = None
        self.reflector = None
        self.device_stub = None

    def connect(self):
        """Establish gRPC connection to Starlink dish."""
        try:
            self.channel = grpc.insecure_channel(self.target)
            self.reflector = reflector.GrpcReflectionClient()
            self.reflector.load_protocols(self.channel, symbols=["SpaceX.API.Device.Device"])

            # Get the Device service stub
            stub_class = self.reflector.service_stub_class("SpaceX.API.Device.Device")
            self.device_stub = stub_class(self.channel)

            logger.info(f"Connected to Starlink dish at {self.target}")
        except Exception as e:
            logger.error(f"Failed to connect to Starlink dish: {e}")
            raise

    def close(self):
        """Close the gRPC channel."""
        if self.channel:
            self.channel.close()
            logger.info("Disconnected from Starlink dish")

    def get_status(self) -> Dict:
        """
        Fetch current status from Starlink dish.

        Returns:
            Dictionary with status data including pop_ping_drop_rate
        """
        try:
            # Create Request message
            request_class = self.reflector.message_class("SpaceX.API.Device.Request")
            request = request_class()
            request.get_status.SetInParent()

            # Make the call
            response = self.device_stub.Handle(request, timeout=10)

            # Extract relevant data
            dish_status = response.dish_get_status

            result = {
                "pop_ping_drop_rate": dish_status.pop_ping_drop_rate,
                "pop_ping_latency_ms": dish_status.pop_ping_latency_ms,
                "uptime_s": dish_status.device_state.uptime_s,
            }

            return result

        except grpc.RpcError as e:
            logger.error(f"gRPC error fetching status: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching status: {e}")
            raise

    def get_history(self, samples: int = -1, start_counter: Optional[int] = None) -> Tuple[Dict, Dict]:
        """
        Fetch history data from Starlink dish.

        Args:
            samples: Number of samples to fetch (-1 for all available)
            start_counter: Counter to start from (for incremental fetching)

        Returns:
            Tuple of (general_info, bulk_data) dictionaries
            - general_info contains: end_counter, samples
            - bulk_data contains: pop_ping_drop_rate (list), timestamps, etc.
        """
        try:
            # Create Request message
            request_class = self.reflector.message_class("SpaceX.API.Device.Request")
            request = request_class()
            request.get_history.SetInParent()

            # Make the call
            response = self.device_stub.Handle(request, timeout=10)

            # Extract history data
            history = response.dish_get_history

            # Determine which samples to return
            end_counter = history.current
            total_samples = len(history.pop_ping_drop_rate)

            if start_counter is not None and start_counter < end_counter:
                # Calculate how many new samples we have
                new_samples = end_counter - start_counter
                if new_samples > total_samples:
                    new_samples = total_samples

                # Get only the new samples (from the end of the arrays)
                start_idx = total_samples - new_samples
            else:
                # Get all samples or requested number
                if samples < 0 or samples > total_samples:
                    start_idx = 0
                else:
                    start_idx = total_samples - samples

            # Extract the requested slice
            ping_drop_rates = list(history.pop_ping_drop_rate[start_idx:])

            general_info = {
                "end_counter": end_counter,
                "samples": len(ping_drop_rates),
            }

            bulk_data = {
                "pop_ping_drop_rate": ping_drop_rates,
            }

            return general_info, bulk_data

        except grpc.RpcError as e:
            logger.error(f"gRPC error fetching history: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching history: {e}")
            raise

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
