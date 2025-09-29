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
        <button onclick="toggleAutoRotate()">Auto Rotate</button><br>
        <button onclick="changePointSize(1)">Size +</button>
        <button onclick="changePointSize(-1)">Size -</button>
    </div>

    <script>
        // Global variables
        let scene, camera, renderer, points, controls;
        let autoRotate = false;
        let pointSize = 0.02;
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
                center.x + maxDim,
                center.y + maxDim * 0.5,
                center.z + maxDim
            );
            camera.lookAt(center);
            
            console.log("Bounding box:", box);
            console.log("Camera position:", camera.position);
            
            // Add basic controls
            setupControls();
            
            // Start render loop
            animate();
        }}
        
        function setupControls() {{
            let isDragging = false;
            let previousMousePosition = {{ x: 0, y: 0 }};
            
            renderer.domElement.addEventListener('mousedown', function(e) {{
                isDragging = true;
                previousMousePosition.x = e.clientX;
                previousMousePosition.y = e.clientY;
            }});
            
            renderer.domElement.addEventListener('mousemove', function(e) {{
                if (isDragging) {{
                    const deltaMove = {{
                        x: e.clientX - previousMousePosition.x,
                        y: e.clientY - previousMousePosition.y
                    }};
                    
                    // Rotate around center
                    const spherical = new THREE.Spherical();
                    spherical.setFromVector3(camera.position);
                    spherical.theta -= deltaMove.x * 0.01;
                    spherical.phi += deltaMove.y * 0.01;
                    spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi));
                    
                    camera.position.setFromSpherical(spherical);
                    camera.lookAt(0, 0, 0);
                    
                    previousMousePosition.x = e.clientX;
                    previousMousePosition.y = e.clientY;
                }}
            }});
            
            renderer.domElement.addEventListener('mouseup', function() {{
                isDragging = false;
            }});
            
            // Zoom with wheel
            renderer.domElement.addEventListener('wheel', function(e) {{
                const zoomFactor = e.deltaY > 0 ? 1.1 : 0.9;
                camera.position.multiplyScalar(zoomFactor);
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
            
            if (autoRotate) {{
                points.rotation.y += 0.005;
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
                    center.x + maxDim,
                    center.y + maxDim * 0.5,
                    center.z + maxDim
                );
                camera.lookAt(center);
            }}
        }}
        
        function toggleAutoRotate() {{
            autoRotate = !autoRotate;
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

# Global server instance
server = PointCloudServer()

def create_iframe_viewer(file_path, sample_size):
    """Create iframe viewer with standalone Three.js"""
    if not file_path:
        return None, "Please select a PLY file first"
    
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
        server_url = server.start(temp_dir)
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

def update_file_info(file_path):
    """Update file info display when file is selected"""
    if not file_path:
        return "Select a file to see point count"
    
    total_points = get_ply_point_count(file_path)
    if total_points == 0:
        return "❌ Could not read point count"
    
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    return f"📁 {os.path.basename(file_path)}: {total_points:,} points ({file_size_mb:.1f}MB)"

def auto_reload_handler(file_path, sample_size, auto_reload_enabled):
    """Handle auto-reload when sample size changes"""
    if auto_reload_enabled and file_path:
        return create_iframe_viewer(file_path, sample_size)
    else:
        return None, f"📊 Sample size set to {sample_size:,} points. Click 'Load Point Cloud' to apply."

# Create interface
with gr.Blocks(title="Three.js Point Cloud Viewer (Iframe)") as demo:
    gr.Markdown("""
    # 🚀 Three.js Point Cloud Viewer (Iframe Approach)
    
    **Bypasses Gradio's JavaScript restrictions by using a standalone server + iframe**
    
    This approach:
    - ✅ **Full Three.js functionality** (no JavaScript restrictions)
    - ✅ **Real-time interaction** (mouse controls, zooming, rotating)
    - ✅ **High performance** (WebGL rendering)
    - ✅ **3D-FRONT format support** (double precision, NaN filtering)
    - ✅ **Professional controls** (reset view, auto-rotate, point size)
    
    Perfect for human annotation interfaces!
    """)
    
    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(
                label="📁 Select 3D-FRONT PLY File",
                file_types=[".ply"],
                type="filepath"
            )
            
            sample_size = gr.Slider(
                minimum=1000, maximum=200000, value=25000, step=1000,
                label="📊 Sample Size (points to load)",
                info="Higher values = better quality, slower loading"
            )
            
            gr.Markdown("**Quick Presets:**")
            with gr.Row():
                fast_btn = gr.Button("⚡ Fast (10K)", size="sm", variant="secondary")
                medium_btn = gr.Button("🎯 Medium (25K)", size="sm", variant="secondary")
                quality_btn = gr.Button("💎 Quality (50K)", size="sm", variant="secondary")
                ultra_btn = gr.Button("🔥 Ultra (100K)", size="sm", variant="secondary")
            
            with gr.Row():
                full_btn = gr.Button("🌟 Full (All Points)", size="sm", variant="primary")
                point_count_display = gr.Textbox(
                    label="📊 File Info", 
                    value="Select a file to see point count",
                    interactive=False,
                    scale=2
                )
            
            load_btn = gr.Button("🚀 Load Point Cloud", variant="primary")
            
            with gr.Accordion("⚙️ Advanced Options", open=False):
                auto_reload = gr.Checkbox(
                    label="🔄 Auto-reload on sample size change",
                    value=False,
                    info="Automatically reload when slider changes"
                )
            
            gr.Markdown("""
            ### 🎮 Controls (in viewer):
            - **Drag**: Rotate view
            - **Scroll**: Zoom in/out
            - **Reset View**: Return to default position
            - **Auto Rotate**: Continuous rotation
            - **Size +/-**: Adjust point size
            
            ### ⚡ Performance Guide:
            - **Fast (10K)**: Quick preview, good for initial exploration
            - **Medium (25K)**: Balanced quality/speed, recommended default
            - **Quality (50K)**: High detail, slower loading
            - **Ultra (100K)**: Maximum detail, use for final review
            - **🌟 Full**: ALL points from file, maximum fidelity (may be slow!)
            
            💡 **Tip**: Enable auto-reload to see changes instantly!
            ⚠️ **Warning**: Full mode with 1M+ points may take time to load
            """)
            
        with gr.Column(scale=2):
            status_output = gr.Textbox(
                label="📊 Status",
                lines=2,
                interactive=False
            )
            
            gr.Markdown("### 🎯 Three.js Point Cloud Viewer")
            
            viewer_output = gr.HTML(
                value="<p style='text-align: center; padding: 100px; background: #f5f5f5;'>Load a point cloud to start viewing</p>"
            )
    
    gr.Markdown("""
    ### 💡 Why This Works:
    
    **The Problem**: Gradio's HTML component blocks JavaScript execution for security
    
    **The Solution**: 
    1. Create standalone HTML file with full Three.js code
    2. Start local HTTP server to serve the file
    3. Embed in Gradio using iframe (no JavaScript restrictions)
    4. Full Three.js functionality restored!
    
    This gives you the **high-quality 3D visualization** you need for human annotation.
    """)
    
    # Event handlers
    load_btn.click(
        fn=create_iframe_viewer,
        inputs=[file_input, sample_size],
        outputs=[viewer_output, status_output]
    )
    
    # Update file info when file is selected
    file_input.change(
        fn=update_file_info,
        inputs=[file_input],
        outputs=[point_count_display]
    )
    
    # Quick preset buttons
    fast_btn.click(
        fn=lambda: 10000,
        outputs=[sample_size]
    )
    
    medium_btn.click(
        fn=lambda: 25000,
        outputs=[sample_size]
    )
    
    quality_btn.click(
        fn=lambda: 50000,
        outputs=[sample_size]
    )
    
    ultra_btn.click(
        fn=lambda: 100000,
        outputs=[sample_size]
    )
    
    # Full preset - sets slider to total point count
    full_btn.click(
        fn=analyze_file_and_set_full,
        inputs=[file_input],
        outputs=[sample_size, point_count_display]
    )
    
    # Auto-reload when sample size changes (if enabled)
    sample_size.change(
        fn=auto_reload_handler,
        inputs=[file_input, sample_size, auto_reload],
        outputs=[viewer_output, status_output]
    )

if __name__ == "__main__":
    print("🚀 Three.js Point Cloud Viewer (Iframe Approach)")
    print("Bypasses Gradio JavaScript restrictions using standalone server")
    print("="*65)
    
    try:
        demo.launch(
            share=False,
            server_name="0.0.0.0",
            server_port=7871,
            show_error=True,
            inbrowser=True
        )
    finally:
        # Cleanup server
        server.stop()