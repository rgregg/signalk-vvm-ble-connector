FROM python:3.13.5-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends bluetooth bluez bluez-tools curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

ADD requirements.txt /app
RUN ["pip", "install", "-r", "requirements.txt", "--no-cache-dir"]

COPY vvm_to_signalk/ /app/vvm_to_signalk
ADD entrypoint.sh /app/
RUN ["mkdir", "-p", "/app/logs"]

ENV APP_HEALTHCHECK_ENABLE=True

# Set up healthcheck. Healthy = a fresh "OK" heartbeat (SignalK connected and the
# main loop alive). A device that is simply absent keeps reporting OK and stays
# healthy; only genuine faults (SignalK lost, loop stalled) report unhealthy.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD ["python", "-m", "vvm_to_signalk.healthcheck"]

CMD ["/app/entrypoint.sh"] 