
import socket
import threading
import os
 
# Global variables
connections = []
downloads_folder = "Downloads"
share_folder = "share"
share_port = 6000

def connect(host, port):
    # Connect to a given node in the Gnutella network
    host = '130.179.28.133'
    port = 1234
    global connections
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.connect((host, port))
    connections.append(sock)
    print("Connected to {}:{}".format(host, port))

def handle_query(data, conn):
    # Handle an incoming query from another node in the Gnutella network
    global share_folder, connections
    query = data.split()[1]
    if os.path.isdir(share_folder):
        for file_name in os.listdir(share_folder):
            if query.lower() in file_name.lower():
                file_path = os.path.join(share_folder, file_name)
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                    response_str = "FOUND {} {}\r\n".format(file_name, len(file_data))
                    response_str += "Address {}:{}\r\n".format(socket.gethostbyname(socket.gethostname()), share_port)
                    conn.sendall(response_str.encode())
                return
    # If file is not found locally, forward the query to all connections except the one that sent the query
    for connection in connections:
        if connection != conn:
            connection.sendall(data.encode())
def handle_download_query(data, conn):
    global share_folder
    query = data.split()[1]
    if os.path.isdir(share_folder):
        for file_name in os.listdir(share_folder):
            if query.lower() in file_name.lower():
                file_path = os.path.join(share_folder, file_name)
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                    conn.sendall(file_data)
                conn.close()
                return

def handle_connection(conn, addr):
    # Handle an incoming connection from another node in the Gnutella network
    print("Connected to {}:{} (incoming)".format(addr[0], addr[1]))
    while True:
        try:
            data = conn.recv(1024).decode()
            if not data:
                break
            elif data.startswith("SEARCH"):
                threading.Thread(target=handle_query, args=(data, conn)).start()
            elif data.startswith("RETR"):
                threading.Thread(target=handle_download_query, args=(data, conn)).start()
        except ConnectionResetError:
            break
    conn.close()
    print("Connection to {}:{} closed (incoming)".format(addr[0], addr[1]))
 
def listen(port):
    # Listen for incoming connections from other nodes in the Gnutella network
    global connections
    host = ""  # accept connections on all available network interface
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen()
    if port == share_port:
        print("Listening for incoming connections for file sharing")
    else:
        print("Listening for incoming connections on port {}".format(port))
    while True:
        conn, addr = sock.accept()
        connections.append(conn)
        threading.Thread(target=handle_connection, args=(conn, addr), daemon=True).start()
 
def disconnect(connection_num):
    # Disconnect from a specific connection or all connections if no argument is provided
    global connections
    if connection_num == "":
        for conn in connections:
            conn.close()
        connections.clear()
        print("All connections closed")
    else:
        try:
            conn_index = int(connection_num) - 1
            conn = connections[conn_index]
            conn.close()
            connections.pop(conn_index)
            print("Connection {} closed".format(connection_num))
        except IndexError:
            print("Invalid connection number")
 
def list_connections():
    # List all current connections
    global connections
    if not connections:
        print("No active connections")
    else:
        for i, conn in enumerate(connections):
            print("{}: {}:{}".format(i+1, conn.getpeername()[0], conn.getpeername()[1]))
 
file_nodes = {}
def search(query):
    # Search for files on the Gnutella network
    global connections, share_folder, file_nodes
    query_str = "SEARCH {}\r\n".format(query)
    nodes_with_file = []
    for conn in connections:
        conn.sendall(query_str.encode())
        response = conn.recv(1024).decode()
        if response.startswith("FOUND"):
            lines = response.split("\n")
            _, file_name, file_size = lines[0].split(" ")
            address = lines[1].split(" ")
            ip, port = address[1].split(":")
            nodes_with_file.append((file_name.strip(), file_size.strip(), (ip.strip(), port.strip())))
    if os.path.isdir(share_folder):
        for file_name in os.listdir(share_folder):
            if query.lower() in file_name.lower():
                file_path = os.path.join(share_folder, file_name)
                file_size = os.path.getsize(file_path)
                file_node = (socket.gethostbyname(socket.gethostname()), 6000)
                if file_name not in file_nodes:
                    file_nodes[file_name] = []
                if file_node not in file_nodes[file_name]:
                    file_nodes[file_name].append(file_node)
                nodes_with_file.append((file_name, file_size, file_nodes[file_name]))
    
    return nodes_with_file

def search_and_download(query):
    nodes_with_file = search(query)
    if not nodes_with_file:
        print("File not found")
        return
    
    for i, (file_name, file_size, address) in enumerate(nodes_with_file):
        print(f"{i+1}. {address[0]}:{address[1]}")
    choice = input("Enter the number of the node to download from: ")
    try:
        choice_index = int(choice) - 1
        selected_node = nodes_with_file[choice_index]
        ftp_host, ftp_port = selected_node[2][0], selected_node[2][1]
        download(selected_node[0], ftp_host, int(ftp_port))
    except (ValueError, IndexError) as e:
        print(e)
        print("Invalid choice")
    
 
def download(file_name, ftp_host=None, ftp_port=None):
    # Download a file from the Gnutella network using FTP
    global connections, downloads_folder, file_nodes
    download_path = os.path.join(downloads_folder, file_name)
    if not os.path.exists(downloads_folder):
        os.makedirs(downloads_folder)
    if ftp_host and ftp_port:
        print("Connecting to {}:{}".format(ftp_host, ftp_port))
        with open(download_path, 'wb') as f:
            ftp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ftp_sock.connect((ftp_host, ftp_port))
            ftp_sock.sendall(("RETR {}\r\n".format(file_name)).encode())
            ftp_sock.settimeout(3)  # Set a timeout of 10 seconds on the socket

            while True:
                try:
                    data = ftp_sock.recv(4096)
                    if not data:
                        break
                    f.write(data)
                except socket.timeout:
                    break
            ftp_sock.close()
        print("File downloaded to {}".format(download_path))
        return
    # for conn in connections:
    #     query_str = "DOWNLOAD {}\r\n".format(file_name)
    #     conn.sendall(query_str.encode())
    #     response = conn.recv(1024).decode()
    #     if response.startswith("FOUND"):
    #         parts = response.split("\r\n")
    #         host = parts[1].split()[1]
    #         port = int(parts[2].split()[1])
    #         ftp_host, ftp_port = host, port
    #         with open(download_path, 'wb') as f:
    #             ftp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #             ftp_sock.connect((ftp_host, ftp_port))
    #             ftp_sock.sendall(b"RETR {}\r\n".format(file_name))
    #             while True:
    #                 data = ftp_sock.recv(1024)
    #                 if not data:
    #                     break
    #                 f.write(data)
    #             ftp_sock.close()
    #         print("File downloaded to {}".format(download_path))
    #         file_node = (host, port)
    #         if file_name not in file_nodes:
    #             file_nodes[file_name] = []
    #         if file_node not in file_nodes[file_name]:
    #             file_nodes[file_name].append(file_node)
    #         return
    print("File not found")

 
def help_menu():
    # Show the help message
    print("Commands:")
    print("connect [host] [port] - Connect to a node in the Gnutella network")
    print("disconnect [connection number] - Disconnect from the specified connection or all connections")
    print("list - List all current connections")
    print("search [query] - Search for files on the Gnutella network")
    print("download [file name] - Download a file from the Gnutella network")
    print("help - Show this help message")
    print("quit - Quit the client")
    
def prompt_loop():
    # Prompt loop
    while True:
        user_input = input("> ").split()
        command = user_input[0]
        args = user_input[1:]
        if command == "c":
            connect('1', 2)
            # if len(args) != 2:
            #     print("Usage: connect [host] [port]")
            # else:
            #     try:
            #         host = args[0]
            #         port = int(args[1])
            #         connect(host, port)
            #     except ValueError:
            #         print("Invalid port number")
        # start listening in a separate thread
        elif command == "disconnect":
            disconnect(args[0] if args else "")
        elif command == "list":
            list_connections()
        elif command == "s":
            #TODO change this
            search_and_download('atest')
        elif command == "help":
            help_menu()
        elif command == "quit":
            for conn in connections:
                conn.close()
            print("Goodbye!")
            break
        else:
            print("Invalid command. Type 'help' for a list of commands.")

if __name__ == '__main__':
    threading.Thread(target=listen, args=(1234,), daemon=True).start()  # start listening in a separate thread
    threading.Thread(target=listen, args=(share_port,), daemon=True).start()  # start listening in a separate thread
    prompt_loop()
