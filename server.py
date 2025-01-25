import socket
import threading
from threading import Thread
import pickle
import time

class GameRoom:
    def __init__(self, name):
        self.is_active: bool = False
        self.name: str = name
        self.clients: list = []
        self.ready_clients_count = 0
        self.clients_names: list = []
        self.colors = []
        self.game_timer = None
        self.timer_is_active = False

        self.game_state = {}

    def broadcast(self, packet, except_client=None):
        for client in self.clients:
            if client != except_client:
                client.send(pickle.dumps(packet))

    def start_game(self, client):
        if self.game_timer:
            client.send(pickle.dumps(dict(data=self.game_state,
                                          msgtype='continue_game')))

        else:
            self.broadcast(dict(data="Игра началась! У вас есть 1 минута.\n",
                                msgtype='start_game'))
            self.timer_is_active = True
            self.game_timer = threading.Thread(target=self.start_timer, args=(60,))
            self.game_timer.start()

    def start_timer(self, duration):
        start_time = time.time()
        while self.timer_is_active and time.time() - start_time < duration + 1:
            update_time = duration - int(time.time() - start_time)
            self.broadcast(dict(data=update_time,
                                msgtype='update_timer'))
            time.sleep(1)

        if len(self.clients) > 1:
            self.broadcast(dict(data="Время вышло.\n",
                                msgtype='chat'))
        self.broadcast(dict(data="",
                            msgtype="end_game"))
        self.end_game()

    def exit_color_window(self, client, client_name):
        client_idx = self.clients.index(client)
        if len(self.colors) == len(self.clients):
            self.colors.pop(client_idx)
        self.clients.pop(client_idx)
        self.clients_names.pop(client_idx)
        self.broadcast(dict(data=f"Игрок {client_name} покинул комнату.\n",
                            msgtype='chat'),
                       client)
        client.send(pickle.dumps(dict(data='',
                                      msgtype='exit_color_window')))

    def exit_room(self, client, client_name):
        client_idx = self.clients.index(client)
        self.clients.pop(client_idx)
        self.clients_names.pop(client_idx)
        if self.ready_clients_count != 0:
            self.ready_clients_count -= 1
        self.colors.pop(client_idx)
        self.broadcast(dict(data=f"Игрок {client_name} покинул игру.\n",
                            msgtype='chat'),
                       client)
        client.send(pickle.dumps(dict(data='',
                                      msgtype='exit_app')))
        if len(self.clients) == 1:
            self.timer_is_active = False

    def end_game(self):
        self.broadcast(dict(data=60,
                            msgtype='update_timer'))
        self.is_active = False
        self.game_state = {}
        self.timer_is_active = False
        self.game_timer = None
        self.ready_clients_count = 0

class GameServer:
    def __init__(self, host, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((host, port))
        self.socket.listen(5)
        self.is_server_active: bool = True
        self.rooms = [GameRoom('Room1'),
                      GameRoom('Room2'),
                      GameRoom('Room3')]
        self.package_template = {'data': '', 'msgtype': ''}

    def start(self):
        print("Ожидание подключение игроков...")
        while self.is_server_active:
            client_socket, client_address = self.socket.accept()
            print(f'Подключен {client_address}')
            ClientHandler(client_socket, self.rooms)

class ClientHandler(Thread):
    def __init__(self, client, rooms):
        super().__init__()
        self.client = client
        self.rooms = rooms
        self.room: GameRoom | None = None
        self.name: str = ''
        self.color: str = ''

        self.start()

    def run(self):
        while True:
            try:
                data_in_bytes = self.client.recv(1024)

                if not data_in_bytes:
                    break

                data = pickle.loads(data_in_bytes)

                match data['msgtype']:
                    case 'name':
                        self.name = data['data']

                        free_rooms = self.get_free_rooms()
                        free_rooms_names = []
                        for room in free_rooms:
                            free_rooms_names.append(room.name)

                        self.client.send(pickle.dumps(dict(data=free_rooms_names,
                                                           msgtype='free_rooms')))

                    case 'room':
                        self.join_room(data['data'])

                    case 'color':
                        self.color = data['data']
                        self.check_color(self.color)

                    case 'new_player':
                        self.room.colors.append(self.color)
                        self.room.broadcast(dict(data=f'Игрок {self.name} присоединился к комнате.\n',
                                                 msgtype='chat'),
                                            self.client)

                    case 'ready':
                        self.room.broadcast(dict(data=f'Игрок {self.name} готов к игре.\n',
                                                 msgtype='chat'))
                        self.room.ready_clients_count += 1
                        if not self.room.is_active:
                            if (self.room.ready_clients_count == len(self.room.clients) and
                                    self.room.ready_clients_count > 1):
                                self.room.start_game(self.client)
                                self.room.is_active = True
                        else:
                            self.room.start_game(self.client)

                    case 'exit':
                        self.room.exit_room(self.client, self.name)

                    case 'game':
                        x, y, color = tuple(data['data'].split())
                        self.room.game_state[(int(x), int(y))] = color
                        self.room.broadcast(dict(data='{}'.format(data['data']),
                                                 msgtype='game'))

                    case 'chat':
                        message = data['data']
                        self.room.broadcast(dict(data=f'{self.name}: {message}',
                                                 msgtype='chat'),
                                            self.client)
                        self.client.send(pickle.dumps(dict(data=f'You: {message}',
                                                           msgtype='chat')))

                    case 'exit_color_window':
                        self.room.exit_color_window(self.client, self.name)

            except (ConnectionError, OSError):
                print(f"Игрок {self.name} отключился.")
                print(self.room.clients)
                break

    def get_free_rooms(self):
        free_rooms = []
        rooms = self.rooms
        for room in rooms:
            free_rooms.append(room)

        return free_rooms

    def join_room(self, room_name):
        for room in self.rooms:
            if room.name == room_name:
                print(f'Игрок {self.name} подключился к комнате')
                self.room = room
                room.clients.append(self.client)
                room.clients_names.append(self.name)
                break

    def check_color(self, color):
        if color not in self.room.colors:
            self.client.send(pickle.dumps(dict(data='',
                                               msgtype='color_free')))
        else:
            self.color = ''
            self.client.send(pickle.dumps(dict(data='Цвет уже занят',
                                               msgtype='color_not_free')))

def main():
    game_server = GameServer('127.0.0.1', port=3435)
    game_server.start()


if __name__ == "__main__":
    main()