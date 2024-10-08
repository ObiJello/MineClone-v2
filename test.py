import socket
import struct
import io
import time
import mss
from PIL import Image
import sys
from pyngrok import ngrok, conf
import requests
import signal
from flask import Flask, request, jsonify
import threading
import os
import shutil

# Variable to store the ngrok tunnel object
ngrok_tunnel = None
app = Flask(__name__)

# Shared variable to track connection status
client_connected = threading.Event()

# Function to send public IP to client
def send_public_ip_to_client(public_ip, client_ip, client_port):
    """Send the public IP and port to a client Python script running on a remote machine."""
    try:
        response = requests.post(f'http://{client_ip}:{client_port}/receive_ip', json={'public_ip': public_ip})
        if response.status_code == 200:
            print("Public IP sent to the client successfully.")
        else:
            print(f"Failed to send public IP: {response.status_code}")
    except Exception as e:
        print(f"Error sending public IP to client: {e}", file=sys.stderr)

# Function to stream screen
def screen_streamer(client_socket):
    """Stream the screen when a client connects."""
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # Capture the first monitor
        while client_connected.is_set():
            try:
                sct_img = sct.grab(monitor)
                image = Image.frombytes('RGB', (sct_img.width, sct_img.height), sct_img.rgb)
                image = image.resize((800, 600))
                img_byte_array = io.BytesIO()
                image.save(img_byte_array, format='JPEG', quality=40)
                img_bytes = img_byte_array.getvalue()
                client_socket.sendall(struct.pack("!L", len(img_bytes)) + img_bytes)  # Use network byte order (!)
                time.sleep(1 / 24)  # 24 FPS
            except Exception as e:
                print(f"Error in screen streaming: {e}", file=sys.stderr)
                break

# Function to shut down server
def shutdown_server(signal, frame):
    """Signal handler to shut down the server and terminate the Ngrok tunnel."""
    global ngrok_tunnel
    print("Shutting down the server...")
    if ngrok_tunnel:
        try:
            print("Terminating Ngrok tunnel...")
            ngrok.disconnect(ngrok_tunnel.public_url)
            ngrok.kill()  # Kill the Ngrok process
        except Exception as e:
            print(f"Error terminating Ngrok tunnel: {e}")
    os._exit(0)  # Forcefully terminate the Python process

# Flask route to handle shutdown request
@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Shut down the server."""
    print("Shutdown request received.")
    try:
        shutdown_server(signal.SIGINT, None)  # Call the existing shutdown logic
    except Exception as e:
        print(f"Error during shutdown: {e}")
    return jsonify({"status": "shutdown initiated"}), 200

# Function to run Flask app
def run_flask_app():
    """Run the Flask app to handle shutdown requests."""
    app.run(host='0.0.0.0', port=1328)  # Change port if necessary

# Main server function
def run_server():
    """Start the server and wait for client connections."""
    global ngrok_tunnel

    # Set up a signal handler to handle Ctrl+C and termination
    signal.signal(signal.SIGINT, shutdown_server)

    # Configure Ngrok authentication
    conf.get_default().auth_token = "2n6dGlsHf3g0Z5TIssTAmGpbwj5_6NcTVBnzq5LX7UpxZsJEL"  # Replace with your Ngrok auth token

    # List of possible paths to find ngrok
    ngrok_paths = [
        "/Library/Frameworks/Python.framework/Versions/3.12/bin/ngrok",
        "/usr/local/bin/ngrok",
        "/usr/bin/ngrok",
        "/opt/homebrew/bin/ngrok"  # Add more paths if necessary
    ]

    # Find the first valid ngrok path
    ngrok_path = None
    for path in ngrok_paths:
        if os.path.exists(path):
            ngrok_path = path
            break

    if not ngrok_path:
        print("Ngrok executable not found in any of the specified paths. Please check the paths and try again.")
        sys.exit(1)
    conf.get_default().ngrok_path = ngrok_path

    # Use the found ngrok executable to start the tunnel
    try:
        # Expose port 9999 using Ngrok
        ngrok_tunnel = ngrok.connect(9999, "tcp")
        public_url = ngrok_tunnel.public_url
        print(f"Ngrok tunnel created: {public_url}")
    except Exception as e:
        print(f"Failed to start Ngrok: {e}")
        sys.exit(1)

    # Send the public IP and port to the client machine
    client_ip = "192.168.1.180"  # Replace with the actual IP address of the client machine
    client_port = 5321  # The port where the client will listen for the IP
    send_public_ip_to_client(public_url, client_ip, client_port)

    # Start the Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True  # This allows the Flask thread to exit when the main thread does
    flask_thread.start()

    # Now start the socket server
    stream_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    stream_socket.bind(('0.0.0.0', 9999))  # Listen on port 9999
    stream_socket.listen(5)

    print("Server is dormant, waiting for client connection...")

    while True:
        client_socket, addr = stream_socket.accept()
        print(f"Client connected from {addr}. Starting screen stream...")
        client_connected.set()  # Indicate that a client is connected
        client_handler_thread = threading.Thread(target=handle_client, args=(client_socket,))
        client_handler_thread.start()

# Handle client connection
def handle_client(client_socket):
    """Handle client connection to listen for shutdown command."""
    try:
        screen_thread = threading.Thread(target=screen_streamer, args=(client_socket,))  # Start screen streaming in parallel
        screen_thread.start()
        while True:
            message = client_socket.recv(1024)
            if not message:
                break  # Client disconnected
            if message == b'SHUTDOWN':
                print("Shutdown command received from client. Shutting down server...")
                shutdown_server(signal.SIGINT, None)
    except Exception as e:
        print(f"Error handling client: {e}")
    finally:
        print("Client disconnected. Server is back to dormant mode.")
        client_connected.clear()  # Indicate that the client is disconnected
        client_socket.close()

if __name__ == "__main__":
    run_server()
