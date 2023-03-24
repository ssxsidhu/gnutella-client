import socket
import threading

class ConnectionManager:
    def __init__(self):
        self.connections = []
    
    def add(self, sock):
        self.connections.append(sock)
    
    def remove(self, sock):
        if sock in self.connections:
            sock.close()
            self.connections.remove(sock)
            print(f"Disconnected from {sock.getpeername()}")
    
    def remove_all(self):
        for sock in self.connections:
            sock.close()
        self.connections.clear()
        print("Disconnected from all connections")
    
    def list_connections(self):
        if not self.connections:
            print("No active connections")
        else:
            for i, sock in enumerate(self.connections, start=1):
                print(f"{i}. {sock.getpeername()}")
    
    def send_message(self, message):
        for sock in self.connections:
            sock.sendall(message.encode("utf-8"))

class ConnectionHandler:
    def __init__(self, sock, connection_manager):
        self.sock = sock
        self.connection_manager = connection_manager
    
    def run(self):
        while True:
            try:
                data = self.sock.recv(1024)
                if not data:
                    self.connection_manager.remove(self.sock)
                    break
                # TODO: Implement message handling
                print(f"Received message from {self.sock.getpeername()}: {data.decode('utf-8')}")
            except socket.error:
                self.connection_manager.remove(self.sock)
                break



class GnutellaClient:
    def __init__(self):
        self.connection_manager = ConnectionManager()
        self.server_thread = None
    
    def connect(self, host, port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            print(f"Connected to {host}:{port}")
            self.connection_manager.add(sock)
            return sock
        except socket.gaierror as e:
            print(f"Error connecting to {host}:{port}: {e}")
        except socket.error as e:
            print(f"Error connecting to {host}:{port}: {e}")
        return None
    
    def start_server(self, port):
        self.server_thread = threading.Thread(target=self.accept_connections, args=(port,))
        self.server_thread.start()
        print(f"Started server on port {port}")
    
    def accept_connections(self, port):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind(('', port))
        server_sock.listen()
        while True:
            client_sock, client_addr = server_sock.accept()
            print(f"Accepted connection from {client_addr}")
            self.connection_manager.add(client_sock)
            client_handler = ConnectionHandler(client_sock, self.connection_manager)
            client_thread = threading.Thread(target=client_handler.run)
            client_thread.start()
    
    def disconnect(self, sock=None):
        if sock:
            self.connection_manager.remove(sock)
        else:
            self.connection_manager.list_connections()
            self.connection_manager.remove_all()
    
    def search(self, query):
        message = f"SEARCH {query}\n"
        self.connection_manager.send_message(message)
        print(f"Sent search query '{query}' to {len(self.connection_manager.connections)} connections")
    
    def download(self, file_id):
        message = f"DOWNLOAD {file_id}\n"
        self.connection_manager.send_message(message)
        print(f"Sent download request for file {file_id} to {len(self.connection_manager.connections)} connections")
    
    def help(self):
        print("""
Available commands:
connect <host> <port>: Connect to the Gnutella network
disconnect [connection number]: Disconnect from the Gnutella network
list: List current connections
search <query>: Search for files on the Gnutella network
download <file_id>: Download a file from the Gnutella network
help: Show this help message
quit: Quit the client
""")

if __name__ == "__main__":
    client = GnutellaClient()
    client.start_server(8080)
    client.help()
    while True:
        command = input("> ").strip()
        if command.startswith("connect"):
            args = command.split()[1:]
            if len(args) != 2:
                print("Invalid arguments. Usage: connect <host> <port>")
                continue
            host, port = args
            sock = client.connect(host, int(port))
            if sock:
                client.search("test")
        elif command.startswith("disconnect"):
            if len(command.split()) == 2:
                try:
                    index = int(command.split()[1])
                    sock = client.connection_manager.connections[index-1]
                    client.disconnect(sock)
                except (ValueError, IndexError):
                    print("Invalid connection number")
            else:
                client.disconnect()
        elif command == "list":
            client.connection_manager.list_connections()
        elif command.startswith("search"):
            query = " ".join(command.split()[1:])
            client.search(query)
        elif command.startswith("download"):
            file_id = " ".join(command.split()[1:])
            client.download(file_id)
        elif command == "help":
            client.help()
        elif command == "quit":
            client.disconnect()
            break
        else:
            print("Invalid command. Type 'help' for a list of available commands.")
