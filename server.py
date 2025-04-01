import socket
import threading
import rsa
import os
import hashlib


class ChatServer:
    def __init__(self, host="0.0.0.0", port=27101, encryption_size=4096):
        self.host = host
        self.port = port
        self.encryption_size = encryption_size
        self.server_socket = None
        self.clients = []  # List of (client_socket, client_address, public_key, username) tuples
        self.public_key = None
        self.private_key = None
        
        # Password configuration
        self.password = None
        self.password_hash = None
        self.password_file = "server_password.txt"
        
    def setup_password(self):
        """Set up or load the server password"""
        if os.path.exists(self.password_file):
            # Load existing password hash
            with open(self.password_file, 'r') as f:
                self.password_hash = f.read().strip()
            print("Loaded existing password hash.")
        else:
            # Create a new password
            while True:
                password = input("Set server password (min 8 characters): ")
                if len(password) >= 8:
                    break
                print("Password too short. Please use at least 8 characters.")
            
            # Hash the password
            self.password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            # Save the password hash
            with open(self.password_file, 'w') as f:
                f.write(self.password_hash)
            
            print("New password set and saved.")

    def check_password(self, password):
        """Check if the provided password matches the stored hash"""
        provided_hash = hashlib.sha256(password.encode()).hexdigest()
        return provided_hash == self.password_hash

    def start(self):
        # Set up password
        self.setup_password()
        
        # Generate keys
        print("Generating RSA keys...")
        self.public_key, self.private_key = rsa.newkeys(self.encryption_size)

        # Initialize server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)

        print(f"Chat server started on {self.host}:{self.port}")
        print("Waiting for connections...")

        # Main loop to accept connections
        try:
            while True:
                client_socket, client_address = self.server_socket.accept()
                print(f"New connection from {client_address[0]}:{client_address[1]}")

                # Start a thread to handle this client
                client_thread = threading.Thread(
                    target=self.handle_client, args=(client_socket, client_address)
                )
                client_thread.daemon = True
                client_thread.start()
        except KeyboardInterrupt:
            print("\nShutting down server...")
        finally:
            if self.server_socket:
                self.server_socket.close()

    def handle_client(self, client_socket, client_address):
        try:
            # Exchange keys
            client_socket.send(self.public_key.save_pkcs1("PEM"))
            client_public_key_data = client_socket.recv(self.encryption_size * 2)
            client_public_key = rsa.PublicKey.load_pkcs1(client_public_key_data)

            # Get client password
            encrypted_password = client_socket.recv(self.encryption_size)
            password = rsa.decrypt(encrypted_password, self.private_key).decode()
            
            # Check password
            if not self.check_password(password):
                print(f"Authentication failed for client {client_address}")
                # Send authentication failed message
                auth_failed_msg = "AUTHFAILED:Incorrect password."
                encrypted_auth_failed = rsa.encrypt(auth_failed_msg.encode(), client_public_key)
                client_socket.send(encrypted_auth_failed)
                client_socket.close()
                return
                
            # Send authentication success message
            auth_success_msg = "AUTHSUCCESS:Authentication successful."
            encrypted_auth_success = rsa.encrypt(auth_success_msg.encode(), client_public_key)
            client_socket.send(encrypted_auth_success)

            # Get client username
            encrypted_username = client_socket.recv(self.encryption_size)
            username = rsa.decrypt(encrypted_username, self.private_key).decode()

            # Add client to clients list
            client_info = (client_socket, client_address, client_public_key, username)
            self.clients.append(client_info)

            # Send current user count to all clients
            user_count_msg = f"USERCOUNT:{len(self.clients)}"
            self.broadcast_system_message(user_count_msg)

            # Broadcast join message
            join_message = f"{username} has joined the chat"
            self.broadcast_message("SERVER", join_message, client_socket)

            # Send welcome message to the client
            welcome_msg = f"Welcome to the chat, {username}!"
            self.send_message_to_client(
                client_socket, client_public_key, "SERVER", welcome_msg
            )

            # Handle client messages
            while True:
                try:
                    encrypted_message = client_socket.recv(self.encryption_size)
                    if not encrypted_message:
                        break

                    message = rsa.decrypt(encrypted_message, self.private_key).decode()
                    print(f"Message from {username}: {message}")

                    # Broadcast message to all clients INCLUDING the sender
                    self.broadcast_message(username, message)

                except Exception as e:
                    print(f"Error receiving message from {username}: {str(e)}")
                    break

        except Exception as e:
            print(f"Error handling client {client_address}: {str(e)}")
        finally:
            # Remove client from list and close connection
            self.remove_client(client_socket)
            client_socket.close()

    def broadcast_message(self, sender, message, exclude_socket=None):
        """Send a message to all clients except those in exclude_socket"""
        for client in self.clients[
            :
        ]:  # Create a copy of the list to avoid issues if list changes
            client_socket, _, client_public_key, _ = client

            # Skip excluded sockets (if any)
            if exclude_socket is not None and client_socket == exclude_socket:
                continue

            try:
                self.send_message_to_client(
                    client_socket, client_public_key, sender, message
                )
            except Exception:
                # If sending fails, assume client disconnected
                self.remove_client(client_socket)

    def broadcast_system_message(self, message):
        """Send a system message to all clients"""
        for client in self.clients[:]:
            client_socket, _, client_public_key, _ = client
            try:
                encrypted_message = rsa.encrypt(message.encode(), client_public_key)
                client_socket.send(encrypted_message)
            except Exception:
                # If sending fails, assume client disconnected
                self.remove_client(client_socket)

    def send_message_to_client(self, client_socket, client_public_key, sender, message):
        """Encrypt and send a message to a specific client"""
        formatted_message = f"{sender}: {message}"

        # RSA can only encrypt limited amount of data, so we need to handle large messages
        # For simplicity, we'll just truncate messages that are too long
        max_msg_length = (
            self.encryption_size // 8 - 42
        )  # RSA overhead is 42 bytes for PKCS#1 v1.5
        if len(formatted_message) > max_msg_length:
            formatted_message = (
                formatted_message[:max_msg_length] + "... (message truncated)"
            )

        encrypted_message = rsa.encrypt(formatted_message.encode(), client_public_key)
        client_socket.send(encrypted_message)

    def remove_client(self, client_socket):
        """Remove a client from the clients list"""
        for i, client in enumerate(self.clients):
            if client[0] == client_socket:
                _, _, _, username = client
                self.clients.pop(i)
                print(f"{username} has disconnected")
                self.broadcast_message("SERVER", f"{username} has left the chat")

                # Send updated user count
                user_count_msg = f"USERCOUNT:{len(self.clients)}"
                self.broadcast_system_message(user_count_msg)
                break


if __name__ == "__main__":
    boop = input("Press enter to continue :3")
    
    # Get server IP (default to local)
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    # local_ip = "127.0.0.1"

    print(f"Your local IP address is: {local_ip}")


    # Allow specifying different IP and port
    server_ip = input(f"Enter server IP (press Enter for {local_ip}): ") or local_ip
    try:
        server_port = int(input("Enter server port (press Enter for 27101): ") or 27101)
    except ValueError:
        server_port = 27101

    server = ChatServer(server_ip, server_port)
    server.start()