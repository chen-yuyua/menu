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
import socket

# Enhanced encoding handling for exe packaging
def setup_encoding():
    """Setup encoding for exe packaging compatibility"""
    try:
        if sys.platform.startswith('win'):
            if hasattr(sys.stdout, 'reconfigure'):
                try:
                    sys.stdout.reconfigure(encoding='utf-8', errors='ignore')
                    sys.stderr.reconfigure(encoding='utf-8', errors='ignore')
                except:
                    pass

            os.environ['PYTHONIOENCODING'] = 'utf-8'
            os.environ['PYTHONLEGACYWINDOWSSTDIO'] = '1'

    except Exception:
        pass

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
            for i, line in enumerate(lines[:5]):
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

                if abs(new_z - self.current_z) > 5:
                    if self.current_operation:
                        self.operations.append(self.current_operation)
                        self.current_operation = []

                    self.is_cutting = new_z < 50

                self.current_z = new_z
        except:
            pass

        # Extract G-code command
        gcode = None
        try:
            # 首先查找當前行是否有明確的G指令
            g_match = re.search(r'G(\d+)', line)
            if g_match:
                g_num = int(g_match.group(1))
                if g_num in [0, 1, 2, 3]:
                    gcode = f'G{g_num:02d}'
                    # 更新當前G模式
                    self.current_g_mode = gcode

            # 如果當前行沒有G指令，但有座標移動，則使用當前G模式
            # 但要確保模式的正確性

        except:
            pass

        # Handle tool compensation
        if 'G42' in line or 'G41' in line:
            self.tool_compensation_active = True
            self.current_g_mode = 'G01'
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

            d_match = re.search(r'D(\d+)', line)
            tool_diameter = None
            if d_match:
                tool_diameter = float(d_match.group(1))
        except:
            pass

        # Create movement command if we have coordinates
        if coords and ('X' in coords or 'Y' in coords):
            if not gcode:
                gcode = self.current_g_mode

            if gcode not in ['G00', 'G01', 'G02', 'G03']:
                return None

            new_x = coords.get('X', self.current_x)
            new_y = coords.get('Y', self.current_y)

            if 'G40' in line:
                if (abs(new_x - self.current_x) > 10 or abs(new_y - self.current_y) > 10):
                    self.is_cutting = False
                    gcode = 'G00'

            if abs(new_x - self.current_x) > 0.001 or abs(new_y - self.current_y) > 0.001:
                try:
                    # 確保使用正確的G指令類型
                    final_gcode = gcode if gcode else self.current_g_mode

                    # 調試：檢查圓弧參數是否存在
                    has_arc_params = (arc_params.get('R', 0) != 0 or
                                     arc_params.get('I', 0) != 0 or
                                     arc_params.get('J', 0) != 0)

                    # 如果沒有圓弧參數但使用了G02/G03，改為G01
                    if (final_gcode in ['G02', 'G03']) and not has_arc_params:
                        self.safe_print(f"警告：第{line_num}行 {final_gcode} 指令無圓弧參數，改為G01: {original_line}")
                        final_gcode = 'G01'

                    # 如果有圓弧參數但使用了G01，檢查是否應該是圓弧指令
                    if final_gcode == 'G01' and has_arc_params:
                        self.safe_print(f"注意：第{line_num}行 G01指令包含圓弧參數: {original_line}")

                    cmd = {
                        'type': final_gcode,
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

                    if self.is_cutting or final_gcode == 'G00':
                        self.current_operation.append(cmd)

                    self.current_x = new_x
                    self.current_y = new_y
                except Exception as e:
                    self.safe_print(f"創建指令時發生錯誤，第{line_num}行: {e}")
                    pass

        return None

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

# HTML template - variable name carefully chosen to avoid conflicts
CLEAN_CAM_HTML = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3D CAM可視化工具 (圓弧修正版)</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', 'Segoe UI', sans-serif; }
        body { font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', 'Segoe UI', sans-serif; background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 1600px; margin: 0 auto; background: white; border-radius: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: linear-gradient(135deg, #3d4e60 0%, #4a5568 100%); color: white; padding: 20px 30px; text-align: center; }
        .header h1 { font-size: 2.2em; margin-bottom: 8px; font-weight: 300; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; }
        .header p { opacity: 0.8; font-size: 1em; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; }
        .main-content { display: grid; grid-template-columns: 350px 1fr; min-height: 700px; }
        .left-panel { background: #f8f9fa; padding: 25px; border-right: 1px solid #e9ecef; overflow-y: auto; max-height: 700px; }
        .input-section { margin-bottom: 25px; }
        .input-section h3 { color: #2c3e50; margin-bottom: 12px; font-size: 1.2em; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; }
        textarea { width: 100%; height: 180px; padding: 12px; border: 2px solid #e9ecef; border-radius: 8px; font-family: 'BIZ UDPゴシック', 'Consolas', 'Courier New', monospace; font-size: 10px; line-height: 1.2; resize: vertical; transition: border-color 0.3s ease; }
        textarea:focus { outline: none; border-color: #667eea; }
        .controls { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
        .btn { padding: 10px 20px; border: none; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.3s ease; text-align: center; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; }
        .btn-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3); }
        .btn-secondary { background: #6c757d; color: white; }
        .btn-secondary:hover { background: #5a6268; transform: translateY(-1px); }
        .right-panel { padding: 25px; display: flex; flex-direction: column; }
        .canvas-container { flex: 1; border: 2px solid #e9ecef; border-radius: 10px; position: relative; background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); overflow: hidden; min-height: 500px; }
        #canvas { display: block; cursor: grab; }
        #canvas:active { cursor: grabbing; }
        .canvas-controls { position: absolute; top: 10px; right: 10px; display: flex; gap: 5px; z-index: 10; flex-wrap: wrap; }
        .canvas-btn { background: rgba(255, 255, 255, 0.95); border: 1px solid #dee2e6; border-radius: 4px; padding: 6px 10px; cursor: pointer; font-size: 12px; transition: all 0.2s ease; white-space: nowrap; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; }
        .canvas-btn:hover { background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .canvas-btn.active { background: #007bff; color: white; }
        .view-controls { position: absolute; top: 10px; left: 10px; background: rgba(0, 0, 0, 0.8); color: white; padding: 10px; border-radius: 6px; font-size: 12px; font-family: 'BIZ UDPゴシック', 'Consolas', 'Courier New', monospace; }
        .view-info { margin-bottom: 5px; }
        .view-controls button { background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); color: white; padding: 3px 8px; margin: 2px; border-radius: 3px; cursor: pointer; font-size: 10px; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; }
        .view-controls button:hover { background: rgba(255,255,255,0.3); }
        .info-panel { background: #f8f9fa; padding: 15px; border-radius: 8px; margin-top: 15px; }
        .info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; }
        .info-item { text-align: center; padding: 8px; background: white; border-radius: 6px; border: 1px solid #e9ecef; }
        .info-item .label { color: #6c757d; font-size: 11px; margin-bottom: 4px; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; }
        .info-item .value { color: #2c3e50; font-weight: 600; font-size: 14px; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; }
        .legend { display: flex; gap: 15px; margin-top: 10px; flex-wrap: wrap; }
        .legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; }
        .legend-color { width: 16px; min-width: 16px; height: 3px; border-radius: 2px; }
        .error-message { background: #f8d7da; color: #721c24; padding: 10px; border-radius: 6px; margin-top: 8px; border: 1px solid #f5c6cb; font-size: 12px; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; }
        .success-message { background: #d1edff; color: #0c5460; padding: 10px; border-radius: 6px; margin-top: 8px; border: 1px solid #bee5eb; font-size: 12px; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; }
        .debug-info { background: #fff3cd; color: #856404; padding: 8px; border-radius: 4px; margin-top: 8px; border: 1px solid #ffeaa7; font-size: 11px; font-family: 'BIZ UDPゴシック', 'Consolas', 'Courier New', monospace; }
        .zoom-info { position: absolute; bottom: 10px; left: 10px; background: rgba(0,0,0,0.7); color: white; padding: 5px 10px; border-radius: 4px; font-size: 12px; font-family: monospace; }
        .trajectory-info { position: absolute; top: 10px; right: 200px; background: rgba(0,0,0,0.9); color: white; padding: 12px 16px; border-radius: 8px; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; min-width: 220px; max-width: 300px; z-index: 15; border: 2px solid #007bff; box-shadow: 0 6px 12px rgba(0,0,0,0.4); }
        .operations-info { background: #e8f5e8; border: 1px solid #c3e6c3; border-radius: 6px; padding: 10px; margin-top: 10px; font-size: 11px; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; }
        .operation-item { display: flex; justify-content: space-between; margin: 2px 0; padding: 2px 5px; background: white; border-radius: 3px; }
        .animation-controls { position: absolute; bottom: 50px; left: 10px; background: rgba(0, 0, 0, 0.85); color: white; padding: 12px; border-radius: 6px; font-size: 11px; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; display: none; min-width: 200px; max-width: 280px; }
        .animation-progress { width: 180px; height: 4px; background: rgba(255,255,255,0.3); border-radius: 2px; margin: 5px 0; overflow: hidden; }
        .animation-progress-bar { height: 100%; background: linear-gradient(90deg, #00ff00, #ffff00, #ff0000); width: 0%; transition: width 0.1s ease; }
        .speed-buttons { display: grid; grid-template-columns: repeat(4, 1fr); gap: 2px; margin: 5px 0; }
        .speed-btn { background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3); color: white; padding: 4px 6px; border-radius: 3px; cursor: pointer; font-size: 9px; font-weight: 600; transition: all 0.2s ease; text-align: center; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; }
        .speed-btn:hover { background: rgba(255,255,255,0.3); }
        .speed-btn.active { background: #3498db; border-color: #2980b9; box-shadow: 0 1px 2px rgba(52, 152, 219, 0.3); }
        .speed-btn.active:hover { background: #2980b9; }
        .compact-info { font-size: 10px; line-height: 1.2; margin: 2px 0; }
        .tool-setting { background: #e8f4f8; border: 1px solid #b3d9e6; border-radius: 6px; padding: 10px; margin-top: 15px; }
        .tool-setting h4 { color: #2c3e50; margin-bottom: 8px; font-size: 14px; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; }
        .tool-setting input[type="number"] { padding: 4px 6px; border: 1px solid #ced4da; border-radius: 3px; font-size: 12px; text-align: center; font-family: 'BIZ UDPゴシック', 'Consolas', 'Courier New', monospace; }
        .tool-setting input[type="number"]:focus { outline: none; border-color: #17a2b8; box-shadow: 0 0 3px rgba(23, 162, 184, 0.3); }
        .tool-hint { font-size: 10px; color: #6c757d; margin-top: 4px; font-family: 'BIZ UDPゴシック', 'Yu Gothic', 'Microsoft JhengHei', sans-serif; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 3D CAM可視化工具 (圓弧修正版)</h1>
            <p>3次元等角投影 - 圓弧計算問題完全修正</p>
        </div>

        <div class="main-content">
            <div class="left-panel">
                <div class="input-section">
                    <h3>📝 CAM G-code</h3>
                    <textarea id="gcodeInput" placeholder="請將您的CAM程式碼貼上到這裡...

修正功能：
✓ 正確的圓弧計算 (G02/G03)
✓ 大半徑圓弧支援
✓ R參數和I,J參數支援
✓ 圓心位置驗證
✓ 調試資訊輸出"></textarea>

                    <div class="controls">
                        <button class="btn btn-primary" onclick="parseAndVisualize()">🔧 解析顯示</button>
                        <button class="btn btn-secondary" onclick="clearAll()">🗑️ 清除</button>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr; gap: 5px; margin-top: 10px;">
                        <button class="btn" style="background: #17a2b8; color: white; font-size: 12px;" onclick="testConnection()">🔍 連接測試</button>
                        <button class="btn" style="background: #28a745; color: white; font-size: 12px;" onclick="loadSampleCode()">📋 載入範例</button>
                        <button class="btn" style="background: #dc3545; color: white; font-size: 12px;" onclick="loadCAMCode()">📥 載入CAM程式</button>
                    </div>

                    <!-- 新增：刀徑設定區域 -->
                    <div class="tool-setting">
                        <h4>🔧 刀具設定</h4>
                        <div style="display: grid; grid-template-columns: 1fr 80px; gap: 8px; align-items: center;">
                            <label style="font-size: 12px; color: #495057;">刀徑 (mm):</label>
                            <input type="number" id="toolDiameter" value="6" min="0.1" max="50" step="0.1"
                                   onchange="updateToolDiameter()" />
                        </div>
                        <div class="tool-hint">
                            💡 動畫模式下會顯示刀具圓形和加工路徑
                        </div>
                        <div style="margin-top: 8px;">
                            <button class="btn" style="background: #6c757d; color: white; font-size: 11px; padding: 6px 12px;" onclick="clearToolPaths()">🗑️ 清除刀具路徑</button>
                        </div>
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
                                <button onclick="setSpeed(0.25)" class="speed-btn" data-speed="0.25">0.25x</button>
                                <button onclick="setSpeed(0.5)" class="speed-btn" data-speed="0.5">0.5x</button>
                                <button onclick="setSpeed(1)" class="speed-btn active" data-speed="1">1x</button>
                                <button onclick="setSpeed(2)" class="speed-btn" data-speed="2">2x</button>
                                <button onclick="setSpeed(4)" class="speed-btn" data-speed="4">4x</button>
                                <button onclick="setSpeed(8)" class="speed-btn" data-speed="8">8x</button>
                                <button onclick="setSpeed(16)" class="speed-btn" data-speed="16">16x</button>
                            </div>
                            <div style="margin-top: 4px; text-align: center;">
                                <button onclick="pauseAnimation()" id="pauseBtn">暫停</button>
                            </div>
                        </div>
                    </div>
                    <div class="canvas-controls">
                        <button class="canvas-btn" onclick="toggleGrid()">📐 網格</button>
                        <button class="canvas-btn" onclick="toggleAxes()">🔄 座標軸</button>
                        <button class="canvas-btn" onclick="zoomIn3D()">🔍+ 放大</button>
                        <button class="canvas-btn" onclick="zoomOut3D()">🔍- 縮小</button>
                        <button class="canvas-btn" onclick="fitToView3D()">📐 全視圖</button>
                        <button class="canvas-btn" onclick="toggleAnimation()" id="animationBtn">▶️ 動畫開始</button>
                    </div>
                    <div class="zoom-info" id="zoomInfo">3D 縮放: 100%</div>

                    <!-- 新增：軌跡資訊顯示區域 -->
                    <div class="trajectory-info" id="trajectoryInfo" style="display: none;">
                        <div style="font-weight: bold; margin-bottom: 6px; color: #fff; font-size: 16px;">軌跡資訊</div>
                        <div style="font-size: 14px; margin-bottom: 4px; color: #e0e0e0;">指令: <span id="trajCommand" style="color: #FFD700; font-weight: bold;">G01</span></div>
                        <div style="font-size: 14px; margin-bottom: 4px; color: #e0e0e0;">行號: <span id="trajLineNumber" style="color: #87CEEB; font-weight: bold;">123</span></div>
                        <div style="font-size: 14px; margin-bottom: 4px; color: #e0e0e0;">座標: <span id="trajCoords" style="color: #98FB98; font-weight: bold;">X10.5 Y20.3</span></div>
                        <div style="font-size: 13px; color: #ccc; margin-bottom: 4px; border-top: 1px solid #555; padding-top: 4px;">原始程式碼:</div>
                        <div style="font-size: 12px; font-family: 'Consolas', 'Courier New', monospace; background: rgba(255,255,255,0.1); color: #F0F8FF; padding: 6px 8px; border-radius: 4px; max-width: 260px; word-wrap: break-word; line-height: 1.4;" id="trajOriginal">G01 X10.5 Y20.3 F1000</div>
                    </div>
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
        // All variables properly declared
        let canvas, ctx;
        let currentCommands = [];
        let rotationX = 30, rotationY = 45, zoom3D = 1.0, offsetX = 0, offsetY = 0;
        let showGrid = true, showAxes = true;
        let isDragging = false, lastMouseX, lastMouseY;
        let isAnimating = false, animationFrame = 0, animationInterval = null;
        let drawnCommands = [], toolPosition = { x: 0, y: 0, z: 0 };
        let animationSpeed = 1, animationPaused = false;

        // 軌跡檢測相關變數
        let trajectorySegments = []; // 儲存所有軌跡線段資訊
        let hoveredSegment = null;   // 當前懸停的線段

        // 新增：刀具相關變數
        let toolDiameter = 6;        // 刀具直徑 (mm)
        let toolPath = [];           // 刀具走過的路徑點
        let machiningPaths = [];     // 加工路徑 (刀具中心到工件表面的平行路徑)

        window.addEventListener('load', function() {
            try {
                console.log('Arc-fixed version initializing...');
                canvas = document.getElementById('canvas');
                ctx = canvas.getContext('2d');
                setupCanvas();
                setupKeyboard();
                resetView3D();
                showMessage('3D CAM可視化工具準備就緒！圓弧計算問題已修正', 'success');
            } catch (e) {
                console.error('Init error:', e);
                showMessage('初始化錯誤: ' + e.message, 'error');
            }
        });

        function setupCanvas() {
            canvas.addEventListener('mousedown', e => {
                isDragging = true;
                lastMouseX = e.clientX;
                lastMouseY = e.clientY;
                canvas.style.cursor = 'grabbing';
            });

            canvas.addEventListener('mousemove', e => {
                if (isDragging) {
                    const deltaX = e.clientX - lastMouseX;
                    const deltaY = e.clientY - lastMouseY;
                    if (e.shiftKey) {
                        offsetX += deltaX;
                        offsetY += deltaY;
                    } else {
                        rotationY += deltaX * 0.5;
                        rotationX += deltaY * 0.5;
                        rotationX = Math.max(-90, Math.min(90, rotationX));
                        updateRotationDisplay();
                    }
                    lastMouseX = e.clientX;
                    lastMouseY = e.clientY;
                    redraw3D();
                } else {
                    // 新增：檢測滑鼠懸停軌跡
                    checkTrajectoryHover(e);
                }
            });

            canvas.addEventListener('mouseup', () => {
                isDragging = false;
                canvas.style.cursor = 'grab';
            });

            canvas.addEventListener('wheel', e => {
                e.preventDefault();
                const factor = e.deltaY > 0 ? 0.9 : 1.1;
                zoom3D *= factor;
                zoom3D = Math.max(0.1, Math.min(10, zoom3D));
                updateZoomDisplay();
                redraw3D();
            });

            canvas.addEventListener('mouseleave', () => {
                isDragging = false;
                canvas.style.cursor = 'grab';
                // 隱藏軌跡資訊
                hideTrajectoryInfo();
            });
        }

        function setupKeyboard() {
            document.addEventListener('keydown', e => {
                const step = 10;
                let redraw = false;
                switch(e.key) {
                    case 'ArrowLeft': offsetX -= step; redraw = true; e.preventDefault(); break;
                    case 'ArrowRight': offsetX += step; redraw = true; e.preventDefault(); break;
                    case 'ArrowUp': offsetY -= step; redraw = true; e.preventDefault(); break;
                    case 'ArrowDown': offsetY += step; redraw = true; e.preventDefault(); break;
                }
                if (redraw) redraw3D();
            });
        }

        function updateRotationDisplay() {
            try {
                document.getElementById('rotationX').textContent = Math.round(rotationX);
                document.getElementById('rotationY').textContent = Math.round(rotationY);
            } catch (e) {
                console.error('Rotation display error:', e);
            }
        }

        function updateZoomDisplay() {
            try {
                document.getElementById('zoomLevel').textContent = Math.round(zoom3D * 100);
                document.getElementById('zoomInfo').textContent = '3D 縮放: ' + Math.round(zoom3D * 100) + '%';
            } catch (e) {
                console.error('Zoom display error:', e);
            }
        }

        function project3D(x, y, z) {
            try {
                const radX = rotationX * Math.PI / 180;
                const radY = rotationY * Math.PI / 180;
                const cosY = Math.cos(radY), sinY = Math.sin(radY);
                const x1 = x * cosY - z * sinY;
                const z1 = x * sinY + z * cosY;
                const cosX = Math.cos(radX), sinX = Math.sin(radX);
                const y1 = y * cosX - z1 * sinX;
                const scale = zoom3D * 3;
                return {
                    x: canvas.width / 2 + x1 * scale + offsetX,
                    y: canvas.height / 2 - y1 * scale + offsetY,
                    z: y * sinX + z1 * cosX
                };
            } catch (e) {
                console.error('3D projection error:', e);
                return { x: 0, y: 0, z: 0 };
            }
        }

        function parseAndVisualize() {
            try {
                const gcode = document.getElementById('gcodeInput').value.trim();
                if (!gcode) {
                    showMessage('請輸入CAM G-code程式碼。', 'error');
                    return;
                }

                showMessage('正在解析CAM G-code（圓弧修正版）...', 'info');

                fetch('/parse', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({gcode: gcode})
                })
                .then(response => {
                    if (!response.ok) throw new Error('HTTP error! status: ' + response.status);
                    return response.json();
                })
                .then(result => {
                    if (result.error) {
                        showMessage('解析錯誤: ' + result.error, 'error');
                    } else {
                        currentCommands = result.commands;
                        if (currentCommands.length > 0) {
                            updateUI();
                            showMessage('成功顯示 ' + currentCommands.length + ' 個CAM指令！圓弧計算已修正。', 'success');
                            const debugInfo = gcode.split('\\n').length + '行程式碼 → ' + currentCommands.length + '個3D移動指令（圓弧修正版）';
                            document.getElementById('messageArea').innerHTML += '<div class="debug-info">' + debugInfo + '</div>';

                            // 添加指令類型統計
                            let g00Count = 0, g01Count = 0, g02Count = 0, g03Count = 0;
                            console.log('=== 指令解析結果 ===');

                            for (let i = 0; i < currentCommands.length; i++) {
                                const cmd = currentCommands[i];
                                switch(cmd.type) {
                                    case 'G00': g00Count++; break;
                                    case 'G01': g01Count++; break;
                                    case 'G02': g02Count++; break;
                                    case 'G03': g03Count++; break;
                                }

                                // 輸出前10個指令的詳細資訊用於調試
                                if (i < 10) {
                                    console.log(`指令${i+1}: ${cmd.type} | 線號:${cmd.line_number} | 原始:${cmd.original_line}`);
                                }
                            }

                            console.log(`G00(快速移動-紅色): ${g00Count}個`);
                            console.log(`G01(直線插補-藍色): ${g01Count}個`);
                            console.log(`G02(順時針圓弧-橙色): ${g02Count}個`);
                            console.log(`G03(逆時針圓弧-紫色): ${g03Count}個`);
                            console.log('如果看到G01顯示錯誤顏色，請檢查Console輸出');
                        } else {
                            showMessage('未找到移動指令。請確認G-code包含移動指令。', 'error');
                        }
                    }
                })
                .catch(error => {
                    showMessage('通訊錯誤: ' + error.message, 'error');
                });
            } catch (error) {
                showMessage('解析錯誤: ' + error.message, 'error');
            }
        }

        function updateUI() {
            visualize3D();
            updateStats();
            updateOps();
        }

        function updateStats() {
            try {
                let totalDistance = 0, minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity, minZ = Infinity, maxZ = -Infinity;

                for (let cmd of currentCommands) {
                    const dx = cmd.to.x - cmd.from.x, dy = cmd.to.y - cmd.from.y, dz = cmd.to.z - cmd.from.z;
                    totalDistance += Math.sqrt(dx * dx + dy * dy + dz * dz);
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
                    'workVolume': isFinite(minX) ? (maxX-minX).toFixed(1) + '×' + (maxY-minY).toFixed(1) + '×' + (maxZ-minZ).toFixed(1) + 'mm' : '--'
                };

                Object.keys(updates).forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.textContent = updates[id];
                });
            } catch (e) {
                console.error('Stats error:', e);
            }
        }

        function updateOps() {
            try {
                const ops = {};
                for (let cmd of currentCommands) {
                    const opId = cmd.operation_id;
                    ops[opId] = (ops[opId] || 0) + 1;
                }

                const count = Object.keys(ops).length;
                let html = '';
                for (let opId in ops) {
                    html += '<div class="operation-item"><span>操作 #' + (parseInt(opId) + 1) + '</span><span>' + ops[opId] + '指令</span></div>';
                }

                const countEl = document.getElementById('operationCount');
                const listEl = document.getElementById('operationsList');
                const infoEl = document.getElementById('operationsInfo');

                if (countEl) countEl.textContent = count.toString();
                if (listEl) listEl.innerHTML = html;
                if (infoEl) infoEl.style.display = 'block';
            } catch (e) {
                console.error('Ops error:', e);
            }
        }

        function visualize3D() {
            if (currentCommands.length === 0) return;
            fitToView3D();
            redraw3D();
        }

        function redraw3D() {
            try {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                if (showGrid) drawGrid();
                if (showAxes) drawAxes();
                drawPaths();
            } catch (e) {
                console.error('Redraw error:', e);
            }
        }

        function drawGrid() {
            try {
                ctx.save();
                ctx.strokeStyle = 'rgba(200, 200, 200, 0.3)';
                ctx.lineWidth = 1;
                const size = 20, extent = 100;

                for (let x = -extent; x <= extent; x += size) {
                    const start = project3D(x, -extent, 0);
                    const end = project3D(x, extent, 0);
                    ctx.beginPath();
                    ctx.moveTo(start.x, start.y);
                    ctx.lineTo(end.x, end.y);
                    ctx.stroke();
                }

                for (let y = -extent; y <= extent; y += size) {
                    const start = project3D(-extent, y, 0);
                    const end = project3D(extent, y, 0);
                    ctx.beginPath();
                    ctx.moveTo(start.x, start.y);
                    ctx.lineTo(end.x, end.y);
                    ctx.stroke();
                }
                ctx.restore();
            } catch (e) {
                console.error('Grid error:', e);
            }
        }

        function drawAxes() {
            try {
                ctx.save();
                ctx.lineWidth = 3;
                const origin = project3D(0, 0, 0);
                const len = 50;

                // X axis - Red
                ctx.strokeStyle = '#e74c3c';
                ctx.beginPath();
                const xEnd = project3D(len, 0, 0);
                ctx.moveTo(origin.x, origin.y);
                ctx.lineTo(xEnd.x, xEnd.y);
                ctx.stroke();

                // Y axis - Green
                ctx.strokeStyle = '#27ae60';
                ctx.beginPath();
                const yEnd = project3D(0, len, 0);
                ctx.moveTo(origin.x, origin.y);
                ctx.lineTo(yEnd.x, yEnd.y);
                ctx.stroke();

                // Z axis - Blue
                ctx.strokeStyle = '#3498db';
                ctx.beginPath();
                const zEnd = project3D(0, 0, len);
                ctx.moveTo(origin.x, origin.y);
                ctx.lineTo(zEnd.x, zEnd.y);
                ctx.stroke();

                // Labels
                ctx.fillStyle = '#2c3e50';
                ctx.font = '14px "BIZ UDPゴシック", "Yu Gothic", "Microsoft JhengHei", Arial';
                ctx.fillText('X', xEnd.x + 5, xEnd.y);
                ctx.fillText('Y', yEnd.x + 5, yEnd.y);
                ctx.fillText('Z', zEnd.x + 5, zEnd.y);
                ctx.restore();
            } catch (e) {
                console.error('Axes error:', e);
            }
        }

        function drawPaths() {
            try {
                if (currentCommands.length === 0) return;

                const toDraw = isAnimating ? drawnCommands : currentCommands;
                const colors = ['#3498db', '#e74c3c', '#f39c12', '#9b59b6', '#1abc9c', '#95a5a6'];

                // 重置軌跡線段陣列
                trajectorySegments = [];

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
                    ctx.font = '12px "BIZ UDPゴシック", "Yu Gothic", "Microsoft JhengHei", Arial';
                    ctx.fillText('START', startProj.x + 10, startProj.y - 10);
                }

                // Draw paths and collect trajectory segments
                for (let i = 0; i < toDraw.length; i++) {
                    const cmd = toDraw[i];
                    const operationColor = colors[cmd.operation_id % colors.length];

                    // 明確設定每種指令的顏色和樣式
                    switch (cmd.type) {
                        case 'G00':
                            ctx.strokeStyle = '#e74c3c';  // 紅色 - 快速移動
                            ctx.lineWidth = 2;
                            ctx.setLineDash([6, 6]);
                            break;
                        case 'G01':
                            ctx.strokeStyle = '#3498db';  // 藍色 - 直線插補 (固定藍色，不使用操作顏色)
                            ctx.lineWidth = 3;
                            ctx.setLineDash([]);
                            break;
                        case 'G02':
                            ctx.strokeStyle = '#f39c12';  // 橙色 - 順時針圓弧
                            ctx.lineWidth = 4;
                            ctx.setLineDash([]);
                            break;
                        case 'G03':
                            ctx.strokeStyle = '#9b59b6';  // 紫色 - 逆時針圓弧
                            ctx.lineWidth = 4;
                            ctx.setLineDash([]);
                            break;
                        default:
                            // 預設情況
                            ctx.strokeStyle = operationColor;
                            ctx.lineWidth = 2;
                            ctx.setLineDash([]);
                            console.warn('Unknown G-code type:', cmd.type);
                            break;
                    }

                    ctx.beginPath();

                    if (cmd.type === 'G02' || cmd.type === 'G03') {
                        // 繪製圓弧並收集線段
                        drawFixedArcWithSegments(cmd, i);
                    } else {
                        // 繪製直線並收集線段
                        const from = project3D(cmd.from.x, cmd.from.y, cmd.from.z);
                        const to = project3D(cmd.to.x, cmd.to.y, cmd.to.z);
                        ctx.moveTo(from.x, from.y);
                        ctx.lineTo(to.x, to.y);

                        // 收集直線軌跡線段資訊
                        trajectorySegments.push({
                            points: [from, to],
                            command: cmd,
                            commandIndex: i,
                            type: 'line'
                        });
                    }

                    ctx.stroke();

                    // 調試：輸出指令類型和顏色資訊
                    if (i < 10) { // 只輸出前10個指令的調試資訊
                        console.log(`Command ${i}: ${cmd.type}, Color: ${ctx.strokeStyle}, Original: ${cmd.original_line}`);
                    }
                }

                // Tool position and machining paths (動畫中或動畫結束後)
                if ((isAnimating || toolPath.length > 0) && toolPosition) {
                    // 繪製刀具路徑（已走過的路徑）
                    if (toolPath.length > 1) {
                        ctx.strokeStyle = 'rgba(255, 165, 0, 0.5)';
                        ctx.lineWidth = 1;
                        ctx.setLineDash([3, 3]);
                        ctx.beginPath();
                        for (let i = 0; i < toolPath.length; i++) {
                            const pathPoint = project3D(toolPath[i].x, toolPath[i].y, toolPath[i].z);
                            if (i === 0) {
                                ctx.moveTo(pathPoint.x, pathPoint.y);
                            } else {
                                ctx.lineTo(pathPoint.x, pathPoint.y);
                            }
                        }
                        ctx.stroke();
                        ctx.setLineDash([]);
                    }

                    // 繪製加工路徑（刀具邊緣的平行路徑）
                    if (machiningPaths.length > 0) {
                        ctx.strokeStyle = 'rgba(128, 128, 128, 0.7)'; // 動畫結束後稍微加深
                        ctx.lineWidth = 1;
                        ctx.setLineDash([4, 4]);

                        for (let path of machiningPaths) {
                            const fromProj = project3D(path.from.x, path.from.y, path.from.z);
                            const toProj = project3D(path.to.x, path.to.y, path.to.z);

                            ctx.beginPath();
                            ctx.moveTo(fromProj.x, fromProj.y);
                            ctx.lineTo(toProj.x, toProj.y);
                            ctx.stroke();
                        }
                        ctx.setLineDash([]);
                    }

                    // 繪製Z軸連線（從底面到刀具）
                    const toolProj = project3D(toolPosition.x, toolPosition.y, toolPosition.z);
                    const baseProj = project3D(toolPosition.x, toolPosition.y, 0);

                    ctx.strokeStyle = isAnimating ? 'rgba(255, 107, 107, 0.6)' : 'rgba(255, 107, 107, 0.8)';
                    ctx.lineWidth = 2;
                    ctx.setLineDash([6, 6]);
                    ctx.beginPath();
                    ctx.moveTo(baseProj.x, baseProj.y);
                    ctx.lineTo(toolProj.x, toolProj.y);
                    ctx.stroke();
                    ctx.setLineDash([]);

                    // 繪製刀具圓形（根據實際刀徑）
                    const toolRadius3D = (toolDiameter / 2) * zoom3D * 3; // 與3D投影縮放一致

                    // 刀具主體 - 動畫結束後稍微調整透明度
                    const toolAlpha = isAnimating ? 0.7 : 0.8;
                    ctx.fillStyle = `rgba(255, 215, 0, ${toolAlpha})`; // 金色刀具
                    ctx.strokeStyle = '#ff4757';
                    ctx.lineWidth = 2;
                    ctx.beginPath();
                    ctx.arc(toolProj.x, toolProj.y, Math.max(3, toolRadius3D), 0, Math.PI * 2);
                    ctx.fill();
                    ctx.stroke();

                    // 刀具中心點
                    ctx.fillStyle = '#ff4757';
                    ctx.beginPath();
                    ctx.arc(toolProj.x, toolProj.y, 2, 0, Math.PI * 2);
                    ctx.fill();

                    // 刀具資訊顯示
                    ctx.fillStyle = '#2c3e50';
                    ctx.font = '10px "BIZ UDPゴシック", "Yu Gothic", "Microsoft JhengHei", Arial';
                    const labelText = isAnimating ? `Ø${toolDiameter}mm` : `Ø${toolDiameter}mm (完成)`;
                    ctx.fillText(labelText, toolProj.x + Math.max(3, toolRadius3D) + 5, toolProj.y - 5);
                }

                ctx.restore();

                // 繪製懸停效果
                drawHoverEffect();

            } catch (e) {
                console.error('Path error:', e);
            }
        }

        function drawFixedArc(cmd) {
            try {
                let centerX, centerY, radius;
                const fromX = cmd.from.x, fromY = cmd.from.y, toX = cmd.to.x, toY = cmd.to.y;

                if (cmd.r && cmd.r !== 0) {
                    radius = Math.abs(cmd.r);
                    const dx = toX - fromX, dy = toY - fromY;
                    const chordLength = Math.sqrt(dx * dx + dy * dy);

                    if (chordLength === 0) {
                        centerX = fromX; centerY = fromY;
                    } else if (chordLength > 2 * radius * 1.001) {
                        const from = project3D(fromX, fromY, cmd.from.z);
                        const to = project3D(toX, toY, cmd.to.z);
                        ctx.moveTo(from.x, from.y);
                        ctx.lineTo(to.x, to.y);
                        return;
                    } else {
                        const midX = (fromX + toX) / 2, midY = (fromY + toY) / 2;
                        const halfChord = chordLength / 2;
                        const centerDistance = Math.sqrt(Math.max(0, radius * radius - halfChord * halfChord));
                        const perpX = -dy / chordLength, perpY = dx / chordLength;
                        let direction;
                        if (cmd.r > 0) {
                            direction = (cmd.type === 'G02') ? -1 : 1;
                        } else {
                            direction = (cmd.type === 'G02') ? 1 : -1;
                        }
                        centerX = midX + direction * centerDistance * perpX;
                        centerY = midY + direction * centerDistance * perpY;
                    }
                } else if (cmd.i !== 0 || cmd.j !== 0) {
                    centerX = fromX + cmd.i;
                    centerY = fromY + cmd.j;
                    radius = Math.sqrt(cmd.i * cmd.i + cmd.j * cmd.j);
                } else {
                    const from = project3D(fromX, fromY, cmd.from.z);
                    const to = project3D(toX, toY, cmd.to.z);
                    ctx.moveTo(from.x, from.y);
                    ctx.lineTo(to.x, to.y);
                    return;
                }

                const radiusToStart = Math.sqrt((fromX - centerX) ** 2 + (fromY - centerY) ** 2);
                const radiusToEnd = Math.sqrt((toX - centerX) ** 2 + (toY - centerY) ** 2);
                const tolerance = Math.max(0.1, radius * 0.001);

                if (Math.abs(radiusToStart - radius) > tolerance || Math.abs(radiusToEnd - radius) > tolerance) {
                    const from = project3D(fromX, fromY, cmd.from.z);
                    const to = project3D(toX, toY, cmd.to.z);
                    ctx.moveTo(from.x, from.y);
                    ctx.lineTo(to.x, to.y);
                    return;
                }

                const startAngle = Math.atan2(fromY - centerY, fromX - centerX);
                const endAngle = Math.atan2(toY - centerY, toX - centerX);

                let angularSpan;
                if (cmd.type === 'G02') {
                    angularSpan = startAngle - endAngle;
                    if (angularSpan <= 0) angularSpan += 2 * Math.PI;
                } else {
                    angularSpan = endAngle - startAngle;
                    if (angularSpan <= 0) angularSpan += 2 * Math.PI;
                }

                if (cmd.r && cmd.r < 0) {
                    angularSpan = 2 * Math.PI - angularSpan;
                }

                const segments = Math.max(8, Math.ceil(angularSpan * radius / 5));

                for (let i = 0; i <= segments; i++) {
                    const t = i / segments;
                    let currentAngle;
                    if (cmd.type === 'G02') {
                        currentAngle = startAngle - t * angularSpan;
                    } else {
                        currentAngle = startAngle + t * angularSpan;
                    }

                    const x = centerX + radius * Math.cos(currentAngle);
                    const y = centerY + radius * Math.sin(currentAngle);
                    const point = project3D(x, y, cmd.from.z);

                    if (i === 0) {
                        ctx.moveTo(point.x, point.y);
                    } else {
                        ctx.lineTo(point.x, point.y);
                    }
                }
            } catch (e) {
                console.error('Arc error:', e);
                const from = project3D(cmd.from.x, cmd.from.y, cmd.from.z);
                const to = project3D(cmd.to.x, cmd.to.y, cmd.to.z);
                ctx.moveTo(from.x, from.y);
                ctx.lineTo(to.x, to.y);
            }
        }

        // 新增：帶線段收集功能的圓弧繪製函數
        function drawFixedArcWithSegments(cmd, commandIndex) {
            try {
                let centerX, centerY, radius;
                const fromX = cmd.from.x, fromY = cmd.from.y, toX = cmd.to.x, toY = cmd.to.y;

                // 圓弧計算邏輯與 drawFixedArc 相同
                if (cmd.r && cmd.r !== 0) {
                    radius = Math.abs(cmd.r);
                    const dx = toX - fromX, dy = toY - fromY;
                    const chordLength = Math.sqrt(dx * dx + dy * dy);

                    if (chordLength === 0) {
                        centerX = fromX; centerY = fromY;
                    } else if (chordLength > 2 * radius * 1.001) {
                        const from = project3D(fromX, fromY, cmd.from.z);
                        const to = project3D(toX, toY, cmd.to.z);
                        ctx.moveTo(from.x, from.y);
                        ctx.lineTo(to.x, to.y);

                        // 收集直線軌跡線段
                        trajectorySegments.push({
                            points: [from, to],
                            command: cmd,
                            commandIndex: commandIndex,
                            type: 'line'
                        });
                        return;
                    } else {
                        const midX = (fromX + toX) / 2, midY = (fromY + toY) / 2;
                        const halfChord = chordLength / 2;
                        const centerDistance = Math.sqrt(Math.max(0, radius * radius - halfChord * halfChord));
                        const perpX = -dy / chordLength, perpY = dx / chordLength;
                        let direction = cmd.r > 0 ? (cmd.type === 'G02' ? -1 : 1) : (cmd.type === 'G02' ? 1 : -1);
                        centerX = midX + direction * centerDistance * perpX;
                        centerY = midY + direction * centerDistance * perpY;
                    }
                } else if (cmd.i !== 0 || cmd.j !== 0) {
                    centerX = fromX + cmd.i;
                    centerY = fromY + cmd.j;
                    radius = Math.sqrt(cmd.i * cmd.i + cmd.j * cmd.j);
                } else {
                    const from = project3D(fromX, fromY, cmd.from.z);
                    const to = project3D(toX, toY, cmd.to.z);
                    ctx.moveTo(from.x, from.y);
                    ctx.lineTo(to.x, to.y);
                    trajectorySegments.push({
                        points: [from, to],
                        command: cmd,
                        commandIndex: commandIndex,
                        type: 'line'
                    });
                    return;
                }

                const radiusToStart = Math.sqrt((fromX - centerX) ** 2 + (fromY - centerY) ** 2);
                const radiusToEnd = Math.sqrt((toX - centerX) ** 2 + (toY - centerY) ** 2);
                const tolerance = Math.max(0.1, radius * 0.001);

                if (Math.abs(radiusToStart - radius) > tolerance || Math.abs(radiusToEnd - radius) > tolerance) {
                    const from = project3D(fromX, fromY, cmd.from.z);
                    const to = project3D(toX, toY, cmd.to.z);
                    ctx.moveTo(from.x, from.y);
                    ctx.lineTo(to.x, to.y);
                    trajectorySegments.push({
                        points: [from, to],
                        command: cmd,
                        commandIndex: commandIndex,
                        type: 'line'
                    });
                    return;
                }

                const startAngle = Math.atan2(fromY - centerY, fromX - centerX);
                const endAngle = Math.atan2(toY - centerY, toX - centerX);

                let angularSpan;
                if (cmd.type === 'G02') {
                    angularSpan = startAngle - endAngle;
                    if (angularSpan <= 0) angularSpan += 2 * Math.PI;
                } else {
                    angularSpan = endAngle - startAngle;
                    if (angularSpan <= 0) angularSpan += 2 * Math.PI;
                }

                if (cmd.r && cmd.r < 0) {
                    angularSpan = 2 * Math.PI - angularSpan;
                }

                const segments = Math.max(8, Math.ceil(angularSpan * radius / 5));
                let arcPoints = [];

                for (let i = 0; i <= segments; i++) {
                    const t = i / segments;
                    let currentAngle = cmd.type === 'G02' ?
                        startAngle - t * angularSpan :
                        startAngle + t * angularSpan;

                    const x = centerX + radius * Math.cos(currentAngle);
                    const y = centerY + radius * Math.sin(currentAngle);
                    const point = project3D(x, y, cmd.from.z);

                    arcPoints.push(point);

                    if (i === 0) {
                        ctx.moveTo(point.x, point.y);
                    } else {
                        ctx.lineTo(point.x, point.y);
                    }
                }

                // 收集圓弧軌跡線段資訊
                trajectorySegments.push({
                    points: arcPoints,
                    command: cmd,
                    commandIndex: commandIndex,
                    type: 'arc'
                });

            } catch (e) {
                console.error('Arc with segments error:', e);
                const from = project3D(cmd.from.x, cmd.from.y, cmd.from.z);
                const to = project3D(cmd.to.x, cmd.to.y, cmd.to.z);
                ctx.moveTo(from.x, from.y);
                ctx.lineTo(to.x, to.y);
                trajectorySegments.push({
                    points: [from, to],
                    command: cmd,
                    commandIndex: commandIndex,
                    type: 'line'
                });
            }
        }

        // Animation functions
        function toggleAnimation() {
            if (currentCommands.length === 0) {
                showMessage('請先解析G-code才能開始動畫。', 'error');
                return;
            }
            isAnimating ? stopAnimation() : startAnimation();
        }

        function setSpeed(speed) {
            animationSpeed = speed;
            document.querySelectorAll('.speed-btn').forEach(btn => {
                btn.classList.remove('active');
                if (parseFloat(btn.dataset.speed) === speed) {
                    btn.classList.add('active');
                }
            });
            if (isAnimating && !animationPaused) {
                clearInterval(animationInterval);
                const interval = Math.max(25, 200 / animationSpeed);
                animationInterval = setInterval(animateStep, interval);
            }
        }

        function startAnimation() {
            isAnimating = true;
            animationPaused = false;
            animationFrame = 0;
            drawnCommands = [];
            toolPath = []; // 重置刀具路徑
            machiningPaths = []; // 重置加工路徑

            if (currentCommands.length > 0) {
                toolPosition = { x: currentCommands[0].from.x, y: currentCommands[0].from.y, z: currentCommands[0].from.z };
                toolPath.push({ ...toolPosition }); // 記錄起始位置
            }

            // 更新刀徑
            updateToolDiameter();

            document.getElementById('animationBtn').textContent = '⏸️ 停止';
            document.getElementById('animationBtn').classList.add('active');
            document.getElementById('animationControls').style.display = 'block';
            document.getElementById('animationTotal').textContent = currentCommands.length;
            document.getElementById('pauseBtn').textContent = '暫停';

            const interval = Math.max(25, 200 / animationSpeed);
            animationInterval = setInterval(animateStep, interval);

            showMessage('3D CAM動畫已開始（包含刀具路徑顯示）。', 'success');
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

            // 保留刀具路徑和加工路徑 - 不清除
            // toolPath = []; // 註解掉，保留刀具路徑
            // machiningPaths = []; // 註解掉，保留加工路徑

            // 計算完整的加工路徑（基於所有指令）
            if (currentCommands.length > 0) {
                calculateFullMachiningPaths();
                // 保持刀具在最終位置
                const lastCmd = currentCommands[currentCommands.length - 1];
                toolPosition = { x: lastCmd.to.x, y: lastCmd.to.y, z: lastCmd.to.z };
            }

            redraw3D();
            showMessage('動畫結束，刀具路徑和加工範圍已保留。', 'success');
        }

        function pauseAnimation() {
            if (!isAnimating) return;

            if (animationPaused) {
                animationPaused = false;
                const interval = Math.max(25, 200 / animationSpeed);
                animationInterval = setInterval(animateStep, interval);
                document.getElementById('pauseBtn').textContent = '暫停';
            } else {
                animationPaused = true;
                if (animationInterval) {
                    clearInterval(animationInterval);
                    animationInterval = null;
                }
                document.getElementById('pauseBtn').textContent = '繼續';
            }
        }

        function animateStep() {
            if (animationFrame >= currentCommands.length) {
                stopAnimation();
                return;
            }

            const cmd = currentCommands[animationFrame];
            drawnCommands.push(cmd);

            // 更新刀具位置
            toolPosition.x = cmd.to.x;
            toolPosition.y = cmd.to.y;
            toolPosition.z = cmd.to.z;

            // 記錄刀具路徑
            toolPath.push({ ...toolPosition });

            // 更新加工路徑
            updateMachiningPaths();

            document.getElementById('animationProgress').textContent = animationFrame + 1;
            document.getElementById('currentX').textContent = cmd.to.x.toFixed(2);
            document.getElementById('currentY').textContent = cmd.to.y.toFixed(2);
            document.getElementById('currentZ').textContent = cmd.to.z.toFixed(2);
            document.getElementById('currentOperation').textContent = '#' + (cmd.operation_id + 1);
            document.getElementById('currentCommand').textContent = cmd.type;

            const progress = ((animationFrame + 1) / currentCommands.length) * 100;
            document.getElementById('progressBar').style.width = progress + '%';

            animationFrame++;
            redraw3D();
        }

        function clearAll() {
            if (isAnimating) stopAnimation();
            document.getElementById('gcodeInput').value = '';
            currentCommands = [];
            drawnCommands = [];
            toolPath = [];
            machiningPaths = [];
            animationFrame = 0;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            resetView3D();

            // 重置刀徑為預設值
            document.getElementById('toolDiameter').value = 6;
            toolDiameter = 6;

            ['totalCommands', 'operationCount', 'totalDistance', 'workVolume'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.textContent = id === 'workVolume' ? '--' : '0';
            });

            document.getElementById('operationsInfo').style.display = 'none';
            showMessage('已清除所有內容。', 'info');
        }

        // View functions
        function resetView3D() {
            rotationX = 30; rotationY = 45; zoom3D = 1.0; offsetX = 0; offsetY = 0;
            updateRotationDisplay(); updateZoomDisplay(); redraw3D();
        }

        function viewTop() { rotationX = 90; rotationY = 0; updateRotationDisplay(); redraw3D(); }
        function viewFront() { rotationX = 0; rotationY = 0; updateRotationDisplay(); redraw3D(); }
        function viewRight() { rotationX = 0; rotationY = 90; updateRotationDisplay(); redraw3D(); }
        function viewIsometric() { rotationX = 30; rotationY = 45; updateRotationDisplay(); redraw3D(); }

        function zoomIn3D() { zoom3D *= 1.25; updateZoomDisplay(); redraw3D(); }
        function zoomOut3D() { zoom3D *= 0.8; updateZoomDisplay(); redraw3D(); }

        function fitToView3D() {
            if (currentCommands.length === 0) return;
            let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity, minZ = Infinity, maxZ = -Infinity;
            for (let cmd of currentCommands) {
                minX = Math.min(minX, cmd.from.x, cmd.to.x);
                maxX = Math.max(maxX, cmd.from.x, cmd.to.x);
                minY = Math.min(minY, cmd.from.y, cmd.to.y);
                maxY = Math.max(maxY, cmd.from.y, cmd.to.y);
                minZ = Math.min(minZ, cmd.from.z, cmd.to.z);
                maxZ = Math.max(maxZ, cmd.from.z, cmd.to.z);
            }
            if (!isFinite(minX)) return;
            const maxRange = Math.max(maxX - minX || 1, maxY - minY || 1, maxZ - minZ || 1);
            zoom3D = Math.min(canvas.width, canvas.height) * 0.6 / maxRange;
            offsetX = 0; offsetY = 0;
            updateZoomDisplay(); redraw3D();
        }

        function toggleGrid() { showGrid = !showGrid; redraw3D(); }
        function toggleAxes() { showAxes = !showAxes; redraw3D(); }

        // Utility functions
        function testConnection() {
            showMessage('測試伺服器連接中...', 'info');
            fetch('/parse', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({gcode: 'G01 X10 Y10'})
            })
            .then(response => response.ok ? response.json() : Promise.reject('HTTP ' + response.status))
            .then(() => showMessage('✅ 伺服器連接正常！', 'success'))
            .catch(error => showMessage('❌ 連接失敗: ' + error, 'error'));
        }

        function loadSampleCode() {
            const sample = `G01 X0 Y0 Z2 F500
G01 X10 Y0
G01 X10 Y10
G02 X0 Y10 R5
G01 X0 Y0
G01 X5 Y5
G02 X15 Y5 R5
G03 X25 Y15 R10
G01 X25 Y25
G02 X5 Y25 I-10 J0
G01 X5 Y5
G00 Z50`;
            document.getElementById('gcodeInput').value = sample;
            showMessage('已載入範例程式碼。', 'success');
        }

        function loadCAMCode() {
            const cam = `N42
(*** ENDMILL =D6.***)
G100T42G90G00G54.1P1X-0.399Y34.226A0M3
M8G43H42Z50.
Z13.
G01Z4.F150
G41X-0.439Y37.726D42
G03X-1.525Y37.698R37.737
G01X-2.586Y37.633
X-3.089Y37.602
X-4.623Y37.445
X-6.125Y37.228
G03X-18.024Y33.144R38.178
X-23.213Y29.617R32.072
X-29.477Y21.732R25.32
X-31.916Y13.328R24.626
X-31.621Y5.722R28.018
G01X-31.291Y4.19
G03X-29.081Y-1.867R28.92
X-27.164Y-5.176R44.413
G01X-26.508Y-6.177
X-25.849Y-7.131
X-25.19Y-8.041
X-24.533Y-8.907
X-23.877Y-9.732
X-23.226Y-10.518
X-21.918Y-12.003
X-20.64Y-13.345
G03X-14.845Y-18.362R51.569
G01X-13.824Y-19.098
G03X1.828Y-23.499R23.583
X9.987Y-21.349R23.741
G01X11.168Y-20.756
X12.3Y-20.117
X13.402Y-19.464
X14.474Y-18.801
X15.517Y-18.13
X16.532Y-17.45
X17.519Y-16.764
G03X25.285Y-10.359R72.23
G01X26.021Y-9.644
G03X33.078Y3.535R25.03
G01X33.214Y4.296
X33.325Y5.048
X33.414Y5.792
X33.481Y6.526
X33.551Y7.975
X33.544Y9.381
X33.466Y10.741
X33.324Y12.052
X33.125Y13.315
G03X25.524Y27.701R27.175
G01X24.472Y28.688
X23.439Y29.562
G03X-1.525Y37.698R37.737
G01X-2.586Y37.633
G40X-2.372Y34.14
G00Z50.

X-1.657Y33.185
Z13.
G01Z4.F150
G41X-1.481Y29.69D42F1000
G02X0.333Y29.724R29.184
X15.463Y25.395R29.858
G01X16.178Y24.945
G02X19.918Y21.991R24.492
X25.251Y11.891R19.137
X25.224Y5.063R18.924
X20.39Y-3.962R17.018
G01X19.779Y-4.554
X18.384Y-5.848
X16.927Y-7.116
X15.382Y-8.376
X13.716Y-9.644
G02X9.272Y-12.612R62.995
G01X8.294Y-13.192
G02X4.506Y-14.903R17.413
X-5.618Y-14.526R15.75
X-8.485Y-13.056R16.06
G01X-9.231Y-12.547
X-10.088Y-11.93
G02X-18.201Y-4.016R42.273
G01X-18.765Y-3.274
X-19.317Y-2.512
X-19.869Y-1.712
X-20.419Y-0.873
X-20.965Y0.007
G02X-23.839Y7.685R20.615
X-23.883Y13.106R19.654
X-22.004Y18.751R16.359
X-17.364Y24.061R17.694
X-13.281Y26.596R25.428
X-1.203Y29.703R29.972
X0.333Y29.724R29.858
G40G01X0.374Y33.224
G00Z50.
G00X-85.Y196.M9G54.1P1A0
M211
M30`;
            document.getElementById('gcodeInput').value = cam;
            showMessage('已載入CAM程式碼！', 'success');
        }

        function showMessage(msg, type) {
            try {
                const area = document.getElementById('messageArea');
                const className = type === 'error' ? 'error-message' : 'success-message';
                area.innerHTML = '<div class="' + className + '">' + msg + '</div>';
                if (type !== 'error') {
                    setTimeout(() => {
                        if (!area.querySelector('.debug-info')) area.innerHTML = '';
                    }, 8000);
                }
            } catch (e) {
                console.error('Show message error:', e);
            }
        }

        // 新增：刀具相關函數
        function updateToolDiameter() {
            try {
                const input = document.getElementById('toolDiameter');
                toolDiameter = parseFloat(input.value) || 6;
                toolDiameter = Math.max(0.1, Math.min(50, toolDiameter)); // 限制範圍
                input.value = toolDiameter; // 確保顯示正確的值

                console.log('刀徑已更新為:', toolDiameter + 'mm');

                // 如果正在動畫中，重新計算加工路徑
                if (isAnimating) {
                    updateMachiningPaths();
                    redraw3D();
                }
            } catch (e) {
                console.error('更新刀徑錯誤:', e);
            }
        }

        // 計算加工路徑（刀具邊緣路徑）
        function updateMachiningPaths() {
            machiningPaths = [];
            const radius = toolDiameter / 2;

            try {
                for (let i = 0; i < drawnCommands.length; i++) {
                    const cmd = drawnCommands[i];

                    if (cmd.type === 'G01') {
                        // 直線加工路徑
                        const dx = cmd.to.x - cmd.from.x;
                        const dy = cmd.to.y - cmd.from.y;
                        const length = Math.sqrt(dx * dx + dy * dy);

                        if (length > 0.001) {
                            // 垂直向量（法向量）
                            const nx = -dy / length;
                            const ny = dx / length;

                            // 刀具左側和右側邊緣點
                            const leftFrom = {
                                x: cmd.from.x + nx * radius,
                                y: cmd.from.y + ny * radius,
                                z: cmd.from.z
                            };
                            const leftTo = {
                                x: cmd.to.x + nx * radius,
                                y: cmd.to.y + ny * radius,
                                z: cmd.to.z
                            };
                            const rightFrom = {
                                x: cmd.from.x - nx * radius,
                                y: cmd.from.y - ny * radius,
                                z: cmd.from.z
                            };
                            const rightTo = {
                                x: cmd.to.x - nx * radius,
                                y: cmd.to.y - ny * radius,
                                z: cmd.to.z
                            };

                            machiningPaths.push({
                                type: 'line',
                                from: leftFrom,
                                to: leftTo,
                                side: 'left'
                            });
                            machiningPaths.push({
                                type: 'line',
                                from: rightFrom,
                                to: rightTo,
                                side: 'right'
                            });
                        }
                    } else if (cmd.type === 'G02' || cmd.type === 'G03') {
                        // 圓弧加工路徑（簡化處理）
                        const segments = 8; // 圓弧分段數
                        for (let j = 0; j <= segments; j++) {
                            const t = j / segments;
                            const angle = t * Math.PI / 4; // 簡化角度計算

                            const nx = Math.cos(angle);
                            const ny = Math.sin(angle);

                            const centerX = cmd.from.x + (cmd.to.x - cmd.from.x) * t;
                            const centerY = cmd.from.y + (cmd.to.y - cmd.from.y) * t;

                            if (j > 0) {
                                const prevT = (j - 1) / segments;
                                const prevX = cmd.from.x + (cmd.to.x - cmd.from.x) * prevT;
                                const prevY = cmd.from.y + (cmd.to.y - cmd.from.y) * prevT;

                                machiningPaths.push({
                                    type: 'line',
                                    from: {
                                        x: prevX + nx * radius,
                                        y: prevY + ny * radius,
                                        z: cmd.from.z
                                    },
                                    to: {
                                        x: centerX + nx * radius,
                                        y: centerY + ny * radius,
                                        z: cmd.to.z
                                    },
                                    side: 'arc'
                                });
                            }
                        }
                    }
                }
            } catch (e) {
                console.error('計算加工路徑錯誤:', e);
            }
        }

        // 新增：計算完整的加工路徑（用於動畫結束後）
        function calculateFullMachiningPaths() {
            machiningPaths = [];
            toolPath = []; // 重新計算完整路徑

            const radius = toolDiameter / 2;

            try {
                // 重新計算完整的刀具路徑
                if (currentCommands.length > 0) {
                    toolPath.push({ x: currentCommands[0].from.x, y: currentCommands[0].from.y, z: currentCommands[0].from.z });

                    for (let cmd of currentCommands) {
                        toolPath.push({ x: cmd.to.x, y: cmd.to.y, z: cmd.to.z });
                    }
                }

                // 計算完整的加工路徑
                for (let i = 0; i < currentCommands.length; i++) {
                    const cmd = currentCommands[i];

                    if (cmd.type === 'G01' && cmd.is_cutting) {
                        // 只為切削移動計算加工路徑
                        const dx = cmd.to.x - cmd.from.x;
                        const dy = cmd.to.y - cmd.from.y;
                        const length = Math.sqrt(dx * dx + dy * dy);

                        if (length > 0.001) {
                            // 垂直向量（法向量）
                            const nx = -dy / length;
                            const ny = dx / length;

                            // 刀具左側和右側邊緣點
                            machiningPaths.push({
                                type: 'line',
                                from: {
                                    x: cmd.from.x + nx * radius,
                                    y: cmd.from.y + ny * radius,
                                    z: cmd.from.z
                                },
                                to: {
                                    x: cmd.to.x + nx * radius,
                                    y: cmd.to.y + ny * radius,
                                    z: cmd.to.z
                                },
                                side: 'left'
                            });
                            machiningPaths.push({
                                type: 'line',
                                from: {
                                    x: cmd.from.x - nx * radius,
                                    y: cmd.from.y - ny * radius,
                                    z: cmd.from.z
                                },
                                to: {
                                    x: cmd.to.x - nx * radius,
                                    y: cmd.to.y - ny * radius,
                                    z: cmd.to.z
                                },
                                side: 'right'
                            });
                        }
                    } else if ((cmd.type === 'G02' || cmd.type === 'G03') && cmd.is_cutting) {
                        // 圓弧加工路徑的詳細計算
                        addArcMachiningPath(cmd, radius);
                    }
                }

                console.log('完整加工路徑計算完成:', machiningPaths.length, '條路徑');
                console.log('完整刀具路徑計算完成:', toolPath.length, '個點');

            } catch (e) {
                console.error('計算完整加工路徑錯誤:', e);
            }
        }

        // 新增：為圓弧添加加工路徑
        function addArcMachiningPath(cmd, radius) {
            try {
                // 簡化的圓弧邊界計算
                const segments = Math.max(8, Math.ceil(Math.abs(cmd.r || 10) / 2));

                for (let j = 0; j < segments; j++) {
                    const t1 = j / segments;
                    const t2 = (j + 1) / segments;

                    // 簡單的線性插值（可以改進為真正的圓弧計算）
                    const x1 = cmd.from.x + (cmd.to.x - cmd.from.x) * t1;
                    const y1 = cmd.from.y + (cmd.to.y - cmd.from.y) * t1;
                    const x2 = cmd.from.x + (cmd.to.x - cmd.from.x) * t2;
                    const y2 = cmd.from.y + (cmd.to.y - cmd.from.y) * t2;

                    const dx = x2 - x1;
                    const dy = y2 - y1;
                    const length = Math.sqrt(dx * dx + dy * dy);

                    if (length > 0.001) {
                        const nx = -dy / length;
                        const ny = dx / length;

                        machiningPaths.push({
                            type: 'line',
                            from: { x: x1 + nx * radius, y: y1 + ny * radius, z: cmd.from.z },
                            to: { x: x2 + nx * radius, y: y2 + ny * radius, z: cmd.to.z },
                            side: 'arc-left'
                        });
                        machiningPaths.push({
                            type: 'line',
                            from: { x: x1 - nx * radius, y: y1 - ny * radius, z: cmd.from.z },
                            to: { x: x2 - nx * radius, y: y2 - ny * radius, z: cmd.to.z },
                            side: 'arc-right'
                        });
                    }
                }
            } catch (e) {
                console.error('圓弧加工路徑計算錯誤:', e);
            }
        }
        // 新增：清除刀具路徑函數
        function clearToolPaths() {
            toolPath = [];
            machiningPaths = [];
            toolPosition = null;
            redraw3D();
            showMessage('刀具路徑已清除。', 'info');
        }

        function checkTrajectoryHover(event) {
            if (trajectorySegments.length === 0) return;

            const rect = canvas.getBoundingClientRect();
            const mouseX = event.clientX - rect.left;
            const mouseY = event.clientY - rect.top;

            let closestSegment = null;
            let minDistance = Infinity;
            const threshold = 8; // 滑鼠檢測閾值（像素）

            for (let segment of trajectorySegments) {
                if (segment.type === 'line') {
                    // 直線距離檢測
                    const distance = pointToLineDistance(mouseX, mouseY, segment.points[0], segment.points[1]);
                    if (distance < threshold && distance < minDistance) {
                        minDistance = distance;
                        closestSegment = segment;
                    }
                } else if (segment.type === 'arc') {
                    // 圓弧距離檢測（檢測到圓弧上各點的最小距離）
                    for (let i = 0; i < segment.points.length - 1; i++) {
                        const distance = pointToLineDistance(mouseX, mouseY, segment.points[i], segment.points[i + 1]);
                        if (distance < threshold && distance < minDistance) {
                            minDistance = distance;
                            closestSegment = segment;
                        }
                    }
                }
            }

            if (closestSegment !== hoveredSegment) {
                hoveredSegment = closestSegment;
                if (hoveredSegment) {
                    showTrajectoryInfo(hoveredSegment, event);
                } else {
                    hideTrajectoryInfo();
                }
                redraw3D();
            }
        }

        // 計算點到線段的距離
        function pointToLineDistance(px, py, p1, p2) {
            const A = px - p1.x;
            const B = py - p1.y;
            const C = p2.x - p1.x;
            const D = p2.y - p1.y;

            const dot = A * C + B * D;
            const lenSq = C * C + D * D;

            if (lenSq === 0) return Math.sqrt(A * A + B * B);

            let param = dot / lenSq;
            param = Math.max(0, Math.min(1, param));

            const xx = p1.x + param * C;
            const yy = p1.y + param * D;

            const dx = px - xx;
            const dy = py - yy;
            return Math.sqrt(dx * dx + dy * dy);
        }

        // 顯示軌跡資訊
        function showTrajectoryInfo(segment, event) {
            const info = document.getElementById('trajectoryInfo');
            const cmd = segment.command;

            // 更新資訊內容
            document.getElementById('trajCommand').textContent = cmd.type;
            document.getElementById('trajLineNumber').textContent = cmd.line_number || '未知';

            // 格式化座標資訊
            let coordText = '';
            if (cmd.type === 'G02' || cmd.type === 'G03') {
                coordText = `X${cmd.to.x.toFixed(2)} Y${cmd.to.y.toFixed(2)}`;
                if (cmd.r !== 0) {
                    coordText += ` R${cmd.r.toFixed(2)}`;
                }
                if (cmd.i !== 0 || cmd.j !== 0) {
                    coordText += ` I${cmd.i.toFixed(2)} J${cmd.j.toFixed(2)}`;
                }
            } else {
                coordText = `X${cmd.to.x.toFixed(2)} Y${cmd.to.y.toFixed(2)} Z${cmd.to.z.toFixed(2)}`;
            }
            document.getElementById('trajCoords').textContent = coordText;

            // 顯示原始程式碼
            document.getElementById('trajOriginal').textContent = cmd.original_line || '程式碼不可用';

            // 顯示並定位資訊框
            info.style.display = 'block';

            // 可選：讓資訊框跟隨滑鼠（但保持在合理位置）
            // const rect = canvas.getBoundingClientRect();
            // info.style.left = Math.min(event.clientX + 10, window.innerWidth - 300) + 'px';
            // info.style.top = Math.max(10, event.clientY - 100) + 'px';
        }

        // 隱藏軌跡資訊
        function hideTrajectoryInfo() {
            document.getElementById('trajectoryInfo').style.display = 'none';
            hoveredSegment = null;
        }

        // 繪製懸停效果
        function drawHoverEffect() {
            if (!hoveredSegment) return;

            ctx.save();
            ctx.strokeStyle = '#FFD700'; // 金色高亮
            ctx.lineWidth = 6;
            ctx.setLineDash([]);
            ctx.globalAlpha = 0.8;

            ctx.beginPath();
            if (hoveredSegment.type === 'line') {
                const points = hoveredSegment.points;
                ctx.moveTo(points[0].x, points[0].y);
                ctx.lineTo(points[1].x, points[1].y);
            } else if (hoveredSegment.type === 'arc') {
                const points = hoveredSegment.points;
                for (let i = 0; i < points.length; i++) {
                    if (i === 0) {
                        ctx.moveTo(points[i].x, points[i].y);
                    } else {
                        ctx.lineTo(points[i].x, points[i].y);
                    }
                }
            }
            ctx.stroke();
            ctx.restore();
        }
    </script>
</body>
</html>'''

class SafeCNCRequestHandler(BaseHTTPRequestHandler):
    """Safe request handler for exe packaging"""

    def __init__(self, *args, **kwargs):
        self.parser_instance = SafeMultiOperationCAMParser()
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        """Override to prevent encoding issues in exe"""
        try:
            super().log_message(format, *args)
        except:
            pass

    def do_GET(self):
        try:
            if self.path == '/' or self.path == '/index.html':
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(CLEAN_CAM_HTML.encode('utf-8', errors='ignore'))
            else:
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            self.parser_instance.safe_print(f"GET request error: {e}")
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
                commands = self.parser_instance.parse_gcode(gcode)

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
            self.parser_instance.safe_print(f"POST request error: {e}")
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
    setup_encoding()
    port = find_free_port()
    server_address = ('localhost', port)

    try:
        httpd = HTTPServer(server_address, SafeCNCRequestHandler)

        try:
            print(f"🎯 3D CAM可視化工具 (圓弧修正版)")
            print(f"✅ 圓弧計算問題完全修正")
            print(f"✅ 所有Pylance錯誤已修正")
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
