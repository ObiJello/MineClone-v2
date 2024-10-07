import socket
import struct
import io
import time
import mss
from PIL import Image
import sys

def screen_streamer(client_socket):
    """Stream the screen when a client connects."""
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # Capture the first monitor
        while True:
            try:
                sct_img = sct.grab(monitor)
                image = Image.frombytes('RGB', (sct_img.width, sct_img.height), sct_img.rgb)
                image = image.resize((800, 600))
                img_byte_array = io.BytesIO()
                image.save(img_byte_array, format='JPEG', quality=40)
                img_bytes = img_byte_array.getvalue()
                client_socket.sendall(struct.pack("L", len(img_bytes)) + img_bytes)
                time.sleep(1 / 24)  # 24 FPS
            except Exception as e:
                print(f"Error in screen streaming: {e}", file=sys.stderr)
                break

def run_server():
    """Start the server and wait for client connections."""
    stream_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    stream_socket.bind(('0.0.0.0', 9999))  # Listen on port 9999
    stream_socket.listen(5)
    
    print("Server is dormant, waiting for client connection...")

    while True:
        client_socket, addr = stream_socket.accept()
        print(f"Client connected from {addr}. Starting screen stream...")
        screen_streamer(client_socket)
        print("Client disconnected. Server is back to dormant mode.")

if __name__ == "__main__":
    run_server()

