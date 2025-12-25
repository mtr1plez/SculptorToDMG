#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🎬 ================================"
echo "🎬 Sculptor Pro - Full Build Script"
echo "🎬 ================================"
echo ""

# Проверка зависимостей
echo "📋 Checking dependencies..."

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ npm is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All dependencies found${NC}"
echo ""

# 1. Установка Python зависимостей
echo "📦 Step 1: Installing Python dependencies..."
pip3 install -r requirements.txt
pip3 install pyinstaller
echo ""

# 2. Сборка бэкенда
echo "🐍 Step 2: Building backend with PyInstaller..."
python3 build_backend.py

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Backend build failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Backend built successfully${NC}"
echo ""

# 3. Переход в UI и установка зависимостей
echo "⚛️  Step 3: Installing frontend dependencies..."
cd ui
npm install

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ npm install failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# 4. Сборка frontend
echo "🎨 Step 4: Building frontend..."
npm run build

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Frontend build failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Frontend built successfully${NC}"
echo ""

# 5. Сборка Electron приложения
echo "📦 Step 5: Building Electron app..."
npm run build:electron

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Electron build failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Electron app built successfully${NC}"
echo ""

# Готово!
echo "🎉 ================================"
echo "🎉 BUILD COMPLETED SUCCESSFULLY!"
echo "🎉 ================================"
echo ""
echo "📂 Output location: ui/dist/"
echo ""
echo "🚀 You can now distribute your .dmg file!"
echo ""

# Показываем размер файла
if [ -f "dist/*.dmg" ]; then
    DMG_SIZE=$(du -h dist/*.dmg | cut -f1)
    echo "📦 DMG Size: $DMG_SIZE"
fi