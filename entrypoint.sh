#!/bin/bash

# BLE access is provided by the host's bluetoothd via the mounted D-Bus socket,
# so the container does not start its own bluetooth service (which would require
# root and contend with the host adapter).

# exec so the application is PID 1 and receives signals directly.
exec python -m vvm_to_signalk
