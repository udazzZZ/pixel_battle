import socket
import pickle
import threading
from threading import Thread
from PyQt6.QtCore import pyqtSignal, QObject, pyqtSlot
from PyQt6.QtWidgets import QApplication, QMainWindow, QColorDialog
from queue import Queue
from registration import Ui_Registration
from choose_room_window import Ui_RoomWindow
from choose_color_window import Ui_ChooseColorWindow

class Communication(QObject):
    free_rooms_updater = pyqtSignal(list)
    chat_updater = pyqtSignal(str)
    color_free = pyqtSignal()
    color_not_free = pyqtSignal(str)

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
        self.color = Color(self.reg_window, self, self.comm, self.client, self.name)

class Color(QMainWindow, Ui_ChooseColorWindow):
    def __init__(self, reg_window, choose_room_window, comm, client, name):
        super().__init__()
        self.reg_window = reg_window
        self.choose_room_window = choose_room_window
        self.comm = comm
        self.client = client
        self.name = name
        self.selected_color = ''
        self.game = None
        self.setupUi(self)

        self.setWindowTitle("Выбор цвета")

        self.button_send.clicked.connect(self.join_game)
        self.pushButton.clicked.connect(self.color_window_open)
        self.button_send.setEnabled(False)

        self.comm.color_free.connect(self.can_join)
        self.comm.color_not_free.connect(self.can_not_join)

        self.show()

    def join_game(self):
        self.game = GameWindow()
        self.client.send_message(dict(data='',
                                      msgtype='ready'))

    def color_window_open(self):
        color = QColorDialog.getColor()
        self.selected_color = color
        self.client.send_message(dict(data=color.name(),
                                      msgtype='color'))
        self.label.setStyleSheet(f"background-color: {color.name()}")

    @pyqtSlot()
    def can_join(self):
        self.button_send.setEnabled(True)

    @pyqtSlot(str)
    def can_not_join(self, message):
        self.choose_room_text.append(message)

class GameWindow:
    pass

def main():
    app = QApplication([])

    start_window = Registration()
    start_window.show()

    app.exec()


if __name__ == "__main__":
    main()