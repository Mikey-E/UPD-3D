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

def read_3dfront_ply_for_js(file_path, max_points=50000):
    """Read 3D-FRONT PLY and convert to JavaScript format"""
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
            
            if format_type != 'binary_little_endian':
                return None, None, "Only binary PLY supported for 3D-FRONT"
            
            # Calculate bytes per vertex
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
        
        if len(vertices) == 0:
            return None, None, "No valid vertices found"
        
        return vertices, colors, f"Loaded {valid_count} valid points"
        
    except Exception as e:
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
        <strong>3D-FRONT Point Cloud Viewer</strong><br>
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
                center.x + maxDim * 0.6,
                center.y + maxDim * 0.3,
                center.z + maxDim * 0.6
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
                    center.x + maxDim * 0.6,
                    center.y + maxDim * 0.3,
                    center.z + maxDim * 0.6
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

def create_embedded_viewer(file_path, sample_size):
    """Create embedded Three.js viewer using data URL (for public sharing)"""
    if not file_path:
        return None, "Please select a PLY file first"

    try:
        # Use the actual sample size requested - let the caller decide the limit
        max_embedded_points = sample_size
        vertices, colors, status = read_3dfront_ply_for_js(file_path, max_points=max_embedded_points)
        
        if vertices is None:
            return None, f"❌ {status}"
        
        # Create self-contained HTML with embedded Three.js viewer
        title = f"3D-FRONT Point Cloud ({len(vertices)//3:,} points)"
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
                center.x + maxDim * 0.6,
                center.y + maxDim * 0.3,
                center.z + maxDim * 0.6
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
                    center.x + maxDim * 0.6,
                    center.y + maxDim * 0.3,
                    center.z + maxDim * 0.6
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
def create_iframe_viewer(file_path, sample_size, server_instance=None):
    """Create iframe viewer with standalone Three.js"""
    if not file_path:
        return None, "Please select a PLY file first"
    
    if server_instance is None:
        server_instance = main_server

    try:
        # Add loading status
        loading_status = f"🔄 Loading {sample_size:,} points from point cloud..."
        
        # Read point cloud data
        vertices, colors, status = read_3dfront_ply_for_js(file_path, max_points=sample_size)
        
        if vertices is None:
            return None, f"❌ {status}"
        
        # Create temp directory for HTML file
        temp_dir = tempfile.mkdtemp()
        html_file = os.path.join(temp_dir, "pointcloud_viewer.html")
        
        # Generate HTML with updated title
        title = f"3D-FRONT Point Cloud ({len(vertices)//3:,} points)"
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

def validate_and_load_path(path_input):
    """Validate path and return it if valid, otherwise return None"""
    if not path_input or not path_input.strip():
        return None, "Please enter a file path"
    
    path = path_input.strip()
    
    if not os.path.exists(path):
        return None, f"❌ File not found: {path}"
    
    if not path.lower().endswith('.ply'):
        return None, f"❌ File must be a PLY file: {path}"
    
    return path, f"✅ Valid PLY file: {os.path.basename(path)}"


def load_from_path_input(path_input):
    """Load viewer from path input"""
    validated_path, status = validate_and_load_path(path_input)
    
    if validated_path is None:
        placeholder = f"<p style='text-align: center; padding: 60px; background: #fce8e6;'>{status}</p>"
        default_slider = gr.Slider(
            minimum=1000,
            maximum=500000,
            value=100000,
            step=1000,
            label="📊 Number of Points to Display",
            info="Drag to change the number of points rendered (updates automatically)"
        )
        return (
            status,  # point_count_display
            default_slider,  # slider component
            placeholder, status  # main viewer
        )
    
    # Update file info
    file_info = update_file_info(validated_path)
    
    # Get total points and set slider range
    total_points = get_ply_point_count(validated_path)
    if total_points <= 0:
        max_points = 500000
        default_points = 100000
    else:
        max_points = total_points  # Slider max = actual file point count
        default_points = min(100000, total_points)  # Default 100K or max if file is smaller
    
    # Create new slider with proper maximum
    new_slider = gr.Slider(
        minimum=1000,
        maximum=max_points,
        value=default_points,
        step=1000,
        label="📊 Number of Points to Display",
        info="Drag to change the number of points rendered (updates automatically)"
    )
    
    # Load viewer with default point count
    main_viewer, main_status = load_main_viewer(validated_path, default_points)
    
    return (
        file_info,
        new_slider,  # new slider component with proper max
        main_viewer or f"<p style='text-align: center; padding: 60px; background: #fce8e6;'>{main_status}</p>", 
        main_status
    )


def update_file_info(file_path):
    """Update file info display when file is selected"""
    if not file_path:
        return "Select a file to see point count"
    
    total_points = get_ply_point_count(file_path)
    if total_points == 0:
        return "❌ Could not read point count"
    
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    return f"📁 {os.path.basename(file_path)}: {total_points:,} points ({file_size_mb:.1f}MB)"





def load_main_viewer(file_path, point_count):
    """Load the main viewer with specified point count"""
    global USE_EMBEDDED_VIEWERS
    if not file_path:
        return None, "Please select a PLY file first"
    
    if point_count <= 0:
        return None, "Invalid point count"
    
    if USE_EMBEDDED_VIEWERS:
        return create_embedded_viewer(file_path, point_count)
    else:
        return create_iframe_viewer(file_path, point_count, server_instance=main_server)

def get_default_point_count(file_path):
    """Get default point count (100K or max, whichever is less)"""
    if not file_path:
        return 100000
    
    total_points = get_ply_point_count(file_path)
    if total_points == 0:
        return 100000
    
    return min(total_points, 100000)

# Create interface
with gr.Blocks() as demo:
    
    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(
                label="📁 Select 3D-FRONT PLY File",
                file_types=[".ply"],
                type="filepath"
            )
            
            gr.Markdown("**OR**")
            
            path_input = gr.Textbox(
                label="📝 Enter PLY File Path",
                value="/project/3dllms/melgin/datasets/3d-grand_unzipped/3D-FRONT/ffed9e6c-5e6d-49aa-ba90-83927369ff47/LivingRoom-1184/LivingRoom-1184.ply",
                placeholder="Enter full path to PLY file...",
                lines=2
            )
            
            load_path_btn = gr.Button("🔄 Load from Path", variant="primary")
            
            point_count_display = gr.Textbox(
                label="📊 File Info",
                value="Select a file to see point count",
                interactive=False
            )
            
        with gr.Column(scale=2):
            # Point count slider
            point_count_slider = gr.Slider(
                minimum=1000,
                maximum=500000,
                value=100000,
                step=1000,
                label="📊 Number of Points to Display",
                info="Drag to change the number of points rendered (updates automatically)"
            )
            
            # Single viewer
            status_output = gr.Textbox(
                label="📊 Status",
                lines=1,
                interactive=False
            )
            viewer_output = gr.HTML(
                value="<p style='text-align: center; padding: 60px; background: #f5f5f5;'>Load a point cloud to start viewing</p>"
            )
    
    # Store current file path for slider updates
    current_file = gr.State(None)
    
    # Event handlers
    def update_file_and_slider(file_path):
        """Update file info and slider when file is selected"""
        if not file_path:
            return "Select a file to see point count", gr.Slider(minimum=1000, maximum=500000, value=100000, step=1000), file_path
        
        file_info = update_file_info(file_path)
        total_points = get_ply_point_count(file_path)
        
        if total_points <= 0:
            max_points = 500000
            default_points = 100000
        else:
            max_points = total_points  # Slider max = actual file point count
            default_points = min(100000, total_points)  # Default 100K or max if file is smaller
        
        # Create new slider with proper maximum
        new_slider = gr.Slider(
            minimum=1000,
            maximum=max_points,
            value=default_points,
            step=1000,
            label="📊 Number of Points to Display",
            info="Drag to change the number of points rendered (updates automatically)"
        )
        
        return file_info, new_slider, file_path
    
    def update_viewer_from_slider(file_path, point_count):
        """Update viewer when slider changes"""
        if not file_path:
            return "<p style='text-align: center; padding: 60px; background: #f5f5f5;'>Load a point cloud to start viewing</p>", "No file selected"
        
        viewer_html, status = load_main_viewer(file_path, int(point_count))
        if viewer_html is None:
            viewer_html = f"<p style='text-align: center; padding: 60px; background: #fce8e6;'>{status}</p>"
        
        return viewer_html, status
    
    # File input events
    file_input.change(
        fn=update_file_and_slider,
        inputs=[file_input],
        outputs=[point_count_display, point_count_slider, current_file]
    )
    
    # Load initial viewer when file changes
    file_input.change(
        fn=update_viewer_from_slider,
        inputs=[current_file, point_count_slider],
        outputs=[viewer_output, status_output]
    )
    
    # Slider change event - updates viewer in real time
    point_count_slider.change(
        fn=update_viewer_from_slider,
        inputs=[current_file, point_count_slider],
        outputs=[viewer_output, status_output]
    )
    
    # Path input button event
    load_path_btn.click(
        fn=load_from_path_input,
        inputs=[path_input],
        outputs=[
            point_count_display,
            point_count_slider,  # Replace entire slider component
            viewer_output, 
            status_output
        ]
    )
    
    # Update current file when path is loaded
    load_path_btn.click(
        fn=lambda path: validate_and_load_path(path)[0] if validate_and_load_path(path)[0] else None,
        inputs=[path_input],
        outputs=[current_file]
    )

if __name__ == "__main__":
    print("🚀 Three.js Point Cloud Viewer (Iframe Approach)")
    print("Bypasses Gradio JavaScript restrictions using standalone server")
    print("="*65)
    
    # Add configuration options
    import argparse
    parser = argparse.ArgumentParser(description='Point Cloud Viewer')
    parser.add_argument('--share', action='store_true', help='Enable public sharing via Gradio tunnel')
    parser.add_argument('--host', default='0.0.0.0', help='Host address (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=7871, help='Port number (default: 7871)')
    args = parser.parse_args()
    
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