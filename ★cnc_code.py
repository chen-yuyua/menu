# -*- coding: utf-8 -*-
import sys
import os
import webbrowser
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import math
import re
import tempfile
import socket

# Enhanced encoding handling for exe packaging
def setup_encoding():
    """Setup encoding for exe packaging compatibility"""
    try:
        if sys.platform.startswith('win'):
            # For Windows exe packaging
            if hasattr(sys.stdout, 'reconfigure'):
                try:
                    sys.stdout.reconfigure(encoding='utf-8', errors='ignore')
                    sys.stderr.reconfigure(encoding='utf-8', errors='ignore')
                except:
                    pass

            # Set environment variables
            os.environ['PYTHONIOENCODING'] = 'utf-8'
            os.environ['PYTHONLEGACYWINDOWSSTDIO'] = '1'

    except Exception as e:
        # Silent fail for packaging compatibility
        pass

# Call setup immediately
setup_encoding()

class SafeMultiOperationCAMParser:
    """Safe version of CAM parser for exe packaging"""

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

    def safe_print(self, message):
        """Safe print function for exe packaging"""
        try:
            print(message)
        except:
            # Silent fail if print doesn't work in exe
            pass

    def parse_gcode(self, gcode_text):
        self.reset()

        if not gcode_text:
            return []

        try:
            lines = gcode_text.split('\n')
        except:
            lines = str(gcode_text).split('\n')

        self.safe_print(f"Processing {len(lines)} lines of multi-operation CAM G-code...")

        processed_lines = 0
        skipped_lines = 0

        for line_num, line in enumerate(lines, 1):
            try:
                line = str(line).strip()
                if not line:
                    continue

                processed_lines += 1

                # Skip comments and program headers
                if (line.startswith('(') or line.startswith(';') or
                    line.startswith('N') or line.startswith('%')):
                    skipped_lines += 1
                    continue

                # Process the line
                self._parse_line(line, line_num)

            except Exception as e:
                self.safe_print(f"Parse error at line {line_num}: {line} - {e}")
                continue

        # Finalize last operation
        if self.current_operation:
            self.operations.append(self.current_operation)

        # Flatten all operations into commands
        self.commands = []
        for op in self.operations:
            self.commands.extend(op)

        self.safe_print(f"Parsing summary:")
        self.safe_print(f"- Total lines: {len(lines)}")
        self.safe_print(f"- Processed lines: {processed_lines}")
        self.safe_print(f"- Skipped lines: {skipped_lines}")
        self.safe_print(f"- Valid movement commands: {len(self.commands)}")
        self.safe_print(f"- Operations detected: {len(self.operations)}")

        if len(self.commands) == 0:
            self.safe_print("Warning: No movement commands found!")
            for i, line in enumerate(lines[:5]):  # Show first 5 lines only
                self.safe_print(f"  {i+1}: {line}")

        return self.commands

    def _parse_line(self, line, line_num):
        original_line = str(line).strip()
        line = str(line).strip().upper()

        # Handle tool setup and mode commands
        if any(x in line for x in ['G100', 'G56', 'G43', 'M08', 'M30', 'M211', 'M9']):
            return None

        # Handle program headers and comments
        if (line.startswith('(') or line.startswith('N') or
            'PROGRAM' in line or 'ENDMILL' in line):
            return None

        # Detect operation changes (Z movements)
        try:
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
        except:
            pass

        # Extract G-code command - support both G1 and G01 formats
        gcode = None
        try:
            g_match = re.search(r'G(\d+)', line)
            if g_match:
                g_num = int(g_match.group(1))
                if g_num in [0, 1, 2, 3]:
                    gcode = f'G{g_num:02d}'  # Convert G1 to G01, etc.
                    if gcode in ['G00', 'G01', 'G02', 'G03']:
                        self.current_g_mode = gcode
        except:
            pass

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

        try:
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
        except:
            # Safe fallback if regex fails
            pass

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
                try:
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
                except:
                    pass

        return None

# Global parser instance
parser = SafeMultiOperationCAMParser()

def find_free_port():
    """Find a free port for the server"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port
    except:
        return 8080

# HTML template for exe packaging
EXE_SAFE_HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3D CAM可視化工具 (EXE版)</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Microsoft JhengHei', 'Segoe UI', sans-serif;
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
            <h1>🎯 3D CAM可視化工具 (EXE版)</h1>
            <p>3次元等角投影 - 獨立執行版本</p>
        </div>

        <div class="main-content">
            <div class="left-panel">
                <div class="input-section">
                    <h3>📝 CAM G-code</h3>
                    <textarea id="gcodeInput" placeholder="請將CAM程式碼貼上到這裡...

支援功能：
✓ 3D等角投影顯示
✓ 滑鼠拖拽旋轉
✓ 滾輪縮放
✓ Shift+拖拽平移
✓ 方向鍵平移"></textarea>

                    <div class="controls">
                        <button class="btn btn-primary" onclick="parseAndVisualize()">🔧 解析顯示</button>
                        <button class="btn btn-secondary" onclick="clearAll()">🗑️ 清除</button>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr; gap: 5px; margin-top: 10px;">
                        <button class="btn" style="background: #17a2b8; color: white; font-size: 12px;" onclick="testConnection()">🔍 連接測試</button>
                        <button class="btn" style="background: #28a745; color: white; font-size: 12px;" onclick="loadSampleGCode()">📋 載入範例</button>
                    </div>

                    <div id="messageArea"></div>

                    <div class="operations-info" id="operationsInfo" style="display: none;">
                        <div style="font-weight: bold; margin-bottom: 5px;">檢測到的操作:</div>
                        <div id="operationsList"></div>
                    </div>
                </div>

                <div class="info-panel">
                    <div class="info-grid">
                        <div class="info-item">
                            <div class="label">總指令數</div>
                            <div class="value" id="totalCommands">0</div>
                        </div>
                        <div class="info-item">
                            <div class="label">操作數</div>
                            <div class="value" id="operationCount">0</div>
                        </div>
                        <div class="info-item">
                            <div class="label">距離 (mm)</div>
                            <div class="value" id="totalDistance">0</div>
                        </div>
                        <div class="info-item">
                            <div class="label">3D範圍</div>
                            <div class="value" id="workVolume">--</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="right-panel">
                <div class="canvas-container">
                    <canvas id="canvas" width="1000" height="600"></canvas>
                    <div class="view-controls">
                        <div class="view-info">3D視角控制</div>
                        <div>旋轉: <span id="rotationX">30</span>°, <span id="rotationY">45</span>°</div>
                        <div>縮放: <span id="zoomLevel">100</span>%</div>
                        <div>
                            <button onclick="resetView3D()">重設</button>
                            <button onclick="viewTop()">上視</button>
                            <button onclick="viewFront()">正視</button>
                            <button onclick="viewRight()">右視</button>
                            <button onclick="viewIsometric()">等角</button>
                        </div>
                    </div>
                    <div class="canvas-controls">
                        <button class="canvas-btn" onclick="toggleGrid()">📐 網格</button>
                        <button class="canvas-btn" onclick="toggleAxes()">🔄 座標軸</button>
                        <button class="canvas-btn" onclick="zoomIn3D()">🔍+ 放大</button>
                        <button class="canvas-btn" onclick="zoomOut3D()">🔍- 縮小</button>
                        <button class="canvas-btn" onclick="fitToView3D()">📐 全視圖</button>
                    </div>
                    <div class="zoom-info" id="zoomInfo">3D 縮放: 100%</div>
                </div>

                <div class="legend">
                    <div class="legend-item">
                        <div class="legend-color" style="background: #e74c3c; min-width: 16px; height: 3px;"></div>
                        <span>快速移動 (G00)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background: #3498db; min-width: 16px; height: 3px;"></div>
                        <span>直線插補 (G01)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background: #f39c12; min-width: 16px; height: 3px;"></div>
                        <span>順時針圓弧 (G02)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background: #9b59b6; min-width: 16px; height: 3px;"></div>
                        <span>逆時針圓弧 (G03)</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Global variables - safe for exe packaging
        let canvas, ctx;
        let currentCommands = [];

        // 3D view parameters
        let rotationX = 30;
        let rotationY = 45;
        let zoom3D = 1.0;
        let offsetX = 0, offsetY = 0;
        let showGrid = true;
        let showAxes = true;

        // Interaction
        let isDragging = false;
        let lastMouseX, lastMouseY;

        // Safe initialization for exe
        window.addEventListener('load', function() {
            try {
                console.log('EXE version initializing...');
                canvas = document.getElementById('canvas');
                ctx = canvas.getContext('2d');
                setupCanvasInteraction();
                setupKeyboardControls();
                resetView3D();
                showMessage('3D CAM可視化工具準備就緒！\\n拖拽旋轉，Shift+拖拽平移，滾輪縮放', 'success');
            } catch (e) {
                console.error('Initialization error:', e);
                showMessage('初始化時發生錯誤: ' + e.message, 'error');
            }
        });

        function setupCanvasInteraction() {
            try {
                canvas.addEventListener('mousedown', startDrag);
                canvas.addEventListener('mousemove', handleMouseMove);
                canvas.addEventListener('mouseup', stopDrag);
                canvas.addEventListener('wheel', handleWheel);
                canvas.addEventListener('mouseleave', stopDrag);
            } catch (e) {
                console.error('Canvas interaction setup error:', e);
            }
        }

        function startDrag(e) {
            isDragging = true;
            lastMouseX = e.clientX;
            lastMouseY = e.clientY;
            canvas.style.cursor = 'grabbing';
        }

        function handleMouseMove(e) {
            if (isDragging) {
                try {
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
                } catch (e) {
                    console.error('Mouse move error:', e);
                }
            }
        }

        function stopDrag() {
            isDragging = false;
            canvas.style.cursor = 'grab';
        }

        function handleWheel(e) {
            try {
                e.preventDefault();
                const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
                zoom3D *= zoomFactor;
                zoom3D = Math.max(0.1, Math.min(10, zoom3D));

                updateZoomDisplay();
                redraw3D();
            } catch (e) {
                console.error('Wheel handling error:', e);
            }
        }

        function setupKeyboardControls() {
            try {
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
            } catch (e) {
                console.error('Keyboard controls setup error:', e);
            }
        }

        function updateRotationDisplay() {
            try {
                document.getElementById('rotationX').textContent = Math.round(rotationX);
                document.getElementById('rotationY').textContent = Math.round(rotationY);
            } catch (e) {
                console.error('Rotation display update error:', e);
            }
        }

        function updateZoomDisplay() {
            try {
                document.getElementById('zoomLevel').textContent = Math.round(zoom3D * 100);
                document.getElementById('zoomInfo').textContent = '3D 縮放: ' + Math.round(zoom3D * 100) + '%';
            } catch (e) {
                console.error('Zoom display update error:', e);
            }
        }

        // 3D transformation functions
        function project3D(x, y, z) {
            try {
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
                const scale = zoom3D * 3;
                const screenX = canvas.width / 2 + x1 * scale + offsetX;
                const screenY = canvas.height / 2 - y1 * scale + offsetY;

                return { x: screenX, y: screenY, z: z2 };
            } catch (e) {
                console.error('3D projection error:', e);
                return { x: 0, y: 0, z: 0 };
            }
        }

        function parseAndVisualize() {
            try {
                console.log('Parse function called');

                const gcode = document.getElementById('gcodeInput').value.trim();
                console.log('Input G-code length:', gcode.length);

                if (!gcode) {
                    showMessage('請輸入CAM G-code程式碼。', 'error');
                    return;
                }

                showMessage('正在解析CAM G-code...', 'info');
                console.log('Starting parse process...');

                fetch('/parse', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({gcode: gcode})
                })
                .then(response => {
                    console.log('Response received:', response.status);
                    if (!response.ok) {
                        throw new Error('HTTP error! status: ' + response.status);
                    }
                    return response.json();
                })
                .then(result => {
                    console.log('Parsing result:', result);

                    if (result.error) {
                        showMessage('解析錯誤: ' + result.error, 'error');
                        console.error('Parsing error:', result.error);
                    } else {
                        currentCommands = result.commands;
                        console.log('Parsed commands count:', currentCommands.length);

                        if (currentCommands.length > 0) {
                            console.log('Visualizing 3D...');
                            updateUIOnce();
                            showMessage('成功顯示 ' + currentCommands.length + ' 個CAM指令！', 'success');

                            const totalLines = gcode.split('\\n').length;
                            const debugInfo = totalLines + '行程式碼 → ' + currentCommands.length + '個3D移動指令';
                            document.getElementById('messageArea').innerHTML +=
                                '<div class="debug-info">' + debugInfo + '</div>';
                        } else {
                            showMessage('未找到移動指令。請確認G-code包含移動指令。', 'error');
                            console.log('No movement commands found');
                        }
                    }
                })
                .catch(error => {
                    console.error('Fetch error:', error);
                    showMessage('通訊錯誤: ' + error.message + '\\n\\n請確認伺服器正在運行。', 'error');
                });

            } catch (error) {
                console.error('Parse error:', error);
                showMessage('解析錯誤: ' + error.message, 'error');
            }
        }

        function updateUIOnce() {
            try {
                if (currentCommands.length === 0) return;

                console.log('Updating UI once...');

                visualize3D();
                updateStatisticsOnce();
                updateOperationsInfoOnce();
            } catch (e) {
                console.error('UI update error:', e);
            }
        }

        function updateStatisticsOnce() {
            try {
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

                const updates = {
                    'totalCommands': currentCommands.length.toString(),
                    'totalDistance': totalDistance.toFixed(2),
                    'workVolume': isFinite(minX) ?
                        (maxX-minX).toFixed(1) + '×' + (maxY-minY).toFixed(1) + '×' + (maxZ-minZ).toFixed(1) + 'mm' : '--'
                };

                Object.keys(updates).forEach(id => {
                    const element = document.getElementById(id);
                    if (element && element.textContent !== updates[id]) {
                        element.textContent = updates[id];
                    }
                });
            } catch (e) {
                console.error('Statistics update error:', e);
            }
        }

        function updateOperationsInfoOnce() {
            try {
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
                    operationsHtml +=
                        '<div class="operation-item">' +
                        '<span>操作 #' + (parseInt(opId) + 1) + '</span>' +
                        '<span>' + ops[opId] + '指令</span>' +
                        '</div>';
                }

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
            } catch (e) {
                console.error('Operations info update error:', e);
            }
        }

        function visualize3D() {
            try {
                if (currentCommands.length === 0) return;

                fitToView3D();
                redraw3D();
            } catch (e) {
                console.error('3D visualization error:', e);
            }
        }

        function redraw3D() {
            try {
                ctx.clearRect(0, 0, canvas.width, canvas.height);

                if (showGrid) drawGrid3D();
                if (showAxes) drawAxes3D();

                draw3DPaths();
            } catch (e) {
                console.error('3D redraw error:', e);
            }
        }

        function drawGrid3D() {
            try {
                ctx.save();
                ctx.strokeStyle = 'rgba(200, 200, 200, 0.3)';
                ctx.lineWidth = 1;

                const gridSize = 20;
                const gridExtent = 100;

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
            } catch (e) {
                console.error('Grid drawing error:', e);
            }
        }

        function drawAxes3D() {
            try {
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
            } catch (e) {
                console.error('Axes drawing error:', e);
            }
        }

        function draw3DPaths() {
            try {
                if (currentCommands.length === 0) return;

                const operationColors = ['#3498db', '#e74c3c', '#f39c12', '#9b59b6', '#1abc9c', '#95a5a6'];

                ctx.save();
                ctx.lineCap = 'round';
                ctx.lineJoin = 'round';

                // Draw start point
                if (currentCommands.length > 0) {
                    const start = currentCommands[0].from;
                    const startProj = project3D(start.x, start.y, start.z);

                    ctx.fillStyle = '#27ae60';
                    ctx.beginPath();
                    ctx.arc(startProj.x, startProj.y, 6, 0, Math.PI * 2);
                    ctx.fill();

                    ctx.strokeStyle = 'white';
                    ctx.lineWidth = 2;
                    ctx.stroke();

                    ctx.fillStyle = '#2c3e50';
                    ctx.font = '12px Arial';
                    ctx.fillText('START', startProj.x + 10, startProj.y - 10);
                }

                // Draw paths
                for (let cmd of currentCommands) {
                    const opColor = operationColors[cmd.operation_id % operationColors.length];

                    switch (cmd.type) {
                        case 'G00':
                            ctx.strokeStyle = '#e74c3c';
                            ctx.lineWidth = 2;
                            ctx.setLineDash([6, 6]);
                            break;
                        case 'G01':
                            ctx.strokeStyle = opColor;
                            ctx.lineWidth = 3;
                            ctx.setLineDash([]);
                            break;
                        case 'G02':
                            ctx.strokeStyle = '#f39c12';
                            ctx.lineWidth = 4;
                            ctx.setLineDash([]);
                            break;
                        case 'G03':
                            ctx.strokeStyle = '#9b59b6';
                            ctx.lineWidth = 4;
                            ctx.setLineDash([]);
                            break;
                    }

                    const fromProj = project3D(cmd.from.x, cmd.from.y, cmd.from.z);
                    const toProj = project3D(cmd.to.x, cmd.to.y, cmd.to.z);

                    ctx.beginPath();
                    ctx.moveTo(fromProj.x, fromProj.y);
                    ctx.lineTo(toProj.x, toProj.y);
                    ctx.stroke();
                }

                ctx.restore();
            } catch (e) {
                console.error('Path drawing error:', e);
            }
        }

        // View control functions
        function resetView3D() {
            try {
                rotationX = 30;
                rotationY = 45;
                zoom3D = 1.0;
                offsetX = 0;
                offsetY = 0;
                updateRotationDisplay();
                updateZoomDisplay();
                redraw3D();
            } catch (e) {
                console.error('Reset view error:', e);
            }
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
            try {
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
            } catch (e) {
                console.error('Fit to view error:', e);
            }
        }

        function toggleGrid() {
            showGrid = !showGrid;
            redraw3D();
        }

        function toggleAxes() {
            showAxes = !showAxes;
            redraw3D();
        }

        function clearAll() {
            try {
                console.log('Clear all called');

                document.getElementById('gcodeInput').value = '';
                currentCommands = [];
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                resetView3D();

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

                document.getElementById('operationsInfo').style.display = 'none';
                showMessage('已清除所有內容。', 'info');
            } catch (e) {
                console.error('Clear all error:', e);
            }
        }

        function testConnection() {
            try {
                console.log('Test connection called');
                showMessage('測試伺服器連接中...', 'info');

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
                        throw new Error('HTTP ' + response.status);
                    }
                })
                .then(result => {
                    console.log('Test result:', result);
                    showMessage('✅ 伺服器連接正常！測試解析成功。', 'success');
                })
                .catch(error => {
                    console.error('Test failed:', error);
                    showMessage('❌ 無法連接到伺服器: ' + error.message, 'error');
                });
            } catch (e) {
                console.error('Test connection error:', e);
                showMessage('❌ 連接測試失敗: ' + e.message, 'error');
            }
        }

        function loadSampleGCode() {
            try {
                console.log('Load sample called');
                const sampleGCode = 'G01 X1 Y1 Z0.5 F500\\nG01 X10 Y1\\nG01 X10 Y10\\nG01 X1 Y10\\nG01 X1 Y1\\nG02 X5 Y5 R5\\nG03 X8 Y8 R3\\nG01 X0 Y0\\nG00 Z50';

                document.getElementById('gcodeInput').value = sampleGCode;
                showMessage('已載入範例G-code程式碼。請點擊解析按鈕。', 'success');
            } catch (e) {
                console.error('Load sample error:', e);
                showMessage('載入範例失敗: ' + e.message, 'error');
            }
        }

        function showMessage(message, type) {
            try {
                const messageArea = document.getElementById('messageArea');
                let className = 'success-message';

                if (type === 'error') {
                    className = 'error-message';
                } else if (type === 'info') {
                    className = 'success-message';
                }

                messageArea.innerHTML = '<div class="' + className + '">' + message + '</div>';

                if (type !== 'error') {
                    setTimeout(function() {
                        const debugElements = messageArea.querySelectorAll('.debug-info');
                        if (debugElements.length === 0) {
                            messageArea.innerHTML = '';
                        }
                    }, 8000);
                }
            } catch (e) {
                console.error('Show message error:', e);
            }
        }
    </script>
</body>
</html>'''

class SafeCNCRequestHandler(BaseHTTPRequestHandler):
    """Safe request handler for exe packaging"""

    def log_message(self, format, *args):
        """Override to prevent encoding issues in exe"""
        try:
            super().log_message(format, *args)
        except:
            pass  # Silent fail for exe packaging

    def do_GET(self):
        try:
            if self.path == '/' or self.path == '/index.html':
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(EXE_SAFE_HTML_TEMPLATE.encode('utf-8', errors='ignore'))
            else:
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            parser.safe_print(f"GET request error: {e}")
            try:
                self.send_response(500)
                self.end_headers()
            except:
                pass

    def do_POST(self):
        try:
            if self.path == '/parse':
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)

                try:
                    data = json.loads(post_data.decode('utf-8', errors='ignore'))
                except:
                    data = {'gcode': ''}

                gcode = data.get('gcode', '')
                commands = parser.parse_gcode(gcode)

                response = {
                    'commands': commands,
                    'error': None
                }

                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()

                response_json = json.dumps(response, ensure_ascii=False)
                self.wfile.write(response_json.encode('utf-8', errors='ignore'))

        except Exception as e:
            parser.safe_print(f"POST request error: {e}")
            try:
                response = {
                    'commands': [],
                    'error': str(e)
                }

                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                response_json = json.dumps(response, ensure_ascii=False)
                self.wfile.write(response_json.encode('utf-8', errors='ignore'))
            except:
                try:
                    self.send_response(500)
                    self.end_headers()
                except:
                    pass

def start_safe_server():
    """Safe server startup for exe packaging"""
    port = find_free_port()
    server_address = ('localhost', port)

    try:
        httpd = HTTPServer(server_address, SafeCNCRequestHandler)

        # Safe print for exe
        try:
            print(f"🎯 3D CAM可視化工具 (EXE版)")
            print(f"伺服器啟動: http://localhost:{port}")
            print(f"正在開啟瀏覽器...")
        except:
            pass

        def safe_open_browser():
            time.sleep(2)
            try:
                webbrowser.open(f'http://localhost:{port}')
            except:
                try:
                    print(f"請手動開啟瀏覽器並前往: http://localhost:{port}")
                except:
                    pass

        browser_thread = threading.Thread(target=safe_open_browser)
        browser_thread.daemon = True
        browser_thread.start()

        try:
            print("按 Ctrl+C 停止伺服器")
        except:
            pass

        httpd.serve_forever()

    except KeyboardInterrupt:
        try:
            print("\n伺服器已停止")
        except:
            pass
        try:
            httpd.shutdown()
        except:
            pass
    except Exception as e:
        try:
            print(f"伺服器啟動錯誤: {e}")
        except:
            pass

def main():
    try:
        setup_encoding()
        start_safe_server()
    except Exception as e:
        try:
            print(f"程式錯誤: {e}")
        except:
            pass
    finally:
        try:
            input("\n按 Enter 鍵結束程式...")
        except:
            pass

if __name__ == "__main__":
    main()
