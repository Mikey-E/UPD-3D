#!/usr/bin/env python3
"""
Standalone Three.js Point Cloud Viewer (No Gradio HTML restrictions)
Creates a separate HTML file and serves it via iframe to bypass JavaScript restrictions
"""


import gradio as gr
import numpy as np
import os
import struct
import shutil
import tempfile
import threading
import time
import base64
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socket
import json
from datetime import datetime, timedelta

# Parse arguments at the top so they are available in the Blocks context
import argparse
import sys
parser = argparse.ArgumentParser(description='Point Cloud Viewer')
parser.add_argument('--share', action='store_true', help='Enable public sharing via Gradio tunnel')
parser.add_argument('--host', default='0.0.0.0', help='Host address (default: 0.0.0.0)')
parser.add_argument('--port', type=int, default=7871, help='Port number (default: 7871)')
parser.add_argument('--threedfront-path', default='/project/3dllms/melgin/datasets/3d-grand_unzipped/3D-FRONT', 
                   help='Path to 3D-FRONT dataset directory')
parser.add_argument('--crops3d-path', default='/project/3dllms/melgin/datasets/CEA/Crops3D',
                   help='Path to Crops3D dataset directory')
args, _ = parser.parse_known_args()

def on_dataset_change_wrapper(dataset_name, user):
    return on_dataset_change(dataset_name, args.threedfront_path, args.crops3d_path, user)

def load_questions(dataset_name, current_file):
    """Load questions for the current point cloud"""
    if not current_file:
        return ["No questions available"] * 12
    
    # Map dataset_name to upd_text folder
    if dataset_name == "3D-FRONT_test":
        upd_dataset = "3D-FRONT"
    elif dataset_name == "Crops3D_test":
        upd_dataset = "Crops3D_gpt-5-nano"
    else:
        return ["Invalid dataset"] * 12
    
    # Extract identifier@scene from current_file path
    current_dir = os.path.dirname(current_file)
    basename = os.path.basename(current_file)
    
    if dataset_name == "3D-FRONT_test":
        # Path: /path/3D-FRONT/identifier/scene/scene.ply
        scene_dir = os.path.basename(current_dir)
        identifier = os.path.basename(os.path.dirname(current_dir))
        identifier_scene = f"{identifier}@{scene_dir}"
    elif dataset_name == "Crops3D_test":
        # Path: /path/Crops3D/identifier/scene.ply
        identifier = os.path.basename(current_dir)
        scene = basename[:-4] if basename.endswith('.ply') else basename
        identifier_scene = f"{identifier}@{scene}"
    else:
        return ["Invalid dataset"] * 12
    
    # Question folders (excluding standard_answer)
    question_folders = [
        "aad_additional_instruction", "aad_additional_option", "aad_base",
        "iasd_additional_instruction", "iasd_additional_option", "iasd_base",
        "ivqd_additional_instruction", "ivqd_additional_option", "ivqd_base",
        "open_ended", "open_ended_additional_instruction", "standard"
    ]
    
    questions = []
    for folder in question_folders:
        question_file = f"./upd_text/{upd_dataset}/{folder}/{identifier_scene}.txt"
        try:
            with open(question_file, 'r') as f:
                question_text = f.read().strip()
                questions.append(question_text)
        except FileNotFoundError:
            questions.append(f"Question file not found: {question_file}")
        except Exception as e:
            questions.append(f"Error loading question: {str(e)}")
    
    return questions

def get_ply_point_count(file_path):
    """Get the total number of points in a PLY file"""
    if not file_path or not os.path.exists(file_path):
        return 0
    
    try:
        with open(file_path, 'rb') as f:
            # Read header to find vertex count
            line = f.readline().decode('utf-8').strip()
            if line != 'ply':
                return 0
            
            while True:
                line = f.readline().decode('utf-8').strip()
                if line.startswith('element vertex'):
                    vertex_count = int(line.split()[2])
                    return vertex_count
                elif line == 'end_header':
                    break
        
        return 0
    except:
        return 0

def read_ply_for_js(file_path, max_points=50000):
    """Read PLY file (binary or ASCII) and convert to JavaScript format"""
    try:
        vertices = []
        colors = []
        
        with open(file_path, 'rb') as f:
            # Read header
            line = f.readline().decode('utf-8').strip()
            if line != 'ply':
                return None, None, "Not a valid PLY file"
            
            format_type = None
            vertex_count = 0
            properties = []
            
            while True:
                line = f.readline().decode('utf-8').strip()
                if line.startswith('format'):
                    format_type = line.split()[1]
                elif line.startswith('element vertex'):
                    vertex_count = int(line.split()[2])
                elif line.startswith('property'):
                    prop_info = line.split()
                    properties.append((prop_info[1], prop_info[2]))
                elif line == 'end_header':
                    break
            
            if format_type not in ['binary_little_endian', 'ascii 1.0']:
                return None, None, f"Unsupported PLY format: {format_type}"
            
            is_binary = format_type == 'binary_little_endian'
            
            if is_binary:
                # Binary format
                bytes_per_vertex = 0
                property_map = []
                
                for prop_type, prop_name in properties:
                    if prop_type == 'double':
                        bytes_per_vertex += 8
                        property_map.append((prop_name, 'double', 8))
                    elif prop_type == 'float':
                        bytes_per_vertex += 4
                        property_map.append((prop_name, 'float', 4))
                    elif prop_type == 'uchar':
                        bytes_per_vertex += 1
                        property_map.append((prop_name, 'uchar', 1))
                    elif prop_type == 'short':
                        bytes_per_vertex += 2
                        property_map.append((prop_name, 'short', 2))
                
                # Sample vertices
                sample_stride = max(1, vertex_count // max_points)
                valid_count = 0
                
                for i in range(vertex_count):
                    vertex_data = f.read(bytes_per_vertex)
                    if len(vertex_data) < bytes_per_vertex:
                        break
                    
                    # Skip for sampling
                    if i % sample_stride != 0:
                        continue
                    
                    # Parse vertex
                    pos = 0
                    vertex_values = {}
                    
                    for prop_name, prop_type, prop_size in property_map:
                        if prop_type == 'double':
                            value = struct.unpack('<d', vertex_data[pos:pos+8])[0]
                        elif prop_type == 'float':
                            value = struct.unpack('<f', vertex_data[pos:pos+4])[0]
                        elif prop_type == 'uchar':
                            value = struct.unpack('<B', vertex_data[pos:pos+1])[0]
                        elif prop_type == 'short':
                            value = struct.unpack('<h', vertex_data[pos:pos+2])[0]
                        
                        vertex_values[prop_name] = value
                        pos += prop_size
                    
                    # Extract coordinates
                    x = vertex_values.get('x', 0)
                    y = vertex_values.get('y', 0)
                    z = vertex_values.get('z', 0)
                    
                    # Filter NaN/Inf
                    if np.isfinite([x, y, z]).all():
                        vertices.extend([x, y, z])  # Flatten for Three.js
                        
                        # Colors
                        r = vertex_values.get('red', 128) / 255.0
                        g = vertex_values.get('green', 128) / 255.0
                        b = vertex_values.get('blue', 128) / 255.0
                        colors.extend([r, g, b])
                        
                        valid_count += 1
                        if valid_count >= max_points:
                            break
            else:
                # ASCII format
                sample_stride = max(1, vertex_count // max_points)
                valid_count = 0
                
                for i in range(vertex_count):
                    line = f.readline().decode('utf-8').strip()
                    if not line:
                        break
                    
                    # Skip for sampling
                    if i % sample_stride != 0:
                        continue
                    
                    # Parse ASCII line
                    values = line.split()
                    if len(values) < len(properties):
                        continue
                    
                    vertex_values = {}
                    for j, (prop_type, prop_name) in enumerate(properties):
                        if prop_type in ['double', 'float']:
                            vertex_values[prop_name] = float(values[j])
                        elif prop_type == 'uchar':
                            vertex_values[prop_name] = int(values[j])
                    
                    # Extract coordinates
                    x = vertex_values.get('x', 0)
                    y = vertex_values.get('y', 0)
                    z = vertex_values.get('z', 0)
                    
                    # Filter NaN/Inf
                    if np.isfinite([x, y, z]).all():
                        vertices.extend([x, y, z])
                        
                        # Colors
                        r = vertex_values.get('red', 128) / 255.0
                        g = vertex_values.get('green', 128) / 255.0
                        b = vertex_values.get('blue', 128) / 255.0
                        colors.extend([r, g, b])
                        
                        valid_count += 1
                        if valid_count >= max_points:
                            break
        
        if len(vertices) == 0:
            return None, None, "No valid vertices found"
        
        # Check for NaN/Inf in first few vertices
        first_vertices = vertices[:9]  # First 3 points
        
        return vertices, colors, f"Loaded {valid_count} valid points"
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, None, f"Error: {str(e)}"

def create_standalone_html(vertices, colors, title="Point Cloud"):
    """Create standalone HTML with Three.js viewer"""
    
    # Convert to JavaScript arrays
    js_vertices = "[" + ",".join(map(str, vertices)) + "]"
    js_colors = "[" + ",".join(map(str, colors)) + "]"
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ 
            margin: 0; 
            background: #f0f0f0; 
            font-family: Arial, sans-serif;
            overflow: hidden;
        }}
        #container {{ 
            width: 100vw; 
            height: 100vh; 
            position: relative;
        }}
        #info {{
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 10px;
            border-radius: 5px;
            font-size: 14px;
            z-index: 1000;
        }}
        #controls {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 10px;
            border-radius: 5px;
            z-index: 1000;
        }}
        button {{
            background: #4CAF50;
            color: white;
            border: none;
            padding: 5px 10px;
            margin: 2px;
            border-radius: 3px;
            cursor: pointer;
        }}
        button:hover {{ background: #45a049; }}
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>
    <div id="container"></div>
    <div id="info">
        <strong>{title} Viewer</strong><br>
        Points: {len(vertices)//3:,}<br>
        <span id="fps">FPS: --</span>
    </div>
    <div id="controls">
        <button onclick="resetView()">Reset View</button><br>
        <button onclick="changePointSize(1)">Size +</button>
        <button onclick="changePointSize(-1)">Size -</button>
    </div>

    <script>
        // Global variables
        let scene, camera, renderer, points, controls;
        let autoRotate = true; // Start with auto-rotation enabled
        let pointSize = 0.02;
        let frameCount = 0;
        let lastTime = Date.now();
        let centerPoint = null;
        let showCenter = false;
        
        // Initialize Three.js scene
        function init() {{
            console.log("Initializing Three.js scene...");
            
            // Scene
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0xf0f0f0);
            
            // Camera
            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            
            // Renderer
            renderer = new THREE.WebGLRenderer({{ antialias: true }});
            renderer.setSize(window.innerWidth, window.innerHeight);
            document.getElementById('container').appendChild(renderer.domElement);
            
            // Point cloud data
            const vertices = new Float32Array({js_vertices});
            const colors = new Float32Array({js_colors});
            
            console.log("Vertices loaded:", vertices.length / 3);
            console.log("Colors loaded:", colors.length / 3);
            
            // Create geometry
            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
            geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
            
            // Create material
            const material = new THREE.PointsMaterial({{ 
                size: pointSize,
                vertexColors: true,
                sizeAttenuation: true
            }});
            
            // Create points
            points = new THREE.Points(geometry, material);
            scene.add(points);
            
            // Calculate bounds and position camera
            geometry.computeBoundingBox();
            const box = geometry.boundingBox;
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);
            
            camera.position.set(
                center.x + maxDim * 0.2,
                center.y + maxDim * 0.1,
                center.z + maxDim * 0.2
            );
            camera.lookAt(center);
            
            console.log("Bounding box:", box);
            console.log("Camera position:", camera.position);
            console.log("Point cloud center:", center);
            
            // Create center point marker (invisible by default)
            const centerGeometry = new THREE.SphereGeometry(maxDim * 0.02, 8, 6);
            const centerMaterial = new THREE.MeshBasicMaterial({{ color: 0xff0000 }});
            centerPoint = new THREE.Mesh(centerGeometry, centerMaterial);
            centerPoint.position.copy(center);
            centerPoint.visible = false;
            scene.add(centerPoint);
            
            // Add basic controls
            setupControls();
            
            // Start render loop
            animate();
        }}
        
        function setupControls() {{
            let isDragging = false;
            let previousMousePosition = {{ x: 0, y: 0 }};
            
            // Get point cloud center for proper rotation
            const box = points.geometry.boundingBox;
            const center = box.getCenter(new THREE.Vector3());
            
            renderer.domElement.addEventListener('mousedown', function(e) {{
                isDragging = true;
                autoRotate = false; // Disable auto-rotation when user starts interacting
                previousMousePosition.x = e.clientX;
                previousMousePosition.y = e.clientY;
            }});
            
            renderer.domElement.addEventListener('mousemove', function(e) {{
                if (isDragging) {{
                    const deltaMove = {{
                        x: e.clientX - previousMousePosition.x,
                        y: e.clientY - previousMousePosition.y
                    }};
                    
                    // Rotate around point cloud center, not origin
                    const spherical = new THREE.Spherical();
                    const offset = new THREE.Vector3();
                    offset.copy(camera.position).sub(center);
                    spherical.setFromVector3(offset);
                    
                    spherical.theta -= deltaMove.x * 0.01;
                    spherical.phi += deltaMove.y * 0.01;
                    spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi));
                    
                    offset.setFromSpherical(spherical);
                    camera.position.copy(center).add(offset);
                    camera.lookAt(center);
                    
                    previousMousePosition.x = e.clientX;
                    previousMousePosition.y = e.clientY;
                }}
            }});
            
            renderer.domElement.addEventListener('mouseup', function() {{
                isDragging = false;
            }});
            
            // Zoom with wheel - maintain center focus
            renderer.domElement.addEventListener('wheel', function(e) {{
                autoRotate = false; // Disable auto-rotation when user zooms
                const zoomFactor = e.deltaY > 0 ? 1.1 : 0.9;
                const direction = new THREE.Vector3();
                direction.subVectors(camera.position, center);
                direction.multiplyScalar(zoomFactor);
                camera.position.copy(center).add(direction);
                e.preventDefault();
            }});
            
            // Window resize
            window.addEventListener('resize', function() {{
                camera.aspect = window.innerWidth / window.innerHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(window.innerWidth, window.innerHeight);
            }});
        }}
        
        function animate() {{
            requestAnimationFrame(animate);
            
            if (autoRotate && points) {{
                // Rotate around point cloud center
                const box = points.geometry.boundingBox;
                const center = box.getCenter(new THREE.Vector3());
                
                const radius = camera.position.distanceTo(center);
                const angle = Date.now() * 0.001; // Smooth rotation
                
                camera.position.x = center.x + Math.cos(angle) * radius;
                camera.position.z = center.z + Math.sin(angle) * radius;
                camera.lookAt(center);
            }}
            
            renderer.render(scene, camera);
            
            // Update FPS
            frameCount++;
            const currentTime = Date.now();
            if (currentTime - lastTime >= 1000) {{
                const fps = Math.round(frameCount * 1000 / (currentTime - lastTime));
                document.getElementById('fps').textContent = `FPS: ${{fps}}`;
                frameCount = 0;
                lastTime = currentTime;
            }}
        }}
        
        function resetView() {{
            if (points) {{
                const box = points.geometry.boundingBox;
                const center = box.getCenter(new THREE.Vector3());
                const size = box.getSize(new THREE.Vector3());
                const maxDim = Math.max(size.x, size.y, size.z);
                
                camera.position.set(
                    center.x + maxDim * 0.2,
                    center.y + maxDim * 0.1,
                    center.z + maxDim * 0.2
                );
                camera.lookAt(center);
                
                console.log("Reset to center:", center);
            }}
        }}
        
        function changePointSize(delta) {{
            pointSize = Math.max(0.001, pointSize + delta * 0.005);
            if (points) {{
                points.material.size = pointSize;
            }}
        }}
        
        // Start when page loads
        window.addEventListener('load', init);
    </script>
</body>
</html>
"""
    
    return html_content

class PointCloudServer:
    """Simple HTTP server for standalone HTML files"""
    def __init__(self, port=8080):
        self.port = port
        self.server = None
        self.thread = None
        
    def find_free_port(self):
        """Find a free port"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]
    
    def start(self, directory):
        """Start the server in a background thread"""
        if self.server:
            self.stop()
            
        self.port = self.find_free_port()
        
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=directory, **kwargs)
        
        def run_server():
            self.server = HTTPServer(('localhost', self.port), Handler)
            print(f"Starting server on port {self.port}")
            self.server.serve_forever()
        
        self.thread = threading.Thread(target=run_server, daemon=True)
        self.thread.start()
        time.sleep(1)  # Give server time to start
        
        return f"http://localhost:{self.port}"
    
    def stop(self):
        """Stop the server"""
        if self.server:
            self.server.shutdown()
            self.server = None

# Global server instances and sharing mode
main_server = PointCloudServer()
USE_EMBEDDED_VIEWERS = False  # Will be set to True when using --share

def create_embedded_viewer(file_path, sample_size, dataset_name="Point Cloud"):
    """Create embedded Three.js viewer using data URL (for public sharing)"""
    if not file_path:
        return None, "Please select a PLY file first"

    try:
        # Use the actual sample size requested - let the caller decide the limit
        max_embedded_points = sample_size
        vertices, colors, status = read_ply_for_js(file_path, max_points=max_embedded_points)
        
        if vertices is None:
            return None, f"❌ {status}"
        
        # Create self-contained HTML with embedded Three.js viewer
        title = f"{dataset_name} Point Cloud ({len(vertices)//3:,} points)"
        unique_id = f"viewer_{abs(hash(file_path + str(sample_size))) % 10000}"
        
        # Convert arrays to JavaScript format
        js_vertices = "[" + ",".join(map(str, vertices)) + "]"
        js_colors = "[" + ",".join(map(str, colors)) + "]"
        
        # Create completely self-contained HTML
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ 
            margin: 0; 
            background: #f0f0f0; 
            font-family: Arial, sans-serif;
            overflow: hidden;
        }}
        #container {{ 
            width: 100vw; 
            height: 100vh; 
            position: relative;
        }}
        #info {{
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 10px;
            border-radius: 5px;
            font-size: 14px;
            z-index: 1000;
        }}
        #controls {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 10px;
            border-radius: 5px;
            z-index: 1000;
        }}
        button {{
            background: #4CAF50;
            color: white;
            border: none;
            padding: 5px 10px;
            margin: 2px;
            border-radius: 3px;
            cursor: pointer;
        }}
        button:hover {{ background: #45a049; }}
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>
    <div id="container"></div>
    <div id="info">
        <strong>{title}</strong><br>
        Points: {len(vertices)//3:,}<br>
        <span id="fps">FPS: --</span>
    </div>
    <div id="controls">
        <button onclick="resetView()">Reset View</button><br>
        <button onclick="changePointSize(1)">Size +</button>
        <button onclick="changePointSize(-1)">Size -</button>
    </div>

    <script>
        // Global variables
        let scene, camera, renderer, points;
        let autoRotate = true;
        let pointSize = 0.05;
        let frameCount = 0;
        let lastTime = Date.now();
        
        // Initialize Three.js scene
        function init() {{
            console.log("Initializing Three.js scene...");
            
            // Scene
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0xf0f0f0);
            
            // Camera
            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            
            // Renderer
            renderer = new THREE.WebGLRenderer({{ antialias: true }});
            renderer.setSize(window.innerWidth, window.innerHeight);
            document.getElementById('container').appendChild(renderer.domElement);
            
            // Point cloud data
            const vertices = new Float32Array({js_vertices});
            const colors = new Float32Array({js_colors});
            
            console.log("Vertices loaded:", vertices.length / 3);
            console.log("Colors loaded:", colors.length / 3);
            
            // Create geometry
            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
            geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
            
            // Create material
            const material = new THREE.PointsMaterial({{ 
                size: pointSize,
                vertexColors: true,
                sizeAttenuation: true
            }});
            
            // Create points
            points = new THREE.Points(geometry, material);
            scene.add(points);
            
            // Calculate bounds and position camera
            geometry.computeBoundingBox();
            const box = geometry.boundingBox;
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);
            
            camera.position.set(
                center.x + maxDim * 0.2,
                center.y + maxDim * 0.1,
                center.z + maxDim * 0.2
            );
            camera.lookAt(center);
            
            // Add basic controls
            setupControls();
            
            // Start render loop
            animate();
        }}
        
        function setupControls() {{
            let isDragging = false;
            let previousMousePosition = {{ x: 0, y: 0 }};
            
            // Get point cloud center for proper rotation
            const box = points.geometry.boundingBox;
            const center = box.getCenter(new THREE.Vector3());
            
            renderer.domElement.addEventListener('mousedown', function(e) {{
                isDragging = true;
                autoRotate = false;
                previousMousePosition.x = e.clientX;
                previousMousePosition.y = e.clientY;
            }});
            
            renderer.domElement.addEventListener('mousemove', function(e) {{
                if (isDragging) {{
                    const deltaMove = {{
                        x: e.clientX - previousMousePosition.x,
                        y: e.clientY - previousMousePosition.y
                    }};
                    
                    // Rotate around point cloud center
                    const spherical = new THREE.Spherical();
                    const offset = new THREE.Vector3();
                    offset.copy(camera.position).sub(center);
                    spherical.setFromVector3(offset);
                    
                    spherical.theta -= deltaMove.x * 0.01;
                    spherical.phi += deltaMove.y * 0.01;
                    spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi));
                    
                    offset.setFromSpherical(spherical);
                    camera.position.copy(center).add(offset);
                    camera.lookAt(center);
                    
                    previousMousePosition.x = e.clientX;
                    previousMousePosition.y = e.clientY;
                }}
            }});
            
            renderer.domElement.addEventListener('mouseup', function() {{
                isDragging = false;
            }});
            
            // Zoom with wheel
            renderer.domElement.addEventListener('wheel', function(e) {{
                autoRotate = false;
                const zoomFactor = e.deltaY > 0 ? 1.1 : 0.9;
                const direction = new THREE.Vector3();
                direction.subVectors(camera.position, center);
                direction.multiplyScalar(zoomFactor);
                camera.position.copy(center).add(direction);
                e.preventDefault();
            }});
            
            // Window resize
            window.addEventListener('resize', function() {{
                camera.aspect = window.innerWidth / window.innerHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(window.innerWidth, window.innerHeight);
            }});
        }}
        
        function animate() {{
            requestAnimationFrame(animate);
            
            if (autoRotate && points) {{
                // Rotate around point cloud center
                const box = points.geometry.boundingBox;
                const center = box.getCenter(new THREE.Vector3());
                
                const radius = camera.position.distanceTo(center);
                const angle = Date.now() * 0.0005;
                
                camera.position.x = center.x + Math.cos(angle) * radius;
                camera.position.z = center.z + Math.sin(angle) * radius;
                camera.lookAt(center);
            }}
            
            renderer.render(scene, camera);
            
            // Update FPS
            frameCount++;
            const currentTime = Date.now();
            if (currentTime - lastTime >= 1000) {{
                const fps = Math.round(frameCount * 1000 / (currentTime - lastTime));
                document.getElementById('fps').textContent = `FPS: ${{fps}}`;
                frameCount = 0;
                lastTime = currentTime;
            }}
        }}
        
        function resetView() {{
            if (points) {{
                const box = points.geometry.boundingBox;
                const center = box.getCenter(new THREE.Vector3());
                const size = box.getSize(new THREE.Vector3());
                const maxDim = Math.max(size.x, size.y, size.z);
                
                camera.position.set(
                    center.x + maxDim * 0.2,
                    center.y + maxDim * 0.1,
                    center.z + maxDim * 0.2
                );
                camera.lookAt(center);
                autoRotate = true;
            }}
        }}
        
        function changePointSize(delta) {{
            pointSize = Math.max(0.001, pointSize + delta * 0.02);
            if (points) {{
                points.material.size = pointSize;
            }}
        }}
        
        // Start when page loads
        window.addEventListener('load', init);
    </script>
</body>
</html>
        """
        
        # Convert to data URL
        import base64
        html_b64 = base64.b64encode(html_content.encode('utf-8')).decode('ascii')
        data_url = f"data:text/html;base64,{html_b64}"
        
        # Create iframe with data URL
        iframe_html = f"""
        <iframe src="{data_url}" 
                width="100%" 
                height="500px" 
                frameborder="0"
                style="border-radius: 5px;">
        </iframe>
        """
        
        return iframe_html, f"✅ {status} | Data URL viewer ({len(vertices)//3:,} points)"
        
    except Exception as e:
        return None, f"❌ Error: {str(e)}"
def create_iframe_viewer(file_path, sample_size, server_instance=None, dataset_name="Point Cloud"):
    """Create iframe viewer with standalone Three.js"""
    if not file_path:
        return None, "Please select a PLY file first"
    
    if server_instance is None:
        server_instance = main_server

    try:
        # Add loading status
        loading_status = f"🔄 Loading {sample_size:,} points from point cloud..."
        
        # Read point cloud data
        vertices, colors, status = read_ply_for_js(file_path, max_points=sample_size)
        
        if vertices is None:
            return None, f"❌ {status}"
        
        # Create temp directory for HTML file
        temp_dir = tempfile.mkdtemp()
        html_file = os.path.join(temp_dir, "pointcloud_viewer.html")
        
        # Generate HTML with updated title
        title = f"{dataset_name} Point Cloud ({len(vertices)//3:,} points)"
        html_content = create_standalone_html(vertices, colors, title)
        
        with open(html_file, 'w') as f:
            f.write(html_content)
        
        # Start server
        server_url = server_instance.start(temp_dir)
        viewer_url = f"{server_url}/pointcloud_viewer.html"
        
        # Create iframe HTML
        iframe_html = f"""
        <iframe src="{viewer_url}" 
                width="100%" 
                height="600px" 
                frameborder="0"
                style="border-radius: 5px;">
        </iframe>
        """
        
        return iframe_html, f"✅ {status} | Server: {viewer_url}"
        
    except Exception as e:
        return None, f"❌ Error: {str(e)}"

def set_sample_size_preset(preset_value):
    """Set sample size to preset value"""
    return preset_value

def analyze_file_and_set_full(file_path):
    """Analyze file and return full point count for the slider"""
    if not file_path:
        return 25000, "Select a file to see point count"
    
    total_points = get_ply_point_count(file_path)
    if total_points == 0:
        return 25000, "❌ Could not read point count"
    
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    
    # Warning for very large files
    if total_points > 500000:
        warning = f"⚠️ Large file: {total_points:,} points ({file_size_mb:.1f}MB) - may be slow!"
    else:
        warning = f"✅ {total_points:,} points ({file_size_mb:.1f}MB)"
    
    return total_points, warning

def load_main_viewer(file_path, point_count, dataset_name="Point Cloud"):
    """Load the main viewer with specified point count"""
    global USE_EMBEDDED_VIEWERS
    if not file_path:
        return None, "Please select a PLY file first"
    
    if point_count <= 0:
        return None, "Invalid point count"
    
    if USE_EMBEDDED_VIEWERS:
        return create_embedded_viewer(file_path, point_count, dataset_name)
    else:
        return create_iframe_viewer(file_path, point_count, server_instance=main_server, dataset_name=dataset_name)

def get_default_point_count(file_path):
    """Get default point count (100K or max, whichever is less)"""
    if not file_path:
        return 100000
    
    total_points = get_ply_point_count(file_path)
    if total_points == 0:
        return 100000
    
    return min(total_points, 100000)

def create_dataset_directory(dataset_name):
    """Create directory for collected answers if it doesn't exist"""
    import os
    base_dir = "./human_baseline/collected_answers/pcl_lists"
    dataset_dir = os.path.join(base_dir, dataset_name)
    os.makedirs(dataset_dir, exist_ok=True)
    return dataset_dir

def get_progress_info(dataset_name):
    """Get progress information for a dataset"""
    import os
    
    # Create directory if it doesn't exist
    dataset_dir = create_dataset_directory(dataset_name)
    
    # Count collected files
    try:
        collected_files = len([f for f in os.listdir(dataset_dir) if f.endswith('.json') or f.endswith('.txt')])
    except:
        collected_files = 0
    
    # Count total files from pcl_lists
    pcl_file = f"./pcl_lists/{dataset_name}.txt"
    total_files = 0
    
    try:
        if os.path.exists(pcl_file):
            with open(pcl_file, 'r') as f:
                total_files = len([line.strip() for line in f if line.strip()])
    except:
        total_files = 0
    
    if total_files > 0:
        percentage = (collected_files / total_files) * 100
        return f"📊 {collected_files}/{total_files} files collected ({percentage:.1f}%)"
    else:
        return f"📊 {collected_files}/? files collected (dataset file not found)"

def update_progress_display(dataset_name):
    """Update progress display when dataset selection changes"""
    return get_progress_info(dataset_name)

def on_dataset_change(dataset_name, threedfront_path, crops3d_path, user=None):
    """Handle dataset selection change"""
    # Create directory and update progress
    create_dataset_directory(dataset_name)
    
    # Cleanup stale locks before loading
    removed_count = cleanup_stale_locks(dataset_name)
    if removed_count > 0:
        print(f"🧹 Cleaned up {removed_count} stale lock(s)")
    
    # Load next point cloud for this dataset
    next_cloud_path, cloud_info = get_next_point_cloud(dataset_name, threedfront_path, crops3d_path)
    
    if next_cloud_path:
        # Create lock for this point cloud if user is selected
        identifier_scene = extract_identifier_scene(next_cloud_path, dataset_name)
        if identifier_scene and user:
            create_lock(dataset_name, identifier_scene, user)
        
        # Load the point cloud with default settings
        viewer_html, status = load_main_viewer(next_cloud_path, 100000, dataset_name)
        if viewer_html is None:
            viewer_html = f"<p style='text-align: center; padding: 60px; background: #fce8e6;'>{status}</p>"
        
        # Load questions for this point cloud
        questions = load_questions(dataset_name, next_cloud_path)
        
        # Get instance name for display
        instance_display = identifier_scene if identifier_scene else "Unknown instance"
        
        return update_progress_display(dataset_name), viewer_html, status, next_cloud_path, dataset_name, instance_display, *questions
    else:
        placeholder = "<p style='text-align: center; padding: 60px; background: #f5f5f5;'>All point clouds completed or none available</p>"
        empty_questions = ["No questions available"] * 12
        return update_progress_display(dataset_name), placeholder, "No more point clouds available", None, dataset_name, "No instance available", *empty_questions

def get_next_point_cloud(dataset_name, threedfront_path, crops3d_path):
    """Get the next point cloud that needs annotation
    
    Skips point clouds that are:
    1. Already completed (have .json file)
    2. Currently locked by another user (have .lock file less than 2 hours old)
    
    If a lock is stale (>2 hours old), it will be claimed and replaced.
    """
    import os
    
    # Read the pcl list
    pcl_file = f"./pcl_lists/{dataset_name}.txt"
    if not os.path.exists(pcl_file):
        return None, f"PCL list file not found: {pcl_file}"
    
    # Get completed files
    dataset_dir = create_dataset_directory(dataset_name)
    completed_files = set()
    try:
        for f in os.listdir(dataset_dir):
            if f.endswith('.json'):
                completed_files.add(f[:-5])  # Remove .json extension to get identifier@scene
    except:
        pass
    
    # Find next incomplete point cloud
    try:
        with open(pcl_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                # Parse identifier@scene format
                if '@' not in line:
                    continue
                    
                identifier, scene = line.split('@', 1)
                identifier_scene = line
                
                # Skip if already completed
                if identifier_scene in completed_files:
                    continue
                
                # Check if locked
                is_locked, is_stale, lock_info = check_lock(dataset_name, identifier_scene)
                
                if is_locked and not is_stale:
                    # Active lock - skip this one
                    continue
                
                # If lock is stale, we'll claim it below after we verify the file exists
                
                # Build path based on dataset
                if dataset_name == "3D-FRONT_test":
                    ply_path = os.path.join(threedfront_path, identifier, scene, f"{scene}.ply")
                elif dataset_name == "Crops3D_test":
                    ply_path = os.path.join(crops3d_path, identifier, f"{scene}.ply")
                else:
                    continue
                
                # Check if file exists
                if os.path.exists(ply_path):
                    # If there was a stale lock, log it
                    if is_locked and is_stale:
                        print(f"⚠️ Claiming stale lock for {identifier_scene} (was locked by {lock_info.get('user', 'unknown')} at {lock_info.get('started_at', 'unknown')})")
                    
                    return ply_path, f"Loading {identifier}@{scene}"
    
    except Exception as e:
        return None, f"Error reading PCL list: {str(e)}"
    
    return None, "All point clouds completed or no valid files found"

def extract_identifier_scene(file_path, dataset_name):
    """Extract identifier@scene from file path"""
    current_dir = os.path.dirname(file_path)
    basename = os.path.basename(file_path)
    
    if dataset_name == "3D-FRONT_test":
        # Path: /path/3D-FRONT/identifier/scene/scene.ply
        scene_dir = os.path.basename(current_dir)
        identifier = os.path.basename(os.path.dirname(current_dir))
        return f"{identifier}@{scene_dir}"
    elif dataset_name == "Crops3D_test":
        # Path: /path/Crops3D/identifier/scene.ply
        identifier = os.path.basename(current_dir)
        scene = basename[:-4] if basename.endswith('.ply') else basename
        return f"{identifier}@{scene}"
    else:
        return None

# Lock file management functions
def create_lock(dataset_name, identifier_scene, user):
    """Create a lock file for a point cloud being annotated"""
    import os
    import json
    from datetime import datetime
    import socket
    
    dataset_dir = create_dataset_directory(dataset_name)
    lock_file = os.path.join(dataset_dir, f"{identifier_scene}.lock")
    
    lock_data = {
        "user": user,
        "started_at": datetime.now().isoformat(),
        "hostname": socket.gethostname(),
        "pid": os.getpid()
    }
    
    try:
        with open(lock_file, 'w') as f:
            json.dump(lock_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Warning: Could not create lock file: {e}")
        return False

def release_lock(dataset_name, identifier_scene):
    """Release a lock file after successful annotation"""
    import os
    
    dataset_dir = create_dataset_directory(dataset_name)
    lock_file = os.path.join(dataset_dir, f"{identifier_scene}.lock")
    
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
        return True
    except Exception as e:
        print(f"Warning: Could not release lock file: {e}")
        return False

def check_lock(dataset_name, identifier_scene, max_age_hours=2):
    """Check if a point cloud is locked and if the lock is stale
    
    Returns:
        (is_locked, is_stale, lock_info)
        - is_locked: True if lock file exists
        - is_stale: True if lock is older than max_age_hours
        - lock_info: Dictionary with lock information or None
    """
    import os
    import json
    from datetime import datetime, timedelta
    
    dataset_dir = create_dataset_directory(dataset_name)
    lock_file = os.path.join(dataset_dir, f"{identifier_scene}.lock")
    
    if not os.path.exists(lock_file):
        return False, False, None
    
    try:
        with open(lock_file, 'r') as f:
            lock_data = json.load(f)
        
        # Parse the timestamp
        started_at = datetime.fromisoformat(lock_data['started_at'])
        age = datetime.now() - started_at
        
        is_stale = age > timedelta(hours=max_age_hours)
        
        return True, is_stale, lock_data
    except Exception as e:
        print(f"Warning: Error reading lock file: {e}")
        # If we can't read it, treat it as stale
        return True, True, None

def cleanup_stale_locks(dataset_name, max_age_hours=2):
    """Remove all stale lock files from a dataset
    
    Returns:
        Number of stale locks removed
    """
    import os
    
    dataset_dir = create_dataset_directory(dataset_name)
    removed_count = 0
    
    try:
        for filename in os.listdir(dataset_dir):
            if filename.endswith('.lock'):
                identifier_scene = filename[:-5]  # Remove .lock extension
                is_locked, is_stale, lock_info = check_lock(dataset_name, identifier_scene, max_age_hours)
                
                if is_stale:
                    lock_file = os.path.join(dataset_dir, filename)
                    try:
                        os.remove(lock_file)
                        removed_count += 1
                        print(f"Removed stale lock: {filename}")
                    except Exception as e:
                        print(f"Warning: Could not remove stale lock {filename}: {e}")
    except Exception as e:
        print(f"Warning: Error during lock cleanup: {e}")
    
    return removed_count

def save_annotation(dataset_name, file_path, user, questions, answers):
    """Save annotation to JSON file and release lock"""
    import os
    import json
    from datetime import datetime
    
    # Get identifier@scene
    identifier_scene = extract_identifier_scene(file_path, dataset_name)
    if not identifier_scene:
        return False, "Could not extract identifier@scene from file path"
    
    # Validate all answers are provided
    if any(not answer or not answer.strip() for answer in answers):
        return False, "❌ Please answer all 12 questions before submitting"
    
    # Question type mapping (matches folder names)
    question_types = [
        "aad_additional_instruction", "aad_additional_option", "aad_base",
        "iasd_additional_instruction", "iasd_additional_option", "iasd_base",
        "ivqd_additional_instruction", "ivqd_additional_option", "ivqd_base",
        "open_ended", "open_ended_additional_instruction", "standard"
    ]
    
    # Create annotation data structure
    annotation_data = {
        "identifier_scene": identifier_scene,
        "dataset": dataset_name,
        "annotated_by": user,
        "timestamp": datetime.now().isoformat(),
        "file_path": file_path,
        "responses": []
    }
    
    # Add each question-answer pair
    for i, (q_type, question, answer) in enumerate(zip(question_types, questions, answers)):
        annotation_data["responses"].append({
            "question_number": i + 1,
            "question_type": q_type,
            "prompt": question,
            "response": answer.strip()
        })
    
    # Save to file
    dataset_dir = create_dataset_directory(dataset_name)
    output_file = os.path.join(dataset_dir, f"{identifier_scene}.json")
    
    try:
        with open(output_file, 'w') as f:
            json.dump(annotation_data, f, indent=2)
        
        # Release the lock after successful save
        release_lock(dataset_name, identifier_scene)
        
        return True, f"✅ Annotation saved successfully to {identifier_scene}.json"
    except Exception as e:
        return False, f"❌ Error saving annotation: {str(e)}"


# Create interface
with gr.Blocks() as demo:
    
    # Initialize progress on startup
    def initialize_progress():
        return get_progress_info("3D-FRONT_test")
    
    with gr.Row():
        # Left column: Point cloud viewer and options
        with gr.Column(scale=1):
            viewer_output = gr.HTML(
                value="<p style='text-align: center; padding: 60px; background: #f5f5f5;'>Load a point cloud to start viewing</p>"
            )
            
            # Dataset selection
            dataset_selection = gr.Radio(
                choices=["3D-FRONT_test", "Crops3D_test"],
                label="📊 Dataset",
                value="3D-FRONT_test",
                info="Select dataset for annotation"
            )
            
            # Point count slider
            point_count_slider = gr.Slider(
                minimum=1000,
                maximum=500000,
                value=100000,
                step=1000,
                label="📊 Number of Points to Display",
                info="Drag to change the number of points rendered (updates automatically)"
            )
            
            # Single viewer status
            status_output = gr.Textbox(
                label="📊 Status",
                lines=1,
                interactive=False
            )
            
            # Instance name display (non-expandable)
            instance_name_display = gr.Textbox(
                label="📋 Current Instance",
                value="No instance selected",
                interactive=False,
                lines=1
            )
            
            progress_display = gr.Textbox(
                label="📈 Progress",
                value=get_progress_info("3D-FRONT_test"),
                interactive=False
            )
            
        # Right column: Questions in 3-column grid
        with gr.Column(scale=2):
            question_textboxes = []
            answer_textboxes = []
            
            # Create 4 rows of 3 questions each
            for row in range(4):
                with gr.Row():
                    for col in range(3):
                        question_num = row * 3 + col + 1
                        with gr.Column():
                            gr.Markdown(f"**Question {question_num}**")
                            question_textboxes.append(gr.Textbox(
                                label="",
                                value="No question available",
                                interactive=False,
                                lines=3
                            ))
                            answer_textboxes.append(gr.Textbox(
                                label="",
                                placeholder="Enter your answer here...",
                                interactive=True,
                                lines=2
                            ))
            
            # Submit button
            submit_btn = gr.Button("📝 Submit Answers", variant="primary", size="lg")
            
            submission_status = gr.Textbox(
                label="📋 Submission Status",
                value="No user selected",
                interactive=False
            )
    
    # Hidden user selection state and modal dialog
    user_selection = gr.State(None)
    
    # Create modal dialog for user selection
    with gr.Column(visible=True, elem_id="user-modal") as user_modal:
        with gr.Column(elem_classes="modal-content"):
            gr.HTML("<h2 style='color: black;'>👤 Welcome! Please select your user identity</h2>")
            modal_user_radio = gr.Radio(
                choices=["User 1", "User 2", "User 3", "User 4", "User 5", "User 6", "User 7", 
                        "User 8", "User 9", "User 10", "User 11", "User 12", "User 13", "User 14", "User 15"],
                label="Select Your User ID",
                value=None,
                interactive=True
            )
            modal_submit_btn = gr.Button("🚀 Continue", variant="primary", size="lg")
    
    # CSS for modal
    demo.load(
        None,
        None,
        None,
        js="""
        () => {
            const style = document.createElement('style');
            style.textContent = `
                #user-modal {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100vw;
                    height: 100vh;
                    background: rgba(0, 0, 0, 0.5);
                    z-index: 10000;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                #user-modal.hidden {
                    display: none !important;
                }
                .modal-content {
                    background: white;
                    padding: 50px;
                    border-radius: 16px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.4);
                    min-width: 500px;
                    max-width: 600px;
                }
            `;
            document.head.appendChild(style);
        }
        """
    )
    
    # Store current file path for slider updates
    current_file = gr.State(None)
    current_dataset = gr.State(None)

    # User selection handler
    def select_user_and_load(selected_user):
        """Handle user selection, hide modal, and load first point cloud"""
        print(f"DEBUG: select_user_and_load called with user: {selected_user}")
        
        if selected_user is None:
            # Keep modal visible if no user selected
            print("DEBUG: No user selected, keeping modal visible")
            placeholder = "<p style='text-align: center; padding: 60px; background: #f5f5f5;'>Please select a user</p>"
            empty_questions = ["No questions available"] * 12
            return [None, gr.update(visible=True), "No user selected", placeholder, "No file selected", None, "3D-FRONT_test", "No instance selected"] + empty_questions
        
        print(f"DEBUG: User selected: {selected_user}, loading dataset")
        dataset = "3D-FRONT_test"
        
        # Load the first point cloud for this user and dataset
        result = on_dataset_change(dataset, args.threedfront_path, args.crops3d_path, selected_user)
        # result contains: progress_display, viewer_output, status_output, current_file, current_dataset, file_path_display, *questions (12)
        print(f"DEBUG: on_dataset_change returned {len(result)} items")
        
        # Return: user_selection, user_modal (hidden), then all the results from on_dataset_change
        output = [selected_user, gr.update(visible=False)] + list(result)
        print(f"DEBUG: Returning {len(output)} outputs (should be 20: user_selection, user_modal, 6 fields, 12 questions)")
        return output
    
    # Connect modal submit button with JavaScript to hide modal
    modal_submit_btn.click(
        fn=select_user_and_load,
        inputs=[modal_user_radio],
        outputs=[user_selection, user_modal, progress_display, viewer_output, status_output, current_file, current_dataset, instance_name_display] + question_textboxes,
        js="""
        (user) => {
            console.log('Continue button clicked, user:', user);
            if (user) {
                console.log('Hiding modal');
                const modal = document.getElementById('user-modal');
                if (modal) {
                    modal.classList.add('hidden');
                    modal.style.display = 'none';
                }
            }
            return user;
        }
        """
    )

    # Event handlers
    def update_viewer_from_slider(file_path, point_count, dataset_name):
        """Update viewer when slider changes"""
        if not file_path:
            no_questions = ["No questions available"] * 12
            return "<p style='text-align: center; padding: 60px; background: #f5f5f5;'>Load a point cloud to start viewing</p>", "No file selected", "No instance selected", *no_questions
        
        viewer_html, status = load_main_viewer(file_path, int(point_count), dataset_name)
        if viewer_html is None:
            viewer_html = f"<p style='text-align: center; padding: 60px; background: #fce8e6;'>{status}</p>"
        
        # Load questions for the current point cloud
        questions = load_questions(dataset_name, file_path)
        
        # Get instance name for display
        instance_name = extract_identifier_scene(file_path, dataset_name)
        instance_display = instance_name if instance_name else "Unknown instance"
        
        return viewer_html, status, instance_display, *questions
    
    def handle_submit(selected_user, dataset_name, file_path, point_count, *answers):
        """Handle submit button click with user validation and saving"""
        # Validate user selection
        if selected_user is None:
            return ["❌ No user selected - please select a user before submitting"] + [""] * 12 + [None, dataset_name, "No instance available", "<p style='text-align: center; padding: 60px; background: #f5f5f5;'>No file loaded</p>", "No file selected", get_progress_info(dataset_name)] + ["No questions available"] * 12
        
        # Validate file path
        if not file_path or file_path == "No file available":
            return ["❌ No point cloud loaded"] + [""] * 12 + [None, dataset_name, "No instance available", "<p style='text-align: center; padding: 60px; background: #f5f5f5;'>No file loaded</p>", "No file selected", get_progress_info(dataset_name)] + ["No questions available"] * 12
        
        # Get the questions for this point cloud
        questions = load_questions(dataset_name, file_path)
        
        # Validate we have all 12 answers
        if len(answers) != 12:
            current_instance = extract_identifier_scene(file_path, dataset_name) or "Unknown instance"
            return [f"❌ Expected 12 answers, got {len(answers)}"] + list(answers) + [file_path, dataset_name, current_instance, "<p style='text-align: center; padding: 60px; background: #f5f5f5;'>Error</p>", file_path, get_progress_info(dataset_name)] + questions
        
        # Save the annotation
        success, message = save_annotation(dataset_name, file_path, selected_user, questions, answers)
        
        if not success:
            # Return error message but keep current state
            current_instance = extract_identifier_scene(file_path, dataset_name) or "Unknown instance"
            return [message] + list(answers) + [file_path, dataset_name, current_instance, "<p style='text-align: center; padding: 60px; background: #f5f5f5;'>Error</p>", file_path, get_progress_info(dataset_name)] + questions
        
        # Success! Load next point cloud and clear answers
        next_cloud_path, cloud_info = get_next_point_cloud(dataset_name, args.threedfront_path, args.crops3d_path)
        
        if next_cloud_path:
            # Create lock for the new point cloud
            next_identifier_scene = extract_identifier_scene(next_cloud_path, dataset_name)
            if next_identifier_scene:
                create_lock(dataset_name, next_identifier_scene, selected_user)
            
            # Load the next point cloud with the current slider value
            viewer_html, status = load_main_viewer(next_cloud_path, int(point_count), dataset_name)
            if viewer_html is None:
                viewer_html = f"<p style='text-align: center; padding: 60px; background: #fce8e6;'>{status}</p>"
            
            # Load questions for next point cloud
            next_questions = load_questions(dataset_name, next_cloud_path)
            
            # Return: submission_status, 12 empty answer fields, current_file, current_dataset, instance_name_display, viewer_output, status_output, progress_display, 12 questions
            return [message + " 🔄 Loading next point cloud..."] + [""] * 12 + [next_cloud_path, dataset_name, next_identifier_scene, viewer_html, status, get_progress_info(dataset_name)] + next_questions
        else:
            # All done!
            placeholder = "<p style='text-align: center; padding: 60px; background: #d4edda; color: #155724;'><strong>🎉 All point clouds completed!</strong></p>"
            empty_questions = ["No more questions"] * 12
            return [message + " 🎉 All point clouds in this dataset completed!"] + [""] * 12 + [None, dataset_name, "All completed", placeholder, "All completed", get_progress_info(dataset_name)] + empty_questions

    # Slider change event - updates viewer in real time
    point_count_slider.change(
        fn=update_viewer_from_slider,
        inputs=[current_file, point_count_slider, current_dataset],
        outputs=[viewer_output, status_output, instance_name_display] + question_textboxes
    )

    # Submit button event
    submit_btn.click(
        fn=handle_submit,
        inputs=[user_selection, current_dataset, current_file, point_count_slider] + answer_textboxes,
        outputs=[submission_status] + answer_textboxes + [current_file, current_dataset, instance_name_display, viewer_output, status_output, progress_display] + question_textboxes
    )

    # Dataset selection change event (must be inside Blocks context)
    dataset_selection.change(
        fn=on_dataset_change_wrapper,
        inputs=[dataset_selection, user_selection],
        outputs=[progress_display, viewer_output, status_output, current_file, current_dataset, instance_name_display] + question_textboxes
    )

if __name__ == "__main__":
    print("🚀 Three.js Point Cloud Viewer (Iframe Approach)")
    print("Bypasses Gradio JavaScript restrictions using standalone server")
    print("="*65)
    

    # Set global sharing mode
    USE_EMBEDDED_VIEWERS = args.share
    
    print(f"🌐 Server will run on {args.host}:{args.port}")
    if args.share:
        print("🔗 Public sharing enabled - you'll get a gradio.live URL")
        print("📱 Using embedded viewers (compatible with public sharing)")
    else:
        print("🏠 Local/network access only")
        print("🖥️ Using iframe viewers (better performance for local use)")
    
    try:
        demo.launch(
            share=args.share,
            server_name=args.host,
            server_port=args.port,
            show_error=True,
            inbrowser=not args.share  # Don't auto-open browser if sharing publicly
        )
    finally:
        # Cleanup servers
        main_server.stop()