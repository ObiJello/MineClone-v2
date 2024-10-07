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

# Variable to store the ngrok tunnel object
ngrok_tunnel = None

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
    sys.exit(0)

def run_server():
    """Start the server and wait for client connections."""
    global ngrok_tunnel

    # Set up a signal handler to handle Ctrl+C and termination
    signal.signal(signal.SIGINT, shutdown_server)

    # Configure Ngrok authentication
    conf.get_default().auth_token = "2n6dGlsHf3g0Z5TIssTAmGpbwj5_6NcTVBnzq5LX7UpxZsJEL"  # Replace with your Ngrok auth token

    # Expose port 9999 using Ngrok
    ngrok_tunnel = ngrok.connect(9999, "tcp")
    public_url = ngrok_tunnel.public_url
    print(f"Ngrok tunnel created: {public_url}")

    # Send the public IP and port to the client machine
    client_ip = "192.168.1.180"  # Replace with the actual IP address of the client machine
    client_port = 5321  # The port where the client will listen for the IP
    send_public_ip_to_client(public_url, client_ip, client_port)

    # Now start the server
    stream_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    stream_socket.bind(('0.0.0.0', 9999))  # Listen on port 6789
    stream_socket.listen(5)

    print("Server is dormant, waiting for client connection...")

    while True:
        client_socket, addr = stream_socket.accept()
        print(f"Client connected from {addr}. Starting screen stream...")
        screen_streamer(client_socket)
        print("Client disconnected. Server is back to dormant mode.")

if __name__ == "__main__":
    run_server()
