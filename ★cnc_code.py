# -*- coding: utf-8 -*-
import sys
import os
import webbrowser
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import json
import math
import re

# Fix encoding issues for Japanese Windows systems
if sys.platform.startswith('win'):
    import locale
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='ignore')
        sys.stderr.reconfigure(encoding='utf-8', errors='ignore')
    except:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'ignore')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'ignore')

os.environ['PYTHONIOENCODING'] = 'utf-8'

class MultiOperationCAMParser:
    def __init__(self):
        self.reset()

    def reset(self):
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 0.0
        self.feed_rate = 100.0
        self.commands = []
        self.current_g_mode = 'G01'
        self.is_cutting = False
        self.operations = []
        self.current_operation = []
        self.tool_compensation_active = False

    def parse_gcode(self, gcode_text):
        self.reset()
        lines = gcode_text.split('\n')

        print(f"Processing {len(lines)} lines of multi-operation CAM G-code...")

        processed_lines = 0
        skipped_lines = 0
        valid_commands = 0

        for line_num, line in enumerate(lines, 1):
            try:
                line = line.strip()
                if not line:
                    continue

                processed_lines += 1

                # Skip comments and program headers
                if (line.startswith('(') or line.startswith(';') or
                    line.startswith('N') or line.startswith('%')):
                    skipped_lines += 1
                    continue

                # Process the line
                result = self._parse_line(line, line_num)
                if result:
                    valid_commands += 1

            except Exception as e:
                print(f"Parse error at line {line_num}: {line} - {e}")
                continue

        # Finalize last operation
        if self.current_operation:
            self.operations.append(self.current_operation)

        # Flatten all operations into commands
        self.commands = []
        for op in self.operations:
            self.commands.extend(op)

        print(f"Parsing summary:")
        print(f"- Total lines: {len(lines)}")
        print(f"- Processed lines: {processed_lines}")
        print(f"- Skipped lines: {skipped_lines}")
        print(f"- Valid movement commands: {len(self.commands)}")
        print(f"- Operations detected: {len(self.operations)}")

        if len(self.commands) == 0:
            print("Warning: No movement commands found!")
            print("First 10 lines of input:")
            for i, line in enumerate(lines[:10]):
                print(f"  {i+1}: {line}")

        return self.commands

    def _parse_line(self, line, line_num):
        original_line = line.strip()
        line = line.strip().upper()

        # Handle tool setup and mode commands
        if any(x in line for x in ['G100', 'G56', 'G43', 'M08', 'M30', 'M211', 'M9']):
            return None

        # Handle program headers and comments
        if (line.startswith('(') or line.startswith('N') or
            'PROGRAM' in line or 'ENDMILL' in line):
            return None

        # Detect operation changes (Z movements)
        z_match = re.search(r'Z([-+]?\d*\.?\d+)', line)
        if z_match:
            new_z = float(z_match.group(1))

            # If Z changes significantly, it might be a new operation
            if abs(new_z - self.current_z) > 5:  # 5mm threshold
                # Save current operation if it has content
                if self.current_operation:
                    self.operations.append(self.current_operation)
                    self.current_operation = []

                # Determine if we're cutting or not
                self.is_cutting = new_z < 50  # Assume cutting if Z < 50mm

            self.current_z = new_z

        # Extract G-code command - support both G1 and G01 formats
        gcode = None
        g_match = re.search(r'G(\d+)', line)
        if g_match:
            g_num = int(g_match.group(1))
            if g_num in [0, 1, 2, 3]:
                gcode = f'G{g_num:02d}'  # Convert G1 to G01, etc.
                if gcode in ['G00', 'G01', 'G02', 'G03']:
                    self.current_g_mode = gcode

        # Handle tool compensation
        if 'G42' in line or 'G41' in line:
            self.tool_compensation_active = True
            self.current_g_mode = 'G01'  # Switch to cutting mode
            self.is_cutting = True
        elif 'G40' in line:
            self.tool_compensation_active = False

        # Extract coordinates and arc parameters
        coords = {}
        arc_params = {}

        x_match = re.search(r'X([-+]?\d*\.?\d+)', line)
        if x_match:
            coords['X'] = float(x_match.group(1))

        y_match = re.search(r'Y([-+]?\d*\.?\d+)', line)
        if y_match:
            coords['Y'] = float(y_match.group(1))

        # Arc parameters
        i_match = re.search(r'I([-+]?\d*\.?\d+)', line)
        if i_match:
            arc_params['I'] = float(i_match.group(1))

        j_match = re.search(r'J([-+]?\d*\.?\d+)', line)
        if j_match:
            arc_params['J'] = float(j_match.group(1))

        r_match = re.search(r'R([-+]?\d*\.?\d+)', line)
        if r_match:
            arc_params['R'] = float(r_match.group(1))

        f_match = re.search(r'F(\d+)', line)
        if f_match:
            self.feed_rate = float(f_match.group(1))

        # Extract tool diameter (D parameter)
        d_match = re.search(r'D(\d+)', line)
        tool_diameter = None
        if d_match:
            tool_diameter = float(d_match.group(1))

        # Create movement command if we have coordinates
        if coords and ('X' in coords or 'Y' in coords):
            if not gcode:
                gcode = self.current_g_mode

            # Skip non-movement commands
            if gcode not in ['G00', 'G01', 'G02', 'G03']:
                return None

            new_x = coords.get('X', self.current_x)
            new_y = coords.get('Y', self.current_y)

            # Special handling for G40 - check if it's a cutting move or retract
            if 'G40' in line:
                # If coordinates are very different, it's likely a retract move
                if (abs(new_x - self.current_x) > 10 or abs(new_y - self.current_y) > 10):
                    self.is_cutting = False
                    gcode = 'G00'  # Treat as rapid move

            # Only create command if there's actual XY movement
            if abs(new_x - self.current_x) > 0.001 or abs(new_y - self.current_y) > 0.001:
                cmd = {
                    'type': gcode,
                    'from': {'x': self.current_x, 'y': self.current_y, 'z': self.current_z},
                    'to': {'x': new_x, 'y': new_y, 'z': self.current_z},
                    'feed_rate': self.feed_rate,
                    'i': arc_params.get('I', 0),
                    'j': arc_params.get('J', 0),
                    'r': arc_params.get('R', 0),
                    'line_number': line_num,
                    'original_line': original_line,
                    'is_cutting': self.is_cutting,
                    'operation_id': len(self.operations),
                    'tool_diameter': tool_diameter
                }

                # Add to current operation based on cutting state
                if self.is_cutting or gcode == 'G00':  # Include rapid moves too
                    self.current_operation.append(cmd)

                self.current_x = new_x
                self.current_y = new_y

        return None

# Global parser instance
parser = MultiOperationCAMParser()

COMPLETE_3D_HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3D等角CAM可視化ツール（完全版）</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', 'Yu Gothic', 'Hiragino Sans', sans-serif;
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1600px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #3d4e60 0%, #4a5568 100%);
            color: white;
            padding: 20px 30px;
            text-align: center;
        }

        .header h1 {
            font-size: 2.2em;
            margin-bottom: 8px;
            font-weight: 300;
        }

        .header p {
            opacity: 0.8;
            font-size: 1em;
        }

        .main-content {
            display: grid;
            grid-template-columns: 350px 1fr;
            min-height: 700px;
        }

        .left-panel {
            background: #f8f9fa;
            padding: 25px;
            border-right: 1px solid #e9ecef;
            overflow-y: auto;
            max-height: 700px;
        }

        .input-section {
            margin-bottom: 25px;
        }

        .input-section h3 {
            color: #2c3e50;
            margin-bottom: 12px;
            font-size: 1.2em;
        }

        textarea {
            width: 100%;
            height: 180px;
            padding: 12px;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 10px;
            line-height: 1.2;
            resize: vertical;
            transition: border-color 0.3s ease;
        }

        textarea:focus {
            outline: none;
            border-color: #667eea;
        }

        .controls {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 15px;
        }

        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-align: center;
        }

        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        .btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
        }

        .btn-secondary {
            background: #6c757d;
            color: white;
        }

        .btn-secondary:hover {
            background: #5a6268;
            transform: translateY(-1px);
        }

        .right-panel {
            padding: 25px;
            display: flex;
            flex-direction: column;
        }

        .canvas-container {
            flex: 1;
            border: 2px solid #e9ecef;
            border-radius: 10px;
            position: relative;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            overflow: hidden;
            min-height: 500px;
        }

        #canvas {
            display: block;
            cursor: grab;
        }

        #canvas:active {
            cursor: grabbing;
        }

        .canvas-controls {
            position: absolute;
            top: 10px;
            right: 10px;
            display: flex;
            gap: 5px;
            z-index: 10;
            flex-wrap: wrap;
        }

        .canvas-btn {
            background: rgba(255, 255, 255, 0.95);
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 6px 10px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s ease;
            white-space: nowrap;
        }

        .canvas-btn:hover {
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .canvas-btn.active {
            background: #007bff;
            color: white;
        }

        .view-controls {
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 10px;
            border-radius: 6px;
            font-size: 12px;
            font-family: monospace;
        }

        .view-info {
            margin-bottom: 5px;
        }

        .view-controls button {
            background: rgba(255,255,255,0.2);
            border: 1px solid rgba(255,255,255,0.3);
            color: white;
            padding: 3px 8px;
            margin: 2px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 10px;
        }

        .view-controls button:hover {
            background: rgba(255,255,255,0.3);
        }

        .coordinate-info {
            position: absolute;
            bottom: 150px;
            left: 10px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-family: monospace;
            pointer-events: none;
            z-index: 20;
            display: none;
        }

        .animation-controls {
            position: absolute;
            bottom: 50px;
            left: 10px;
            background: rgba(0, 0, 0, 0.85);
            color: white;
            padding: 12px;
            border-radius: 6px;
            font-size: 11px;
            font-family: monospace;
            display: none;
            min-width: 200px;
            max-width: 280px;
        }

        .animation-progress {
            width: 180px;
            height: 4px;
            background: rgba(255,255,255,0.3);
            border-radius: 2px;
            margin: 5px 0;
            overflow: hidden;
        }

        .animation-progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #00ff00, #ffff00, #ff0000);
            width: 0%;
            transition: width 0.1s ease;
        }

        .animation-controls button {
            background: rgba(255,255,255,0.2);
            border: 1px solid rgba(255,255,255,0.3);
            color: white;
            padding: 3px 6px;
            margin: 1px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 9px;
        }

        .animation-controls button:hover {
            background: rgba(255,255,255,0.4);
        }

        .speed-buttons {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 2px;
            margin: 5px 0;
        }

        .speed-btn {
            background: rgba(255,255,255,0.15);
            border: 1px solid rgba(255,255,255,0.3);
            color: white;
            padding: 4px 6px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 9px;
            font-weight: 600;
            transition: all 0.2s ease;
            text-align: center;
        }

        .speed-btn:hover {
            background: rgba(255,255,255,0.3);
        }

        .speed-btn.active {
            background: #3498db;
            border-color: #2980b9;
            box-shadow: 0 1px 2px rgba(52, 152, 219, 0.3);
        }

        .speed-btn.active:hover {
            background: #2980b9;
        }

        .compact-info {
            font-size: 10px;
            line-height: 1.2;
            margin: 2px 0;
        }

        .info-panel {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
        }

        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 10px;
        }

        .info-item {
            text-align: center;
            padding: 8px;
            background: white;
            border-radius: 6px;
            border: 1px solid #e9ecef;
        }

        .info-item .label {
            color: #6c757d;
            font-size: 11px;
            margin-bottom: 4px;
        }

        .info-item .value {
            color: #2c3e50;
            font-weight: 600;
            font-size: 14px;
        }

        .legend {
            display: flex;
            gap: 15px;
            margin-top: 10px;
            flex-wrap: wrap;
        }

        .legend-item {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
        }

        .legend-color {
            width: 16px;
            min-width: 16px;
            height: 3px;
            border-radius: 2px;
        }

        .error-message {
            background: #f8d7da;
            color: #721c24;
            padding: 10px;
            border-radius: 6px;
            margin-top: 8px;
            border: 1px solid #f5c6cb;
            font-size: 12px;
        }

        .success-message {
            background: #d1edff;
            color: #0c5460;
            padding: 10px;
            border-radius: 6px;
            margin-top: 8px;
            border: 1px solid #bee5eb;
            font-size: 12px;
        }

        .debug-info {
            background: #fff3cd;
            color: #856404;
            padding: 8px;
            border-radius: 4px;
            margin-top: 8px;
            border: 1px solid #ffeaa7;
            font-size: 11px;
            font-family: monospace;
        }

        .zoom-info {
            position: absolute;
            bottom: 10px;
            left: 10px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-family: monospace;
        }

        .operations-info {
            background: #e8f5e8;
            border: 1px solid #c3e6c3;
            border-radius: 6px;
            padding: 10px;
            margin-top: 10px;
            font-size: 11px;
        }

        .operation-item {
            display: flex;
            justify-content: space-between;
            margin: 2px 0;
            padding: 2px 5px;
            background: white;
            border-radius: 3px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 3D等角CAM可視化ツール（完全版）</h1>
            <p>3次元等角投影 - 閃爍問題完全修正</p>
        </div>

        <div class="main-content">
            <div class="left-panel">
                <div class="input-section">
                    <h3>📝 3D CAM G-code</h3>
                    <textarea id="gcodeInput" placeholder="CAMプログラムをここに貼り付けてください...

3D可視化機能：
✓ 等角投影表示
✓ 回転・ズーム操作
✓ Z高度の立体表示
✓ 動畫再生対応
✓ 平移機能（Shift+ドラッグ）
✓ 閃爍問題修正"></textarea>

                    <div class="controls">
                        <button class="btn btn-primary" onclick="parseAndVisualize()">🔧 解析・表示</button>
                        <button class="btn btn-secondary" onclick="clearAll()">🗑️ クリア</button>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr; gap: 5px; margin-top: 10px;">
                        <button class="btn" style="background: #17a2b8; color: white; font-size: 12px;" onclick="testConnection()">🔍 接続テスト</button>
                        <button class="btn" style="background: #28a745; color: white; font-size: 12px;" onclick="loadSampleGCode()">📋 サンプル読込</button>
                    </div>

                    <div id="messageArea"></div>

                    <div class="operations-info" id="operationsInfo" style="display: none;">
                        <div style="font-weight: bold; margin-bottom: 5px;">検出された操作:</div>
                        <div id="operationsList"></div>
                    </div>
                </div>

                <div class="info-panel">
                    <div class="info-grid">
                        <div class="info-item">
                            <div class="label">総指令数</div>
                            <div class="value" id="totalCommands">0</div>
                        </div>
                        <div class="info-item">
                            <div class="label">操作数</div>
                            <div class="value" id="operationCount">0</div>
                        </div>
                        <div class="info-item">
                            <div class="label">距離 (mm)</div>
                            <div class="value" id="totalDistance">0</div>
                        </div>
                        <div class="info-item">
                            <div class="label">3D範囲</div>
                            <div class="value" id="workVolume">--</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="right-panel">
                <div class="canvas-container">
                    <canvas id="canvas" width="1000" height="600"></canvas>
                    <div class="view-controls">
                        <div class="view-info">3D視点制御</div>
                        <div>回転: <span id="rotationX">30</span>°, <span id="rotationY">45</span>°</div>
                        <div>ズーム: <span id="zoomLevel">100</span>%</div>
                        <div>
                            <button onclick="resetView3D()">リセット</button>
                            <button onclick="viewTop()">上面</button>
                            <button onclick="viewFront()">正面</button>
                            <button onclick="viewRight()">右面</button>
                            <button onclick="viewIsometric()">等角</button>
                        </div>
                    </div>
                    <div class="coordinate-info" id="coordinateInfo">
                        <div>3D座標: X0.000, Y0.000, Z0.000</div>
                        <div>指令: G01</div>
                        <div>操作: #1</div>
                    </div>
                    <div class="animation-controls" id="animationControls">
                        <div style="font-weight: bold; margin-bottom: 5px; font-size: 10px;">3D CAM動畫</div>
                        <div class="compact-info">進度: <span id="animationProgress">0</span>/<span id="animationTotal">0</span></div>
                        <div class="animation-progress">
                            <div class="animation-progress-bar" id="progressBar"></div>
                        </div>
                        <div class="compact-info">座標: X<span id="currentX">0.00</span>, Y<span id="currentY">0.00</span>, Z<span id="currentZ">0.00</span></div>
                        <div class="compact-info">操作: <span id="currentOperation">#1</span> | 指令: <span id="currentCommand">G01</span></div>
                        <div style="margin-top: 6px;">
                            <div style="margin-bottom: 3px; font-size: 9px;">速度:</div>
                            <div class="speed-buttons">
                                <button onclick="setAnimationSpeed(0.25)" class="speed-btn" data-speed="0.25">0.25x</button>
                                <button onclick="setAnimationSpeed(0.5)" class="speed-btn" data-speed="0.5">0.5x</button>
                                <button onclick="setAnimationSpeed(1)" class="speed-btn active" data-speed="1">1x</button>
                                <button onclick="setAnimationSpeed(2)" class="speed-btn" data-speed="2">2x</button>
                                <button onclick="setAnimationSpeed(4)" class="speed-btn" data-speed="4">4x</button>
                                <button onclick="setAnimationSpeed(8)" class="speed-btn" data-speed="8">8x</button>
                                <button onclick="setAnimationSpeed(16)" class="speed-btn" data-speed="16">16x</button>
                            </div>
                            <div style="margin-top: 4px; text-align: center;">
                                <button onclick="pauseAnimation()" id="pauseBtn">一時停止</button>
                            </div>
                        </div>
                    </div>
                    <div class="canvas-controls">
                        <button class="canvas-btn" onclick="toggleGrid()">📐 グリッド</button>
                        <button class="canvas-btn" onclick="toggleAxes()">🔄 軸表示</button>
                        <button class="canvas-btn" onclick="zoomIn3D()">🔍+ 拡大</button>
                        <button class="canvas-btn" onclick="zoomOut3D()">🔍- 縮小</button>
                        <button class="canvas-btn" onclick="fitToView3D()">📐 全体表示</button>
                        <button class="canvas-btn" onclick="toggleAnimation()" id="animationBtn">▶️ 動畫開始</button>
                    </div>
                    <div class="zoom-info" id="zoomInfo">3D ズーム: 100%</div>
                </div>

                <div class="legend">
                    <div class="legend-item">
                        <div class="legend-color" style="background: #e74c3c; min-width: 16px; height: 3px;"></div>
                        <span>早送り (G00)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background: #3498db; min-width: 16px; height: 3px;"></div>
                        <span>送り (G01)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background: #f39c12; min-width: 16px; height: 3px;"></div>
                        <span>CW圆弧 (G02)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background: #9b59b6; min-width: 16px; height: 3px;"></div>
                        <span>CCW圆弧 (G03)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background: #27ae60; min-width: 16px; height: 3px;"></div>
                        <span>工具位置</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Global variables
        let canvas, ctx;
        let currentCommands = [];
        let operations = [];

        // 3D view parameters
        let rotationX = 30;  // degrees
        let rotationY = 45;  // degrees
        let zoom3D = 1.0;
        let offsetX = 0, offsetY = 0;
        let showGrid = true;
        let showAxes = true;

        // Interaction
        let isDragging = false;
        let lastMouseX, lastMouseY;

        // Animation
        let isAnimating = false;
        let animationFrame = 0;
        let animationInterval = null;
        let drawnCommands = [];
        let toolPosition = { x: 0, y: 0, z: 0 };
        let animationSpeed = 1;
        let animationPaused = false;

        // Initialize when page loads
        window.addEventListener('load', function() {
            console.log('Page loaded, initializing...');
            canvas = document.getElementById('canvas');
            ctx = canvas.getContext('2d');
            setupCanvasInteraction();
            setupKeyboardControls();
            resetView3D();
            showMessage('3D等角CAM可視化ツール準備完了！\\nShift+ドラッグで平移、矢印キーでも平移可能です。', 'success');
        });

        function setupCanvasInteraction() {
            canvas.addEventListener('mousedown', startDrag);
            canvas.addEventListener('mousemove', handleMouseMove);
            canvas.addEventListener('mouseup', stopDrag);
            canvas.addEventListener('wheel', handleWheel);
            canvas.addEventListener('mouseleave', stopDrag);
        }

        function startDrag(e) {
            isDragging = true;
            lastMouseX = e.clientX;
            lastMouseY = e.clientY;
            canvas.style.cursor = 'grabbing';
        }

        function handleMouseMove(e) {
            if (isDragging) {
                const deltaX = e.clientX - lastMouseX;
                const deltaY = e.clientY - lastMouseY;

                if (e.shiftKey) {
                    // Shift key held - Pan the view
                    offsetX += deltaX;
                    offsetY += deltaY;
                } else {
                    // Normal drag - Rotate the 3D view
                    rotationY += deltaX * 0.5;
                    rotationX += deltaY * 0.5;

                    // Constrain rotationX
                    rotationX = Math.max(-90, Math.min(90, rotationX));
                    updateRotationDisplay();
                }

                lastMouseX = e.clientX;
                lastMouseY = e.clientY;

                redraw3D();
            }
        }

        function stopDrag() {
            isDragging = false;
            canvas.style.cursor = 'grab';
        }

        function handleWheel(e) {
            e.preventDefault();
            const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
            zoom3D *= zoomFactor;
            zoom3D = Math.max(0.1, Math.min(10, zoom3D));

            updateZoomDisplay();
            redraw3D();
        }

        // Add keyboard support for panning
        function setupKeyboardControls() {
            document.addEventListener('keydown', function(e) {
                const panStep = 10;
                let needsRedraw = false;

                switch(e.key) {
                    case 'ArrowLeft':
                        offsetX -= panStep;
                        needsRedraw = true;
                        e.preventDefault();
                        break;
                    case 'ArrowRight':
                        offsetX += panStep;
                        needsRedraw = true;
                        e.preventDefault();
                        break;
                    case 'ArrowUp':
                        offsetY -= panStep;
                        needsRedraw = true;
                        e.preventDefault();
                        break;
                    case 'ArrowDown':
                        offsetY += panStep;
                        needsRedraw = true;
                        e.preventDefault();
                        break;
                }

                if (needsRedraw) {
                    redraw3D();
                }
            });
        }

        function updateRotationDisplay() {
            document.getElementById('rotationX').textContent = Math.round(rotationX);
            document.getElementById('rotationY').textContent = Math.round(rotationY);
        }

        function updateZoomDisplay() {
            document.getElementById('zoomLevel').textContent = Math.round(zoom3D * 100);
            document.getElementById('zoomInfo').textContent = `3D ズーム: ${Math.round(zoom3D * 100)}%`;
        }

        // 3D transformation functions
        function project3D(x, y, z) {
            // Apply 3D transformations
            const radX = rotationX * Math.PI / 180;
            const radY = rotationY * Math.PI / 180;

            // Rotate around Y axis
            const cosY = Math.cos(radY);
            const sinY = Math.sin(radY);
            const x1 = x * cosY - z * sinY;
            const z1 = x * sinY + z * cosY;

            // Rotate around X axis
            const cosX = Math.cos(radX);
            const sinX = Math.sin(radX);
            const y1 = y * cosX - z1 * sinX;
            const z2 = y * sinX + z1 * cosX;

            // Apply zoom and offset
            const scale = zoom3D * 3;  // Base scale factor
            const screenX = canvas.width / 2 + x1 * scale + offsetX;
            const screenY = canvas.height / 2 - y1 * scale + offsetY;

            return { x: screenX, y: screenY, z: z2 };
        }

        function parseAndVisualize() {
            console.log('parseAndVisualize function called');

            const gcode = document.getElementById('gcodeInput').value.trim();
            console.log('Input G-code length:', gcode.length);
            console.log('First 100 characters:', gcode.substring(0, 100));

            if (!gcode) {
                showMessage('CAM G-codeを入力してください。', 'error');
                return;
            }

            // Show immediate feedback
            showMessage('🔄 解析開始中...', 'info');
            console.log('Starting parse process...');

            try {
                console.log('Sending request to server...');

                fetch('/parse', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({gcode: gcode})
                })
                .then(response => {
                    console.log('Response received:', response.status, response.statusText);
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(result => {
                    console.log('Parsing result:', result);

                    if (result.error) {
                        showMessage('解析エラー: ' + result.error, 'error');
                        console.error('Parsing error:', result.error);
                    } else {
                        currentCommands = result.commands;
                        console.log('Parsed commands count:', currentCommands.length);

                        if (currentCommands.length > 0) {
                            console.log('Visualizing 3D...');

                            // Update UI once and prevent flickering
                            updateUIOnce();

                            showMessage(`✅ ${currentCommands.length}個のCAM指令を3D表示しました！`, 'success');

                            const totalLines = gcode.split('\\n').length;
                            const debugInfo = `${totalLines}行を処理 → ${currentCommands.length}個の3D移動指令を検出`;
                            document.getElementById('messageArea').innerHTML +=
                                '<div class="debug-info">' + debugInfo + '</div>';

                            // Show first few commands for debugging
                            if (currentCommands.length > 0) {
                                console.log('First command:', currentCommands[0]);
                                console.log('Last command:', currentCommands[currentCommands.length - 1]);
                            }
                        } else {
                            showMessage('❌ 移動指令が見つかりません。\\n\\n調試資訊：\\n- 入力行数: ' + gcode.split('\\n').length + '\\n- 解析結果: 0個移動指令\\n\\nConsoleでより詳細な情報を確認してください。', 'error');
                            console.log('No movement commands found in G-code');
                            console.log('Input lines:', gcode.split('\\n').length);
                            console.log('First 5 lines:', gcode.split('\\n').slice(0, 5));

                            // Show more detailed analysis
                            const lines = gcode.split('\\n');
                            let gCodeLines = 0;
                            let movementLines = 0;

                            lines.forEach((line, index) => {
                                const trimmed = line.trim().toUpperCase();
                                if (trimmed.match(/G[0-9]/)) gCodeLines++;
                                if (trimmed.match(/G0[0-3]/)) movementLines++;
                                if (index < 10) console.log(`Line ${index + 1}: "${line}"`);
                            });

                            console.log(`Analysis: ${gCodeLines} G-code lines, ${movementLines} potential movement lines`);
                        }
                    }
                })
                .catch(error => {
                    console.error('Fetch error:', error);
                    showMessage('❌ 通信エラー: ' + error.message + '\\n\\nサーバーが起動していることを確認してください。\\nConsoleで詳細なエラーを確認してください。', 'error');
                });

            } catch (error) {
                console.error('Parse error:', error);
                showMessage('❌ 予期しないエラー: ' + error.message, 'error');
            }
        }

        // Consolidated UI update function to prevent flickering
        function updateUIOnce() {
            if (currentCommands.length === 0) return;

            console.log('Updating UI once to prevent flickering...');

            // 1. Update 3D visualization
            visualize3D();

            // 2. Update statistics
            updateStatisticsOnce();

            // 3. Update operations info
            updateOperationsInfoOnce();
        }

        function updateStatisticsOnce() {
            console.log('Updating statistics once...');

            let totalDistance = 0;
            let minX = Infinity, maxX = -Infinity;
            let minY = Infinity, maxY = -Infinity;
            let minZ = Infinity, maxZ = -Infinity;

            for (let cmd of currentCommands) {
                const dx = cmd.to.x - cmd.from.x;
                const dy = cmd.to.y - cmd.from.y;
                const dz = cmd.to.z - cmd.from.z;
                const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
                totalDistance += distance;

                minX = Math.min(minX, cmd.from.x, cmd.to.x);
                maxX = Math.max(maxX, cmd.from.x, cmd.to.x);
                minY = Math.min(minY, cmd.from.y, cmd.to.y);
                maxY = Math.max(maxY, cmd.from.y, cmd.to.y);
                minZ = Math.min(minZ, cmd.from.z, cmd.to.z);
                maxZ = Math.max(maxZ, cmd.from.z, cmd.to.z);
            }

            // Update all elements at once to prevent flickering
            const updates = {
                'totalCommands': currentCommands.length.toString(),
                'totalDistance': totalDistance.toFixed(2),
                'workVolume': isFinite(minX) ? `${(maxX-minX).toFixed(1)}×${(maxY-minY).toFixed(1)}×${(maxZ-minZ).toFixed(1)}mm` : '--'
            };

            // Apply all updates in a single operation
            Object.keys(updates).forEach(id => {
                const element = document.getElementById(id);
                if (element && element.textContent !== updates[id]) {
                    element.textContent = updates[id];
                }
            });
        }

        function updateOperationsInfoOnce() {
            console.log('Updating operations info once...');

            const ops = {};
            for (let cmd of currentCommands) {
                const opId = cmd.operation_id;
                if (!ops[opId]) {
                    ops[opId] = 0;
                }
                ops[opId]++;
            }

            const operationCount = Object.keys(ops).length;

            let operationsHtml = '';
            for (let opId in ops) {
                operationsHtml += `
                    <div class="operation-item">
                        <span>操作 #${parseInt(opId) + 1}</span>
                        <span>${ops[opId]}指令</span>
                    </div>
                `;
            }

            // Update all operations info at once
            const operationCountElement = document.getElementById('operationCount');
            const operationsListElement = document.getElementById('operationsList');
            const operationsInfoElement = document.getElementById('operationsInfo');

            if (operationCountElement) {
                operationCountElement.textContent = operationCount.toString();
            }

            if (operationsListElement) {
                operationsListElement.innerHTML = operationsHtml;
            }

            if (operationsInfoElement) {
                operationsInfoElement.style.display = 'block';
            }
        }

        // Legacy functions - now replaced by updateUIOnce to prevent flickering
        function updateOperationsInfo() {
            // This function is replaced by updateOperationsInfoOnce
            // to prevent flickering issues
            console.log('updateOperationsInfo called - using updateOperationsInfoOnce instead');
            updateOperationsInfoOnce();
        }

        function updateStatistics() {
            // This function is replaced by updateStatisticsOnce
            // to prevent flickering issues
            console.log('updateStatistics called - using updateStatisticsOnce instead');
            updateStatisticsOnce();
        }

        function visualize3D() {
            if (currentCommands.length === 0) return;

            fitToView3D();
            redraw3D();
        }

        function redraw3D() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            if (showGrid) drawGrid3D();
            if (showAxes) drawAxes3D();

            draw3DPaths();
        }

        function drawGrid3D() {
            ctx.save();
            ctx.strokeStyle = 'rgba(200, 200, 200, 0.3)';
            ctx.lineWidth = 1;

            const gridSize = 20;
            const gridExtent = 100;

            // Draw XY grid at Z=0
            for (let x = -gridExtent; x <= gridExtent; x += gridSize) {
                const start = project3D(x, -gridExtent, 0);
                const end = project3D(x, gridExtent, 0);

                ctx.beginPath();
                ctx.moveTo(start.x, start.y);
                ctx.lineTo(end.x, end.y);
                ctx.stroke();
            }

            for (let y = -gridExtent; y <= gridExtent; y += gridSize) {
                const start = project3D(-gridExtent, y, 0);
                const end = project3D(gridExtent, y, 0);

                ctx.beginPath();
                ctx.moveTo(start.x, start.y);
                ctx.lineTo(end.x, end.y);
                ctx.stroke();
            }

            ctx.restore();
        }

        function drawAxes3D() {
            ctx.save();
            ctx.lineWidth = 3;

            const origin = project3D(0, 0, 0);
            const axisLength = 50;

            // X axis - Red
            ctx.strokeStyle = '#e74c3c';
            ctx.beginPath();
            const xEnd = project3D(axisLength, 0, 0);
            ctx.moveTo(origin.x, origin.y);
            ctx.lineTo(xEnd.x, xEnd.y);
            ctx.stroke();

            // Y axis - Green
            ctx.strokeStyle = '#27ae60';
            ctx.beginPath();
            const yEnd = project3D(0, axisLength, 0);
            ctx.moveTo(origin.x, origin.y);
            ctx.lineTo(yEnd.x, yEnd.y);
            ctx.stroke();

            // Z axis - Blue
            ctx.strokeStyle = '#3498db';
            ctx.beginPath();
            const zEnd = project3D(0, 0, axisLength);
            ctx.moveTo(origin.x, origin.y);
            ctx.lineTo(zEnd.x, zEnd.y);
            ctx.stroke();

            // Axis labels
            ctx.fillStyle = '#2c3e50';
            ctx.font = '14px Arial';
            ctx.fillText('X', xEnd.x + 5, xEnd.y);
            ctx.fillText('Y', yEnd.x + 5, yEnd.y);
            ctx.fillText('Z', zEnd.x + 5, zEnd.y);

            ctx.restore();
        }

        function draw3DPaths() {
            if (currentCommands.length === 0) return;

            const commandsToDraw = isAnimating ? drawnCommands : currentCommands;
            const operationColors = ['#3498db', '#e74c3c', '#f39c12', '#9b59b6', '#1abc9c', '#95a5a6'];

            ctx.save();
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';

            // Draw start point with Z height indication
            if (currentCommands.length > 0) {
                const start = currentCommands[0].from;
                const startProj = project3D(start.x, start.y, start.z);

                // Draw vertical line to show Z height
                if (start.z !== 0) {
                    const baseProj = project3D(start.x, start.y, 0);
                    ctx.strokeStyle = 'rgba(39, 174, 96, 0.5)';
                    ctx.lineWidth = 2;
                    ctx.setLineDash([4, 4]);
                    ctx.beginPath();
                    ctx.moveTo(baseProj.x, baseProj.y);
                    ctx.lineTo(startProj.x, startProj.y);
                    ctx.stroke();
                    ctx.setLineDash([]);
                }

                ctx.fillStyle = '#27ae60';
                ctx.beginPath();
                ctx.arc(startProj.x, startProj.y, 6, 0, Math.PI * 2);
                ctx.fill();

                ctx.strokeStyle = 'white';
                ctx.lineWidth = 2;
                ctx.stroke();

                // Label start point
                ctx.fillStyle = '#2c3e50';
                ctx.font = '12px Arial';
                ctx.fillText(`START Z${start.z.toFixed(1)}`, startProj.x + 10, startProj.y - 10);
            }

            // Group commands by Z height for better visualization
            const zLevels = {};
            for (let cmd of commandsToDraw) {
                const zKey = cmd.from.z.toFixed(1);
                if (!zLevels[zKey]) zLevels[zKey] = [];
                zLevels[zKey].push(cmd);
            }

            // Draw paths grouped by Z level
            Object.keys(zLevels).sort((a, b) => parseFloat(b) - parseFloat(a)).forEach((zKey, levelIndex) => {
                const commands = zLevels[zKey];
                const zValue = parseFloat(zKey);

                // Draw level indicator
                if (commands.length > 0) {
                    const firstCmd = commands[0];
                    const levelProj = project3D(0, 0, zValue);

                    ctx.fillStyle = `hsla(${120 + levelIndex * 60}, 70%, 50%, 0.8)`;
                    ctx.font = '10px Arial';
                    ctx.fillText(`Z${zKey}`, 10, levelProj.y);
                }

                // Draw commands at this Z level
                for (let cmd of commands) {
                    const opColor = operationColors[cmd.operation_id % operationColors.length];

                    // Adjust color intensity based on Z height
                    const zIntensity = Math.max(0.4, 1 - Math.abs(zValue) / 100);

                    switch (cmd.type) {
                        case 'G00':
                            ctx.strokeStyle = `rgba(231, 76, 60, ${zIntensity})`;
                            ctx.lineWidth = 2;
                            ctx.setLineDash([6, 6]);
                            break;
                        case 'G01':
                            // Parse RGB from hex color
                            const r = parseInt(opColor.substr(1,2), 16);
                            const g = parseInt(opColor.substr(3,2), 16);
                            const b = parseInt(opColor.substr(5,2), 16);
                            ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${zIntensity})`;
                            ctx.lineWidth = Math.max(2, 4 - Math.abs(zValue) / 50);
                            ctx.setLineDash([]);
                            break;
                        case 'G02':
                            ctx.strokeStyle = `rgba(243, 156, 18, ${zIntensity})`;
                            ctx.lineWidth = Math.max(3, 5 - Math.abs(zValue) / 50);
                            ctx.setLineDash([]);
                            break;
                        case 'G03':
                            ctx.strokeStyle = `rgba(155, 89, 182, ${zIntensity})`;
                            ctx.lineWidth = Math.max(3, 5 - Math.abs(zValue) / 50);
                            ctx.setLineDash([]);
                            break;
                    }

                    const fromProj = project3D(cmd.from.x, cmd.from.y, cmd.from.z);
                    const toProj = project3D(cmd.to.x, cmd.to.y, cmd.to.z);

                    ctx.beginPath();

                    if (cmd.type === 'G02' || cmd.type === 'G03') {
                        // For arcs, draw multiple line segments for 3D appearance
                        draw3DArc(cmd);
                    } else {
                        // Straight line with Z height consideration
                        ctx.moveTo(fromProj.x, fromProj.y);
                        ctx.lineTo(toProj.x, toProj.y);

                        // Draw Z height change indicators
                        if (Math.abs(cmd.to.z - cmd.from.z) > 0.1) {
                            // Z axis movement - draw with different style
                            ctx.strokeStyle = '#e67e22';
                            ctx.lineWidth = 4;
                            ctx.setLineDash([8, 4]);
                        }
                    }

                    ctx.stroke();

                    // Draw Z level indicators at significant points
                    if (Math.abs(cmd.to.z - cmd.from.z) > 5) {
                        ctx.fillStyle = '#e67e22';
                        ctx.font = '10px Arial';
                        ctx.fillText(`Z${cmd.to.z.toFixed(1)}`, toProj.x + 5, toProj.y - 5);
                    }
                }
            });

            // Draw tool position during animation with enhanced Z visualization
            if (isAnimating && toolPosition) {
                const toolProj = project3D(toolPosition.x, toolPosition.y, toolPosition.z);

                // Draw vertical line from base to tool position
                const toolBaseProj = project3D(toolPosition.x, toolPosition.y, 0);
                ctx.strokeStyle = 'rgba(255, 107, 107, 0.6)';
                ctx.lineWidth = 3;
                ctx.setLineDash([6, 6]);
                ctx.beginPath();
                ctx.moveTo(toolBaseProj.x, toolBaseProj.y);
                ctx.lineTo(toolProj.x, toolProj.y);
                ctx.stroke();
                ctx.setLineDash([]);

                // Tool position marker
                ctx.fillStyle = '#ff6b6b';
                ctx.strokeStyle = '#ff4757';
                ctx.lineWidth = 3;

                ctx.beginPath();
                ctx.arc(toolProj.x, toolProj.y, 8, 0, Math.PI * 2);
                ctx.fill();
                ctx.stroke();

                // Tool glow effect
                ctx.fillStyle = 'rgba(255, 107, 107, 0.3)';
                ctx.beginPath();
                ctx.arc(toolProj.x, toolProj.y, 15, 0, Math.PI * 2);
                ctx.fill();

                // Z height label for tool
                ctx.fillStyle = '#2c3e50';
                ctx.font = 'bold 12px Arial';
                ctx.fillText(`TOOL Z${toolPosition.z.toFixed(1)}`, toolProj.x + 12, toolProj.y - 12);

                // Base position marker
                ctx.fillStyle = 'rgba(255, 107, 107, 0.4)';
                ctx.beginPath();
                ctx.arc(toolBaseProj.x, toolBaseProj.y, 4, 0, Math.PI * 2);
                ctx.fill();
            }

            ctx.restore();
        }

        function draw3DArc(cmd) {
            // Approximate arc with line segments for 3D display
            const segments = 16;

            for (let i = 0; i < segments; i++) {
                const t1 = i / segments;
                const t2 = (i + 1) / segments;

                const x1 = cmd.from.x + t1 * (cmd.to.x - cmd.from.x);
                const y1 = cmd.from.y + t1 * (cmd.to.y - cmd.from.y);
                const z1 = cmd.from.z;

                const x2 = cmd.from.x + t2 * (cmd.to.x - cmd.from.x);
                const y2 = cmd.from.y + t2 * (cmd.to.y - cmd.from.y);
                const z2 = cmd.from.z;

                const proj1 = project3D(x1, y1, z1);
                const proj2 = project3D(x2, y2, z2);

                if (i === 0) {
                    ctx.moveTo(proj1.x, proj1.y);
                } else {
                    ctx.lineTo(proj1.x, proj1.y);
                }
                ctx.lineTo(proj2.x, proj2.y);
            }
        }

        // View control functions
        function resetView3D() {
            rotationX = 30;
            rotationY = 45;
            zoom3D = 1.0;
            offsetX = 0;
            offsetY = 0;
            updateRotationDisplay();
            updateZoomDisplay();
            redraw3D();
        }

        function viewTop() {
            rotationX = 90;
            rotationY = 0;
            updateRotationDisplay();
            redraw3D();
        }

        function viewFront() {
            rotationX = 0;
            rotationY = 0;
            updateRotationDisplay();
            redraw3D();
        }

        function viewRight() {
            rotationX = 0;
            rotationY = 90;
            updateRotationDisplay();
            redraw3D();
        }

        function viewIsometric() {
            rotationX = 30;
            rotationY = 45;
            updateRotationDisplay();
            redraw3D();
        }

        function zoomIn3D() {
            zoom3D *= 1.25;
            updateZoomDisplay();
            redraw3D();
        }

        function zoomOut3D() {
            zoom3D *= 0.8;
            updateZoomDisplay();
            redraw3D();
        }

        function fitToView3D() {
            if (currentCommands.length === 0) return;

            let minX = Infinity, maxX = -Infinity;
            let minY = Infinity, maxY = -Infinity;
            let minZ = Infinity, maxZ = -Infinity;

            for (let cmd of currentCommands) {
                minX = Math.min(minX, cmd.from.x, cmd.to.x);
                maxX = Math.max(maxX, cmd.from.x, cmd.to.x);
                minY = Math.min(minY, cmd.from.y, cmd.to.y);
                maxY = Math.max(maxY, cmd.from.y, cmd.to.y);
                minZ = Math.min(minZ, cmd.from.z, cmd.to.z);
                maxZ = Math.max(maxZ, cmd.from.z, cmd.to.z);
            }

            if (!isFinite(minX)) return;

            const rangeX = maxX - minX || 1;
            const rangeY = maxY - minY || 1;
            const rangeZ = maxZ - minZ || 1;
            const maxRange = Math.max(rangeX, rangeY, rangeZ);

            zoom3D = Math.min(canvas.width, canvas.height) * 0.6 / maxRange;
            offsetX = 0;
            offsetY = 0;

            updateZoomDisplay();
            redraw3D();
        }

        function toggleGrid() {
            showGrid = !showGrid;
            redraw3D();
        }

        function toggleAxes() {
            showAxes = !showAxes;
            redraw3D();
        }

        function toggleAnimation() {
            if (currentCommands.length === 0) {
                showMessage('動畫を開始するにはまずG-codeを解析してください。', 'error');
                return;
            }

            if (isAnimating) {
                stopAnimation();
            } else {
                startAnimation();
            }
        }

        function setAnimationSpeed(speed) {
            animationSpeed = speed;

            // Update button states
            document.querySelectorAll('.speed-btn').forEach(btn => {
                btn.classList.remove('active');
                if (parseFloat(btn.dataset.speed) === speed) {
                    btn.classList.add('active');
                }
            });

            // Update animation interval if currently running
            if (isAnimating && !animationPaused) {
                clearInterval(animationInterval);
                const interval = Math.max(25, 200 / animationSpeed);
                animationInterval = setInterval(animateStep, interval);
            }

            showMessage(`動畫速度を${speed}xに設定しました。`, 'info');
        }

        function startAnimation() {
            isAnimating = true;
            animationPaused = false;
            animationFrame = 0;
            drawnCommands = [];

            if (currentCommands.length > 0) {
                toolPosition = {
                    x: currentCommands[0].from.x,
                    y: currentCommands[0].from.y,
                    z: currentCommands[0].from.z
                };
            }

            document.getElementById('animationBtn').textContent = '⏸️ 停止';
            document.getElementById('animationBtn').classList.add('active');
            document.getElementById('animationControls').style.display = 'block';
            document.getElementById('animationTotal').textContent = currentCommands.length;

            // Reset pause button
            document.getElementById('pauseBtn').textContent = '一時停止';

            // Set initial speed button state
            setAnimationSpeed(1); // Default to 1x speed

            const interval = Math.max(25, 200 / animationSpeed);
            animationInterval = setInterval(animateStep, interval);
            showMessage('3D CAM動畫を開始しました。直接速度ボタンをクリックして調整できます。', 'success');
        }

        function stopAnimation() {
            isAnimating = false;
            animationPaused = false;

            if (animationInterval) {
                clearInterval(animationInterval);
                animationInterval = null;
            }

            document.getElementById('animationBtn').textContent = '▶️ 動畫開始';
            document.getElementById('animationBtn').classList.remove('active');
            document.getElementById('animationControls').style.display = 'none';

            drawnCommands = currentCommands.slice();
            redraw3D();

            showMessage('3D CAM動畫を停止しました。', 'info');
        }

        function pauseAnimation() {
            if (!isAnimating) return;

            if (animationPaused) {
                // Resume
                animationPaused = false;
                const interval = Math.max(25, 200 / animationSpeed);
                animationInterval = setInterval(animateStep, interval);
                document.getElementById('pauseBtn').textContent = '一時停止';
                showMessage('動畫を再開しました。', 'info');
            } else {
                // Pause
                animationPaused = true;
                if (animationInterval) {
                    clearInterval(animationInterval);
                    animationInterval = null;
                }
                document.getElementById('pauseBtn').textContent = '再開';
                showMessage('動畫を一時停止しました。', 'info');
            }
        }

        function animateStep() {
            if (animationFrame >= currentCommands.length) {
                stopAnimation();
                showMessage('3D CAM動畫が完了しました！', 'success');
                return;
            }

            const cmd = currentCommands[animationFrame];
            drawnCommands.push(cmd);

            toolPosition.x = cmd.to.x;
            toolPosition.y = cmd.to.y;
            toolPosition.z = cmd.to.z;

            // Update animation progress display with reduced precision to prevent jumping
            document.getElementById('animationProgress').textContent = animationFrame + 1;
            document.getElementById('currentX').textContent = cmd.to.x.toFixed(2);
            document.getElementById('currentY').textContent = cmd.to.y.toFixed(2);
            document.getElementById('currentZ').textContent = cmd.to.z.toFixed(2);
            document.getElementById('currentOperation').textContent = `#${cmd.operation_id + 1}`;
            document.getElementById('currentCommand').textContent = cmd.type;

            const progress = ((animationFrame + 1) / currentCommands.length) * 100;
            document.getElementById('progressBar').style.width = progress + '%';

            animationFrame++;
            redraw3D();
        }

        function clearAll() {
            console.log('clearAll called');
            if (isAnimating) {
                stopAnimation();
            }

            document.getElementById('gcodeInput').value = '';
            currentCommands = [];
            drawnCommands = [];
            animationFrame = 0;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            resetView3D();

            // Clear statistics without causing flickering
            clearStatistics();

            document.getElementById('operationsInfo').style.display = 'none';
            showMessage('すべてのコンテンツをクリアしました。', 'info');
        }

        function clearStatistics() {
            // Clear all statistics at once to prevent flickering
            const updates = {
                'totalCommands': '0',
                'operationCount': '0',
                'totalDistance': '0',
                'workVolume': '--'
            };

            Object.keys(updates).forEach(id => {
                const element = document.getElementById(id);
                if (element) {
                    element.textContent = updates[id];
                }
            });
        }

        function testConnection() {
            console.log('testConnection called');
            showMessage('サーバー接続をテスト中...', 'info');

            fetch('/parse', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({gcode: 'G01 X10 Y10'})
            })
            .then(response => {
                console.log('Test response:', response.status);
                if (response.ok) {
                    return response.json();
                } else {
                    throw new Error(`HTTP ${response.status}`);
                }
            })
            .then(result => {
                console.log('Test result:', result);
                showMessage('✅ サーバー接続正常！テスト解析成功しました。', 'success');
            })
            .catch(error => {
                console.error('Test failed:', error);
                showMessage('❌ サーバーに接続できません: ' + error.message, 'error');
            });
        }

        function loadSampleGCode() {
            console.log('loadSampleGCode called');
            const sampleGCode = `G01 X1 Y1 Z0.5 F500
G01 X10 Y1
G01 X10 Y10
G01 X1 Y10
G01 X1 Y1
G02 X5 Y5 R5
G03 X8 Y8 R3
G01 X0 Y0
G00 Z50`;

            document.getElementById('gcodeInput').value = sampleGCode;
            showMessage('サンプルG-codeを読み込みました。解析ボタンを押してください。', 'success');
        }

        function showMessage(message, type) {
            const messageArea = document.getElementById('messageArea');
            let className = 'success-message';

            if (type === 'error') {
                className = 'error-message';
            } else if (type === 'info') {
                className = 'success-message';
            }

            messageArea.innerHTML = `<div class="${className}">${message}</div>`;

            if (type !== 'error') {
                setTimeout(() => {
                    const debugElements = messageArea.querySelectorAll('.debug-info');
                    if (debugElements.length === 0) {
                        messageArea.innerHTML = '';
                    }
                }, 8000);
            }
        }
    </script>
</body>
</html>'''

class CNCRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(COMPLETE_3D_HTML_TEMPLATE.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/parse':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                gcode = data.get('gcode', '')
                commands = parser.parse_gcode(gcode)

                response = {
                    'commands': commands,
                    'error': None
                }

                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))

            except Exception as e:
                response = {
                    'commands': [],
                    'error': str(e)
                }

                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def start_server():
    port = 8080
    server_address = ('localhost', port)

    try:
        httpd = HTTPServer(server_address, CNCRequestHandler)
        print(f"🎯 3D等角CAM可視化ツール（完全版）開始中...")
        print(f"✅ JavaScript問題修正済み")
        print(f"✅ 閃爍問題完全修正")
        print(f"✅ 全機能搭載")
        print(f"サーバー起動: http://localhost:{port}")
        print(f"ブラウザを開いています...")

        def open_browser():
            time.sleep(1.5)
            try:
                webbrowser.open(f'http://localhost:{port}')
            except:
                print("ブラウザを自動で開けませんでした。")
                print(f"手動で開いてください: http://localhost:{port}")

        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()

        print("サーバーを停止するにはCtrl+Cを押してください")
        httpd.serve_forever()

    except KeyboardInterrupt:
        print("\nユーザーによってサーバーが停止されました")
        httpd.shutdown()
    except Exception as e:
        print(f"サーバー開始エラー: {e}")

def main():
    try:
        print("🎯 3D等角CAM可視化ツール（完全版）")
        print("✅ 全問題修正済み - 閃爍なし")
        print("=" * 50)

        start_server()

    except Exception as e:
        print(f"エラー: {e}")
    finally:
        try:
            input("\n終了するにはEnterキーを押してください...")
        except:
            pass

if __name__ == "__main__":
    main()