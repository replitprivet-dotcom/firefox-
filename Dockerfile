FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    firefox-esr \
    xvfb \
    fluxbox \
    x11vnc \
    novnc \
    websockify \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --break-system-packages -r requirements.txt

COPY app.py .

RUN mkdir -p /data /firefox-profile

EXPOSE 8080

CMD ["python3", "app.py"]
