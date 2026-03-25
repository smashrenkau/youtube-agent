FROM python:3.11-slim

# システム依存パッケージ（Playwright + ffmpeg）
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ffmpeg \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pythonパッケージインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright Chromiumインストール
RUN playwright install chromium && playwright install-deps chromium

# アプリコードをコピー
COPY . .

# Streamlit設定ディレクトリを作成
RUN mkdir -p storage/scripts storage/audio storage/videos storage/logs storage/slides

EXPOSE 8501

CMD streamlit run app.py \
    --server.port $PORT \
    --server.headless true \
    --server.address 0.0.0.0 \
    --server.fileWatcherType none
