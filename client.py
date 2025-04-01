import socket
import threading
import rsa
import curses
import time
import os
import dotenv

from curses import wrapper
from getpass import getpass


class ChatClient:
    def __init__(self, server_ip, server_port=27101, encryption_size=4096):
        self.server_ip = server_ip
        self.server_port = server_port
        self.encryption_size = encryption_size
        self.client_socket = None
        self.public_key = None
        self.private_key = None
        self.server_public_key = None
        self.username = "Anonymous"
        self.message_history = []
        self.input_str = ""
        self.stdscr = None
        self.send_message_flag = False
        self.connected = False
        self.user_count = 1  # Default to 1 (self)
        self.key_folder = "keys"  # Folder to store keys
        self.env_file = ".env"  # Environment file to store password
        
    def load_or_generate_keys(self, username):
        """Load RSA keys from files or generate new ones if files don't exist"""
        # Create keys directory if it doesn't exist
        if not os.path.exists(self.key_folder):
            os.makedirs(self.key_folder)
            
        private_key_path = os.path.join(self.key_folder, f"{username}_private.pem")
        public_key_path = os.path.join(self.key_folder, f"{username}_public.pem")
        
        # Check if key files exist
        if os.path.exists(private_key_path) and os.path.exists(public_key_path):
            try:
                # Load existing keys
                print("Loading existing RSA keys...")
                with open(private_key_path, 'rb') as f:
                    private_key_data = f.read()
                    self.private_key = rsa.PrivateKey.load_pkcs1(private_key_data)
                
                with open(public_key_path, 'rb') as f:
                    public_key_data = f.read()
                    self.public_key = rsa.PublicKey.load_pkcs1(public_key_data)
                
                print("Keys loaded successfully.")
                return True
            except Exception as e:
                print(f"Error loading keys: {str(e)}. Generating new keys...")
        
        # Generate new keys if files don't exist or loading failed
        try:
            print("Generating new RSA keys (can take a bit)...")
            self.public_key, self.private_key = rsa.newkeys(self.encryption_size)
            
            # Save the keys to files
            with open(private_key_path, 'wb') as f:
                f.write(self.private_key.save_pkcs1('PEM'))
            
            with open(public_key_path, 'wb') as f:
                f.write(self.public_key.save_pkcs1('PEM'))
            
            print("New keys generated and saved.")
            return True
        except Exception as e:
            print(f"Error generating keys: {str(e)}")
            return False

    def load_or_set_password(self, server_ip):
        """Load the password from .env file or prompt the user to set one"""
        # Create .env file if it doesn't exist
        if not os.path.exists(self.env_file):
            with open(self.env_file, 'w') as f:
                f.write("# Chat client environment file\n")
            print(f"Created {self.env_file} file.")
        
        # Load environment variables
        dotenv.load_dotenv(self.env_file)
        
        # Check if we have a password for this server
        password_key = f"CHAT_PASSWORD_{server_ip.replace('.', '_')}"
        password = os.environ.get(password_key)
        
        if not password:
            # Prompt for password
            password = getpass(f"Enter password for server {server_ip}: ")
            
            # Save the password to .env file
            with open(self.env_file, 'a') as f:
                f.write(f"\n{password_key}={password}")
            
            # Reload environment variables
            dotenv.load_dotenv(self.env_file)
            
            print(f"Password saved for server {server_ip}.")
        
        return password

    def connect(self, username):
        """Connect to the chat server"""
        self.username = username

        try:
            # Load or generate keys
            if not self.load_or_generate_keys(username):
                return False
                
            # Load or set password
            password = self.load_or_set_password(self.server_ip)

            # Connect to server
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.server_ip, self.server_port))

            # Exchange keys
            self.server_public_key = rsa.PublicKey.load_pkcs1(
                self.client_socket.recv(self.encryption_size * 2)
            )
            self.client_socket.send(self.public_key.save_pkcs1("PEM"))
            
            # Send password
            encrypted_password = rsa.encrypt(password.encode(), self.server_public_key)
            self.client_socket.send(encrypted_password)
            
            # Wait for authentication response
            encrypted_auth_response = self.client_socket.recv(self.encryption_size)
            auth_response = rsa.decrypt(encrypted_auth_response, self.private_key).decode()
            
            # Check if authentication was successful
            if auth_response.startswith("AUTHFAILED:"):
                error_message = auth_response.split(":", 1)[1]
                print(f"Authentication failed: {error_message}")
                
                # Remove password from .env if it's incorrect
                password_key = f"CHAT_PASSWORD_{self.server_ip.replace('.', '_')}"
                self.update_env_file(password_key, None)
                
                return False

            # Send username
            encrypted_username = rsa.encrypt(username.encode(), self.server_public_key)
            self.client_socket.send(encrypted_username)

            self.connected = True
            print(f"Connected to server at {self.server_ip}:{self.server_port}")
            return True

        except Exception as e:
            print(f"Failed to connect: {str(e)}")
            if self.client_socket:
                self.client_socket.close()
            return False
    
    def update_env_file(self, key, value):
        """Update a value in the .env file"""
        # Read existing env file
        if os.path.exists(self.env_file):
            with open(self.env_file, 'r') as f:
                lines = f.readlines()
        else:
            lines = []
        
        # Remove the key if it exists
        lines = [line for line in lines if not line.strip().startswith(f"{key}=")]
        
        # Add the new value if provided
        if value is not None:
            lines.append(f"{key}={value}\n")
        
        # Write back to file
        with open(self.env_file, 'w') as f:
            f.writelines(lines)

    def disconnect(self):
        """Disconnect from the server"""
        if self.client_socket:
            self.client_socket.close()
        self.connected = False

    def receiving_messages(self):
        """Thread function to receive messages from the server"""
        while self.connected:
            try:
                encrypted_message = self.client_socket.recv(self.encryption_size)
                if not encrypted_message:
                    self.message_history.append(("system", "Disconnected from server"))
                    self.update_screen()
                    self.connected = False
                    break

                message = rsa.decrypt(encrypted_message, self.private_key).decode()

                # Check if this is a system message for user count
                if message.startswith("USERCOUNT:"):
                    self.user_count = int(message.split(":", 1)[1])
                    self.update_screen()
                    continue

                # Split the message into sender and content
                if ": " in message:
                    sender, content = message.split(": ", 1)
                    self.message_history.append((sender, content))
                else:
                    self.message_history.append(("system", message))

                # print("\a") # SO ANNOYING

                self.update_screen()

            except Exception as e:
                self.message_history.append(
                    ("system", f"Error receiving message: {str(e)}")
                )
                self.update_screen()
                self.connected = False
                break

    def sending_messages(self):
        """Thread function to send messages to the server"""
        while self.connected:
            try:
                if self.send_message_flag and self.input_str:
                    message = self.input_str
                    message_encrypted = rsa.encrypt(
                        message.encode(), self.server_public_key
                    )
                    self.client_socket.send(message_encrypted)

                    # Note: We no longer add the message to history here
                    # The server will broadcast it back to us

                    self.input_str = ""
                    self.send_message_flag = False
                    self.update_screen()

                # Short sleep to prevent this thread from hogging CPU
                time.sleep(0.1)

            except Exception as e:
                self.message_history.append(
                    ("system", f"Error sending message: {str(e)}")
                )
                self.update_screen()
                self.connected = False
                break

    def update_screen(self):
        """Update the curses UI with the latest messages and input"""
        if self.stdscr is None:
            return

        # Get terminal dimensions
        height, width = self.stdscr.getmaxyx()

        # Clear the screen
        self.stdscr.clear()

        # Display message history
        max_messages = height - 3  # Leave space for input and a divider
        start_index = max(0, len(self.message_history) - max_messages)

        # Draw a header with user count
        header = f" ~ the void ~ | {self.username} on {self.server_ip}:{self.server_port} | users: {self.user_count} "
        self.stdscr.addstr(0, max(0, (width - len(header)) // 2), header[: width - 1])
        self.stdscr.addstr(1, 0, "=" * width)

        for i, (sender, msg) in enumerate(self.message_history[start_index:]):
            if i >= max_messages:
                break

            # Format the message based on sender
            if sender == "system":
                message_text = f"[SYSTEM] {msg}"
            elif sender == "SERVER":
                message_text = f"[SERVER] {msg}"
            else:
                message_text = f"{sender}: {msg}"

            # Truncate message if it's too long for the screen
            if len(message_text) > width - 2:
                message_text = message_text[: width - 5] + "..."

            self.stdscr.addstr(i + 2, 0, message_text)  # +2 for header and divider

        # Draw input line
        input_line = f"> {self.input_str}"
        if len(input_line) > width - 2:
            visible_input = input_line[-(width - 2) :]
            cursor_pos = width - 1
        else:
            visible_input = input_line
            cursor_pos = len(visible_input)

        self.stdscr.addstr(height - 1, 0, visible_input)
        self.stdscr.move(height - 1, cursor_pos)

        # Refresh the screen
        self.stdscr.refresh()

    def main_ui(self, screen):
        """Main UI function for the curses interface"""
        self.stdscr = screen
        curses.echo()
        curses.cbreak()
        self.stdscr.keypad(True)

        # Start the receiving thread
        recv_thread = threading.Thread(target=self.receiving_messages)
        recv_thread.daemon = True
        recv_thread.start()

        # Start the sending thread
        send_thread = threading.Thread(target=self.sending_messages)
        send_thread.daemon = True
        send_thread.start()

        # Add a welcome message
        self.message_history.append(("system", f"Connected as {self.username}"))
        self.message_history.append(("system", "Press ESC to exit"))

        # Initial screen update
        self.update_screen()

        # Main input loop
        while self.connected:
            try:
                # Get user input
                c = self.stdscr.getch()

                if c == ord("\n"):  # Enter key
                    if self.input_str:
                        # Set the flag to send the message
                        self.send_message_flag = True
                        # Wait a bit to ensure the message is processed
                        time.sleep(0.1)
                elif c == curses.KEY_BACKSPACE or c == 127:  # Backspace key
                    if self.input_str:
                        self.input_str = self.input_str[:-1]
                elif c == curses.KEY_RESIZE:
                    # Terminal was resized
                    self.stdscr.clear()
                elif c == 27:  # ESC key to exit
                    break
                elif 32 <= c <= 126:  # Printable ASCII characters
                    self.input_str += chr(c)

                # Update the screen after any input
                self.update_screen()

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.message_history.append(("system", f"Error: {str(e)}"))
                time.sleep(1)

        # Clean up
        self.disconnect()


if __name__ == "__main__":
    # Check for required packages
    try:
        import dotenv
    except ImportError:
        print("The 'python-dotenv' package is required. Installing...")
        import subprocess
        subprocess.check_call(["pip", "install", "python-dotenv"])
        import dotenv
        print("Package installed successfully.")

    # Get server connection details
    server_ip = str(input("Enter server IP address: ") or "127.0.0.1")
    try:
        server_port = int(input("Enter server port (press Enter for 27101): ") or 27101)
    except ValueError:
        server_port = 27101

    username = input("Enter your username: ")
    if not username:
        username = f"User_{hash(time.time()) % 1000}"

    # Initialize client
    client = ChatClient(server_ip, server_port)

    # Connect to server
    if client.connect(username):
        try:
            # Start the curses interface
            wrapper(client.main_ui)
        except Exception as e:
            print(f"Error in UI: {str(e)}")
        finally:
            # Make sure we disconnect properly
            client.disconnect()
            print("Disconnected from server")
    else:
        print("Failed to connect to server")