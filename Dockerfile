FROM python:3.13.5-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends bluetooth bluez bluez-tools curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Run as an unprivileged user. BLE access is via the host's D-Bus socket
# (mounted at runtime), so the container does not need root or its own
# bluetoothd. The user is added to the bluetooth group as a best effort for
# setups whose D-Bus policy grants access by group.
RUN groupadd --gid 1000 vvm && \
    useradd --uid 1000 --gid 1000 --no-create-home --shell /usr/sbin/nologin vvm && \
    usermod --append --groups bluetooth vvm

WORKDIR /app

ADD requirements.txt /app
RUN ["pip", "install", "-r", "requirements.txt", "--no-cache-dir"]

COPY vvm_to_signalk/ /app/vvm_to_signalk
ADD entrypoint.sh /app/
RUN mkdir -p /app/logs && \
    chmod +x /app/entrypoint.sh && \
    chown -R vvm:vvm /app

ENV APP_HEALTHCHECK_ENABLE=True

# Set up healthcheck. Healthy = a fresh "OK" heartbeat (SignalK connected and the
# main loop alive). A device that is simply absent keeps reporting OK and stays
# healthy; only genuine faults (SignalK lost, loop stalled) report unhealthy.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD ["python", "-m", "vvm_to_signalk.healthcheck"]

USER vvm

CMD ["/app/entrypoint.sh"]
