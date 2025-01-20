import socket
from threading import Thread
import pickle

class GameRoom:
    def __init__(self, free, name):
        self.is_active: bool = False
        self.name: str = name
        self.clients: list = []
        self.ready_clients_count = 0
        self.clients_names: list = []
        self.colors = []

    def broadcast(self, packet, except_client=None):
        for client in self.clients:
            if client != except_client:
                client.send(pickle.dumps(packet))

    def start_game(self):
        self.broadcast(dict(data="Игра началась.",
                            msgtype='start_game'))

    def continue_game(self):
        pass

    def exit_room(self, client, client_name, reason=None):
        client_idx = self.clients.index(client)
        self.clients.pop(client_idx)
        self.clients_names.pop(client_idx)
        self.ready_clients_count -= 1
        self.colors.pop(client_idx)
        self.broadcast(dict(data=f"Игрок {client_name} покинул игру.",
                            msgtype='chat'),
                       client)
        if len(self.clients) == 1:
            self.end_game()

    def end_game(self):
        self.broadcast(dict(data="Время вышло. Игра завершена.\n"
                                 "Итоговое изображение уже у вас.",
                            msgtype='chat'))
        self.broadcast(dict(data="",
                            msgtype='end_game'))
        self.is_active = False

class GameServer:
    def __init__(self, host, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((host, port))
        self.socket.listen(5)
        self.is_server_active: bool = True
        self.rooms = [GameRoom(True, 'Room1'),
                      GameRoom(True, 'Room2'),
                      GameRoom(True, 'Room3')]
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
                        print('Комната получена'.format(data['data']))
                        self.join_room(data['data'])

                    case 'color':
                        self.color = data['data']
                        self.check_color(self.color)

                    case 'ready':
                        self.room.broadcast(dict(data=f'Игрок {self.name} присоединился к комнате.',
                                                 msgtype='chat'),
                                            self.client)
                        self.room.ready_clients_count += 1
                        if self.room.ready_clients_count == 2:
                            self.room.start_game()
                            print('Начинаем игру')
                        elif self.room.ready_clients_count > 2:
                            self.room.continue_game()

                    case 'exit':
                        self.exit_game(self.room, self.client, self.name)

            except (ConnectionError, OSError):
                print(f"Игрок {self.name} отключился.")
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
        print(color)
        if color not in self.room.colors:
            self.room.colors.append(color)
            self.client.send(pickle.dumps(dict(data='',
                                               msgtype='color_free')))
        else:
            self.color = ''
            self.client.send(pickle.dumps(dict(data='Цвет уже занят',
                                               msgtype='color_not_free')))

    def exit_game(self, room, player, name):
        packet = dict(data=f"Игрок {name} покинул игру. ",
                      msgtype='chat')
        room.broadcast(packet, player)
        print(f"{name} disconnected")
        cur_player_idx = room.clients.index(player)
        room.clients.pop(cur_player_idx)
        room.clients_names.pop(cur_player_idx)
        room.ready_clients_count -= 1
        room.colors.pop(cur_player_idx)
        self.client.send(pickle.dumps(dict(data='',
                                           msgtype='end_game')))

def main():
    game_server = GameServer('127.0.0.1', port=3434)
    game_server.start()


if __name__ == "__main__":
    main()