import socket
import pickle
import threading
from threading import Thread
from PyQt6.QtCore import pyqtSignal, QObject, pyqtSlot
from PyQt6.QtWidgets import QApplication, QMainWindow, QColorDialog, QPushButton
from queue import Queue
from registration import Ui_Registration
from choose_room_window import Ui_RoomWindow
from choose_color_window import Ui_ChooseColorWindow
from game_room import Ui_GameWindow

class Communication(QObject):
    free_rooms_updater = pyqtSignal(list)
    chat_updater = pyqtSignal(str)
    color_free = pyqtSignal()
    color_not_free = pyqtSignal(str)
    game_updater = pyqtSignal(str)

class GameClient:
    def __init__(self, host, port, communication):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((host, port))
        self.isConnected = True
        self.queue = Queue()
        self.comm = communication
        self.selected_colors = []

        threading.Thread(target=self.receive_messages, daemon=True).start()
        threading.Thread(target=self.send_msg, daemon=True).start()

    def send_msg(self):
        while self.isConnected:
            try:
                msg = self.queue.get(block=True)
                self.socket.send(msg)
            except (ConnectionError, OSError):
                print("Вы были отключены от сервера.")
                self.isConnected = False
                self.socket.close()
                break

    def send_message(self, packet):
        self.queue.put(pickle.dumps(packet), block=False)

    def receive_messages(self):
        while self.isConnected:
            try:
                data_in_bytes = self.socket.recv(1024)

                if not data_in_bytes:
                    break

                data = pickle.loads(data_in_bytes)
                print(data)

                match data['msgtype']:
                    case 'free_rooms':
                        self.comm.free_rooms_updater.emit(data['data'])

                    case 'chat':
                        self.comm.chat_updater.emit(data['data'])

                    case 'start_game':
                        pass

                    case 'continue_game':
                        pass

                    case 'end_game':
                        pass

                    case 'selected_colors':
                        self.selected_colors.append(data['data'])

                    case 'color_free':
                        self.comm.color_free.emit()

                    case 'color_not_free':
                        self.comm.color_not_free.emit(data['data'])

                    case 'game':
                        self.comm.game_updater.emit(data['data'])

            except (ConnectionError, OSError):
                print("Вы были отключены от сервера.")
                self.isConnected = False
                self.socket.close()
                break

class Registration(QMainWindow, Ui_Registration):
    def __init__(self):
        super().__init__()
        self.comm = Communication()
        self.client = GameClient('127.0.0.1', 3434, self.comm)
        self.name: str = ''
        self.room: str = ''
        self.setupUi(self)

        self.reg_input.setPlaceholderText("Введите свое имя...")
        self.setWindowTitle("Регистрация игрока")

        self.send_name_button.clicked.connect(self.send)
        self.comm.free_rooms_updater.connect(self.get_rooms)
        self.show()

    def send(self):
        name = self.reg_input.text()
        self.name = name
        self.client.send_message(dict(data=name,
                                      msgtype='name'))
        self.reg_input.clear()
        self.hide()

    @pyqtSlot(list)
    def get_rooms(self, rooms):
        self.room = Room(self, self.name, self.comm, self.client, rooms)

class Room(QMainWindow, Ui_RoomWindow):
    def __init__(self, reg_window, name, comm, client, rooms):
        super().__init__()
        self.reg_window = reg_window
        self.name = name
        self.comm = comm
        self.client = client
        self.rooms = rooms
        self.color = None
        self.setupUi(self)
        self.setWindowTitle(name)
        self.list_of_rooms.addItems(rooms)
        self.room = ''
        self.show()

        self.button_send.clicked.connect(self.room_is_selected)

    def room_is_selected(self):
        print('комната выбрана')
        self.room = self.list_of_rooms.currentText()
        self.client.send_message(dict(data=self.room,
                                      msgtype='room'))
        self.hide()
        self.color = Color(self.reg_window, self, self.comm, self.client, self.name, self.room)

class Color(QMainWindow, Ui_ChooseColorWindow):
    def __init__(self, reg_window, choose_room_window, comm, client, name, room):
        super().__init__()
        self.reg_window = reg_window
        self.choose_room_window = choose_room_window
        self.comm = comm
        self.client = client
        self.name = name
        self.selected_color = ''
        self.game = None
        self.room = room
        self.setupUi(self)

        self.setWindowTitle("Выбор цвета")

        self.button_send.clicked.connect(self.join_game)
        self.pushButton.clicked.connect(self.color_window_open)
        self.button_send.setEnabled(False)

        self.comm.color_free.connect(self.can_join)
        self.comm.color_not_free.connect(self.can_not_join)

        self.show()

    def join_game(self):
        self.game = GameWindow(self.reg_window,
                               self.choose_room_window,
                               self.comm,
                               self.client,
                               self.name,
                               self.room,
                               self.selected_color)
        self.client.send_message(dict(data='',
                                      msgtype='ready'))
        self.hide()

    def color_window_open(self):
        color = QColorDialog.getColor()
        self.selected_color = color.name()
        print(self.selected_color)
        self.client.send_message(dict(data=self.selected_color,
                                      msgtype='color'))
        self.label.setStyleSheet(f"background-color: {color.name()}")

    @pyqtSlot()
    def can_join(self):
        self.button_send.setEnabled(True)

    @pyqtSlot(str)
    def can_not_join(self, message):
        self.choose_room_text.append(message)

class GameWindow(QMainWindow, Ui_GameWindow):
    def __init__(self, reg_window, choose_room_window, comm, client, name, room, color):
        super().__init__()
        self.reg_window = reg_window
        self.choose_room_window = choose_room_window
        self.comm = comm
        self.client = client
        self.name = name
        self.room = room
        self.color = color
        self.setupUi(self)

        self.setWindowTitle(f"{self.room}. {self.name}.")
        self.lineEdit.setPlaceholderText("Введите сообщение...")
        self.pushButton.clicked.connect(self.exit)
        self.pushButton_2.clicked.connect(self.send)

        self.comm.game_updater.connect(self.update_game)

        self.buttons_map = {}

        for x in range(30):
            for y in range(30):
                cell = QPushButton()
                cell.setMaximumSize(25, 25)
                cell.setMinimumSize(25, 25)
                cell.clicked.connect(lambda clicked, X=x, Y=y: self.game_clicker(X, Y))
                cell.setStyleSheet('background-color: white; border: 1px solid black;')
                self.gridLayout.addWidget(cell, x, y, 1, 1)
                self.buttons_map[(x, y)] = cell

        self.show()

    def send(self):
        message = self.lineEdit.text()
        self.client.send_message(dict(data='',
                                      msgtype='chat'))
        self.lineEdit.clear()

    def exit(self):
        self.client.send_message(dict(data='',
                                      msgtype='exit'))

    def game_clicker(self, X, Y):
        self.client.send_message(dict(data=f'{X} {Y}',
                                      msgtype='game'))

    def update_game(self, coordinates):
        coords = coordinates.split()
        print(coords)
        x = int(coords[0])
        y = int(coords[1])
        cell: QPushButton = self.buttons_map[(x, y)]
        cell.setStyleSheet(f'background-color: {self.color}]; border: 1px solid black;')
        cell.setEnabled(False)

def main():
    app = QApplication([])

    start_window = Registration()
    start_window.show()

    app.exec()


if __name__ == "__main__":
    main()