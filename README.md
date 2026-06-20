# Vessel View Mobile to Signal K

This project is a reverse engineering effort for the Mercury Vessel View Mobile application and bluetooth device.
I was looking for an easy way to connect my MerCrusier engine to SignalK so I can bring together all the information
for navigating, performance, and running my boat on one screen.

To achieve this, I'm using the [SignalK server](http://signalk.org) on a Raspberry Pi 4 with this module
running as a docker container and exporting signals to the SignalK API.

**NOTE:** This project is not affiliated with Mercury or MerCruiser.

## Supported Configuration

This connector decodes all SmartCraft parameters streamed by the Vessel View Mobile device and publishes them to SignalK.
It supports up to 4 engines and exposes engine faults as SignalK notifications. The channel map is discovered at runtime.

**Key capabilities:**

- **Multi-engine support**: Handles up to 4 engines with configurable labels (e.g., "port" and "starboard").
- **All SmartCraft parameters**: For full parameter mapping, see [docs/protocol-map.md](docs/protocol-map.md).
- **Engine faults**: Published as SignalK `notifications.propulsion.*` with fault details.
- **Runtime channel discovery**: Automatically maps VVM channels to parameters as they are observed.
- **Configurable engine labels**: Map engine numbers to custom labels in the `signalk.engine-labels` config section.

## Run with Docker

To run, I'm using the docker image - you can also run the 
python script directly using Python3.

The app reads configurmation from `/app/config/vvm_monitor.yaml` which you can map in from a volume mount in Docker. You can 
also configure values through environment variables, or on the command line.

To start the container on a Raspberry Pi or other Linux system:

```bash
docker run  \
  -v /run/dbus/system_bus_socket:/run/dbus/system_bus_socket \
  -v ./config:/app/config \
  rgregg/vvm_monitor:latest
```

You can also provide configuration via environment variables:

```bash
docker run  \
  -e "VVM_DEVICE_ADDRESS=11:22:33:44:55:66" \
  -e "VVM_SIGNALK_URL=ws://127.0.0.1:3000/signalk/v1/stream?subscribe=none" \
  -e "VVM_USERNAME=admin" \
  -e "VVM_PASSWORD=admin" \
  -v /run/dbus/system_bus_socket:/run/dbus/system_bus_socket \
  --network=host \
  --priviledged \
  vvm_monitor
```

### Image tags

Images are published to Docker Hub as [`rgregg/vvm_monitor`](https://hub.docker.com/r/rgregg/vvm_monitor) with the following tags:

| Tag | Points to | Use when you want… |
| --- | --- | --- |
| `latest` | the newest release | the latest stable version |
| `1.2.3` | one exact release | to pin an exact version |
| `1.2` | newest patch of 1.2 | bug-fix updates, no new features |
| `1` | newest 1.x release | feature updates, no breaking changes |
| `edge` | the tip of `main` | the bleeding edge (may be unstable) |
| `pr-<n>` | an open pull request | trying a change before it merges |

For production, pin to a major or major-minor tag (e.g. `rgregg/vvm_monitor:1` or `:1.2`) so you get fixes without surprises. The image also records its version in the standard `org.opencontainers.image.version` label (`docker inspect`).

Releases are cut by pushing a semver git tag (or publishing a GitHub Release):

```bash
git tag v1.2.3 && git push origin v1.2.3
```

### Running as a non-root user

The container runs as an unprivileged user (`vvm`, UID/GID `1000`) rather than root.
Two things to be aware of when deploying:

- **Volume permissions**: any host directory you bind-mount for config or logs
  (e.g. `./config`, `./logs`) must be readable/writable by UID `1000`. If you see
  permission errors writing the log file, run
  `sudo chown -R 1000:1000 ./config ./logs` on the host (or make them
  world-writable).
- **BLE access**: the container does not run its own `bluetoothd`; it talks to the
  host's Bluetooth daemon through the mounted D-Bus socket
  (`/run/dbus/system_bus_socket`). The host's D-Bus policy must allow UID `1000`
  to use `org.bluez`. This works out of the box on most systems. If scanning or
  connecting fails with a D-Bus permission error, add a host D-Bus policy rule for
  that user, or as a fallback run the container as root with `--user 0:0`.

### Example configuration file

Copy the text and place it into a folder which is mapped to `/app/config` in the container.
The filename must be `vvm_monitor.yaml`.

Only the device address or name is required - if you provide both any device that matches either
value will be used.

```yaml
ble-device:
  address: 11:22:33:44:55:66
  name: "VVM 1234123123"
  retry-interval-seconds: 30
  data-recording:
    enabled: true
    file: ./logs/data.csv
    keep: 0
signalk:
  websocket-url: ws://127.0.0.1:3000/signalk/v1/stream?subscribe=none
  username: admin
  password: pass
  retry-interval-seconds: 30
logging:
  level: INFO
  file: ./logs/vvm_monitor.log
  keep: 5
```
