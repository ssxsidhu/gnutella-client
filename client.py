import json
import socket
import threading
import os
import time

import requests
 
# Global variables

DOWNLOADS_FOLDER = "Downloads"
SHARE_FOLDER = "Share"
CONNECTION_PORT = 6346
SHARE_PORT = 60000
LOG_HOST = '127.0.0.1'
LOG_PORT = 60001
SEARCH_WAIT = 3

connections = []
known_nodes = [
    '3.136.250.73',
    '18.220.250.155',
    '3.133.123.99'
]
search_results = []
connected_node_address =[]

semaphore = threading.Semaphore(1)

def get_public_ip():
    try:
        response = requests.get('https://api.ipify.org').text
        return response
    except requests.exceptions.RequestException as e:
        print(e)
        return None

def connect(host, port, query_message = None):
    # Connect to a given node in the Gnutella network
    global connections
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    address = host+':'+str(port)
    try:
        if host != NODE_PUBLIC_IP:
            if address not in connected_node_address:
                sock.connect((host, port))
                connections.append(sock)
                connected_node_address.append(address)
                if  query_message ==  None:
                    print("Connected to {}:{}".format(host, port))
                    threading.Thread(target=handle_connection, args=(sock,(host,port)), daemon=True).start()
                return sock
            else:
                print("Already connected!")
        else:
            print("Cannot connect to itself")
    except ConnectionRefusedError as e:
        print(e)

def send_log(log_msg):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Send the log message
    sock.sendto(log_msg.encode(), (LOG_HOST, LOG_PORT))

    # Close the UDP socket
    sock.close()

def handle_query(data, conn):
    # Handle an incoming query from another node in the Gnutella network
    global SHARE_FOLDER, connections, connected_node_address
    query = data.split()[1]
    address = data.split('ADDRESS')[1].strip()
    host, port = address.split(':')

    if os.path.isdir(SHARE_FOLDER):
        for file_name in os.listdir(SHARE_FOLDER):
            if query.lower() in file_name.lower():
                file_path = os.path.join(SHARE_FOLDER, file_name)
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                    response_str = "FOUND {} {}\r\n".format(file_name, len(file_data))
                    response_str += "ADDRESS {}:{}\r\n".format(NODE_PUBLIC_IP, SHARE_PORT)
                    sock = connect(host, int(port), '0')
                    sock.sendall(response_str.encode())
                    sock.close()
                    connections.remove(sock)
                    connected_node_address.remove(address)
            
    # If file is not found locally, forward the query to all connections except the one that sent the query
    for connection in connections:
        if connection != conn and host != NODE_PUBLIC_IP:
            try:
                connection.sendall(data.encode())
            except (BrokenPipeError, OSError):
                connections.remove(connection)
                connected_node_address.remove(address)

    
    
def handle_download_query(data, conn):
    global SHARE_FOLDER
    query = data.split()[1]
    if os.path.isdir(SHARE_FOLDER):
        for file_name in os.listdir(SHARE_FOLDER):
            if query.lower() in file_name.lower():
                file_path = os.path.join(SHARE_FOLDER, file_name)
                send_log('\nSending file {}\n'.format(file_name))
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                    conn.sendall(file_data)
                conn.close()
                connections.remove(conn)
                return

def handle_connection(conn, addr, incoming = None):
    # Handle an incoming connection from another node in the Gnutella network
    global search_results
    if incoming:
        send_log("\nConnected to {}:{} (incoming)\n".format(addr[0], addr[1]))
    while True:
        try:
            data = conn.recv(4096)
            if not data:
                break
            else:
                data = data.decode('utf-8', errors='ignore')            
            
            
            send_log('\nMESSAGE received from {}:{}\n'.format(addr[0],addr[1]))
            send_log('{\n'+data+'}')
            if data.startswith("SEARCH"):
                threading.Thread(target=handle_query, args=(data, conn)).start()
            elif data.startswith("FOUND"):
                search_results.append(response_search(data))
            elif data.startswith("RETR"):
                threading.Thread(target=handle_download_query, args=(data, conn)).start()
            
        except (ConnectionResetError, ConnectionAbortedError):
            break
    conn.close()
    if  conn in connections:
        connections.remove(conn)
        address = addr[0]+':'+str(addr[1])
        if address in connected_node_address:
            connected_node_address.remove(address)

    if incoming:
        send_log("\nConnection to {}:{} closed (incoming)\n".format(addr[0], addr[1]))
 
def listen(port):
    # Listen for incoming connections from other nodes in the Gnutella network
    global connections
    semaphore.acquire()

    host = ""  # accept connections on all available network interface
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen()
    if port == SHARE_PORT:
        print("*Listening for incoming Messages and File sharing on port {}".format(SHARE_PORT))
    else:
        print("*Listening for incoming connections on port {}".format(port))
    semaphore.release()

    while True:
        conn, addr = sock.accept()
        connections.append(conn)
        threading.Thread(target=handle_connection, args=(conn, addr, '1'), daemon=True).start()
 
def disconnect(connection_num):
    # Disconnect from a specific connection or all connections if no argument is provided
    global connections
    if connection_num == "":
        for conn in connections:
            conn.close()
        connections.clear()
        connected_node_address.clear()
        print("All connections closed")
    else:
        try:
            conn_index = int(connection_num) - 1
            conn = connections[conn_index]
            remove_from_connected(conn)
            connections.pop(conn_index)
            conn.close()
            print("Connection {} closed".format(connection_num))
        except IndexError:
            print("Invalid connection number")

def remove_from_connected(socket_info):
    global connected_node_address
    ip_address = socket_info.getpeername()[0]
    port_number = socket_info.getpeername()[1]
    formatted_address = f"{ip_address}:{port_number}"
    if formatted_address in connected_node_address:
        connected_node_address.remove(formatted_address)

def list_connections():
    # List all current connections
    global connections
    if not connections:
        print("No active connections")
    else:
        for i, conn in enumerate(connections):
            print("{}: {}:{}".format(i+1, conn.getpeername()[0], conn.getpeername()[1]))
 
def send_search(query):
    # Search for files on the Gnutella network
    global connections, SHARE_PORT, search_results 
    search_results.clear()
    query_str = "SEARCH {}\r\n".format(query)
    query_str += "ADDRESS {}:{}\r\n".format(NODE_PUBLIC_IP, SHARE_PORT)
    for conn in connections:
        conn.sendall(query_str.encode())
    time.sleep(SEARCH_WAIT)
    search_results = list(set(search_results))  #removing duplicates
    list_results(search_results)

    

def response_search(data):
    lines = data.split("\n")
    _, file_name, file_size = lines[0].split(" ")
    address = lines[1].split(" ")
    ip, port = address[1].split(":")
    return (file_name.strip(), file_size.strip(), (ip.strip(), port.strip()))


def list_results(nodes_with_file):
    if not nodes_with_file:
        print("File not found")
        return
    
    for i, (file_name, file_size, address) in enumerate(nodes_with_file):
        print(f"{i+1}. {address[0]}:{address[1]} {file_name} {file_size} bytes")
    choice = input("Enter the number of the node to download from: ")
    try:
        choice_index = int(choice) - 1
        selected_node = nodes_with_file[choice_index]
        ftp_host, ftp_port = selected_node[2][0], selected_node[2][1]
        download(selected_node[0], ftp_host, int(ftp_port))
    except (ValueError, IndexError) as e:
        print("Invalid choice")


def download(file_name, ftp_host=None, ftp_port=None):
    # Download a file from the Gnutella network using FTP
    global connections, DOWNLOADS_FOLDER, file_nodes
    download_path = os.path.join(DOWNLOADS_FOLDER, file_name)
    if not os.path.exists(DOWNLOADS_FOLDER):
        os.makedirs(DOWNLOADS_FOLDER)
    if ftp_host and ftp_port:
        print("Connecting to {}:{}".format(ftp_host, ftp_port))
        with open(download_path, 'wb') as f:
            ftp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ftp_sock.connect((ftp_host, ftp_port))
            ftp_sock.sendall(("RETR {}\r\n".format(file_name)).encode())
            ftp_sock.settimeout(2)  # Set a timeout of 2 seconds on the socket

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
    print("File not found")

 
def help_menu():
    # Show the help message
    print("Commands:")
    print("connect [host] [port] - Connect to a node in the Gnutella network")
    print("disconnect [connection number] - Disconnect from the specified connection or all connections")
    print("list - List all current connections")
    print("search [query] - Search for files on the Gnutella network and then download it")
    print("help - Show this help message")
    print("quit - Quit the client")
    
def prompt_loop():
    # Prompt loop
    while True:
        semaphore.acquire()
        user_input = input("> ").split()
        semaphore.release()
        if not user_input:
            continue
        command = user_input[0]
        args = user_input[1:]
        if command == "connect":
            if len(args)!=2:
                print('Known Nodes:')
                for i, node in enumerate(known_nodes):
                    print(f'{i+1}. {node}')
                print('OR')
                print("Usage: connect [host] [port]")
                choice = input("Enter the number of the node to connect to: ")
                try:
                    choice_index = int(choice) - 1
                    connect(known_nodes[choice_index], CONNECTION_PORT)
                except (ValueError, IndexError) as e:
                    print("Invalid choice")
            else:
                try:
                    host = args[0]
                    port = int(args[1])
                    connect(host, port)
                except ValueError:
                    print("Invalid port number")
        # start listening in a separate thread
        elif command == "disconnect":
            disconnect(args[0] if args else "")
        elif command == "list":
            list_connections()
        elif command == "search":
            #TODO change this
            if len(args) != 1:
                print("Usage: send_search <filename>")
            else:
                print('Searching...')
                send_search(args[0])
        elif command == "help":
            help_menu()
        elif command == "quit":
            for conn in connections:
                conn.close()
                if  conn in connections:
                    connections.remove(conn)
            connected_node_address.clear()
            print("Goodbye!")
            break
        else:
            print("Invalid command. Type 'help' for a list of commands.")

if __name__ == '__main__':
    NODE_PUBLIC_IP = get_public_ip()
    threading.Thread(target=listen, args=(CONNECTION_PORT,), daemon=True).start()  # start listening in a separate thread
    threading.Thread(target=listen, args=(SHARE_PORT,), daemon=True).start()  # start listening in a separate thread
    prompt_loop()
