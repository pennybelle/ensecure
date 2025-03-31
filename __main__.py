import socket
import threading
import rsa
import curses
from curses import wrapper
import time

port = 9987
encryption_type = 4096
public_key = None
private_key = None
public_partner = None
client = None
message_history = []
input_str = ""
stdscr = None
send_message_flag = False  # Flag to indicate when to send a message


def init_connection():
    global public_key, private_key, public_partner, client

    print("generating keys...")
    public_key, private_key = rsa.newkeys(encryption_type)
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)  # using local ip for testing

    choice = input("do you want to host (1) or connect (2): ")
    if choice == "1":
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((local_ip, port))  # TODO: enter ip via input()
        server.listen()
        print("Waiting for connection...")
        # this script is only designed for one connection to host
        # must be redesigned for multiple connections to host
        client, _ = server.accept()
        client.send(public_key.save_pkcs1("PEM"))
        public_partner = rsa.PublicKey.load_pkcs1(client.recv(encryption_type))
    elif choice == "2":
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((local_ip, port))
        public_partner = rsa.PublicKey.load_pkcs1(client.recv(encryption_type))
        client.send(public_key.save_pkcs1("PEM"))
    else:
        print("Invalid Input")
        exit()


def receiving_messages():
    global message_history, stdscr

    while True:
        try:
            message = rsa.decrypt(client.recv(encryption_type), private_key).decode()
            message_history.append(("them", message))

            # Update the screen
            update_screen()
        except Exception as e:
            message_history.append(("system", f"Error receiving message: {str(e)}"))
            update_screen()
            break


def sending_messages():
    global input_str, message_history, stdscr, send_message_flag

    while True:
        try:
            if send_message_flag and input_str:
                message = input_str
                message_encrypted = rsa.encrypt(message.encode(), public_partner)
                client.send(message_encrypted)
                message_history.append(("you", message))
                input_str = ""
                send_message_flag = False  # Reset the flag
                update_screen()

            # Short sleep to prevent this thread from hogging CPU
            time.sleep(0.1)
        except Exception as e:
            message_history.append(("system", f"Error sending message: {str(e)}"))
            update_screen()
            break


def update_screen():
    global stdscr, message_history, input_str

    if stdscr is None:
        return

    # Get terminal dimensions
    height, width = stdscr.getmaxyx()

    # Clear the screen
    stdscr.clear()

    # Display message history
    max_messages = height - 2
    start_index = max(0, len(message_history) - max_messages)
    for i, (sender, msg) in enumerate(message_history[start_index:]):
        if i >= max_messages:
            break

        if sender == "you":
            message_text = f"you: {msg}"
        elif sender == "them":
            message_text = f"them: {msg}"
        else:
            message_text = f"[{msg}]"

        # Truncate message if it's too long for the screen
        if len(message_text) > width - 2:
            message_text = message_text[: width - 5] + "..."

        stdscr.addstr(i, 0, message_text)

    # Draw input line
    input_line = f"> {input_str}"
    if len(input_line) > width - 2:
        visible_input = input_line[-(width - 2) :]
        cursor_pos = width - 1
    else:
        visible_input = input_line
        cursor_pos = len(visible_input)

    stdscr.addstr(height - 1, 0, visible_input)
    stdscr.move(height - 1, cursor_pos)

    # Refresh the screen
    stdscr.refresh()


def main(screen):
    global stdscr, input_str, message_history, send_message_flag

    # Initialize curses
    stdscr = screen
    curses.echo()
    curses.cbreak()
    stdscr.keypad(True)

    # Start the receiving thread
    recv_thread = threading.Thread(target=receiving_messages)
    recv_thread.daemon = True
    recv_thread.start()

    # Start the sending thread
    send_thread = threading.Thread(target=sending_messages)
    send_thread.daemon = True
    send_thread.start()

    # Initial screen update
    update_screen()

    # Main input loop
    while True:
        try:
            # Get user input
            c = stdscr.getch()

            if c == ord("\n"):  # Enter key
                if input_str:
                    # Set the flag to send the message
                    send_message_flag = True
                    # Wait a bit to ensure the message is processed
                    time.sleep(0.1)
            elif c == curses.KEY_BACKSPACE or c == 127:  # Backspace key
                if input_str:
                    input_str = input_str[:-1]
            elif c == curses.KEY_RESIZE:
                # Terminal was resized
                stdscr.clear()
            elif c == 27:  # ESC key to exit
                break
            elif 32 <= c <= 126:  # Printable ASCII characters
                input_str += chr(c)

            # Update the screen after any input
            update_screen()

        except KeyboardInterrupt:
            break
        except Exception as e:
            message_history.append(("system", f"Error: {str(e)}"))
            time.sleep(1)

    # Clean up
    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    curses.endwin()


if __name__ == "__main__":
    # Initialize connection before starting curses
    init_connection()

    # Start the curses interface
    wrapper(main)
