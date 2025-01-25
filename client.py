import socket
import pickle
import threading
import os

from PyQt6.QtCore import pyqtSignal, QObject, pyqtSlot, QRect, Qt
from PyQt6.QtWidgets import (QApplication, QMainWindow,
                             QColorDialog, QPushButton,
                             QWidget, QLabel, QVBoxLayout)
from PyQt6.QtGui import QImage, QPainter, QPixmap
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
    start_game = pyqtSignal(str)
    end_game = pyqtSignal()
    continue_game = pyqtSignal(dict)
    exit_app = pyqtSignal()
    update_timer = pyqtSignal(int)
    exit_color_window = pyqtSignal()

class GameClient:
    def __init__(self, host, port, communication):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((host, port))
        self.isConnected = True
        self.queue = Queue()
        self.comm = communication

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
                        self.comm.start_game.emit(data['data'])

                    case 'continue_game':
                        self.comm.continue_game.emit(data['data'])

                    case 'end_game':
                        self.comm.end_game.emit()

                    case 'color_free':
                        self.comm.color_free.emit()

                    case 'color_not_free':
                        self.comm.color_not_free.emit(data['data'])

                    case 'game':
                        self.comm.game_updater.emit(data['data'])

                    case 'exit_app':
                        self.comm.exit_app.emit()

                    case 'update_timer':
                        self.comm.update_timer.emit(data['data'])

                    case 'exit_color_window':
                        self.comm.exit_color_window.emit()

            except (ConnectionError, OSError):
                print("Вы были отключены от сервера.")
                self.isConnected = False
                self.socket.close()
                break

class Registration(QMainWindow, Ui_Registration):
    def __init__(self):
        super().__init__()
        self.comm = Communication()
        self.client = GameClient('127.0.0.1', 3435, self.comm)
        self.name: str = ''
        self.room: Room | None = None
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
        self.color: Color | None = None
        self.setupUi(self)
        self.setWindowTitle(name)
        self.list_of_rooms.addItems(rooms)
        self.room: str = ''
        self.show()

        self.button_send.clicked.connect(self.room_is_selected)

    def room_is_selected(self):
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
        self.game: GameWindow | None = None
        self.room = room
        self.setupUi(self)

        self.setWindowTitle("Выбор цвета")

        self.button_send.clicked.connect(self.join_game)
        self.pushButton.clicked.connect(self.color_window_open)
        self.button_send.setEnabled(False)

        self.comm.color_free.connect(self.can_join)
        self.comm.color_not_free.connect(self.can_not_join)
        self.comm.exit_color_window.connect(self.exit_color_window)

        self.show()

    def join_game(self):
        self.game = GameWindow(self.choose_room_window,
                               self.comm,
                               self.client,
                               self.name,
                               self.room,
                               self.selected_color)
        self.client.send_message(dict(data='',
                                      msgtype='new_player'))
        self.hide()

    def color_window_open(self):
        color = QColorDialog.getColor()
        self.selected_color = color.name()
        self.client.send_message(dict(data=self.selected_color,
                                      msgtype='color'))
        self.label.setStyleSheet(f"background-color: {color.name()}")

    @pyqtSlot()
    def can_join(self):
        self.choose_room_text.clear()
        self.choose_room_text.append("You can join!")
        self.button_send.setEnabled(True)

    @pyqtSlot(str)
    def can_not_join(self, message):
        self.choose_room_text.clear()
        self.choose_room_text.append(message)
        self.button_send.setEnabled(False)

    @pyqtSlot()
    def exit_color_window(self):
        self.close()

    def closeEvent(self, event):
        self.client.send_message(dict(data='',
                                      msgtype='exit_color_window'))

class GameWindow(QMainWindow, Ui_GameWindow):
    def __init__(self, choose_room_window, comm, client, name, room, color):
        super().__init__()
        self.choose_room_window = choose_room_window
        self.comm = comm
        self.client = client
        self.name = name
        self.room = room
        self.color = color
        self.image_window = None
        self.field_is_empty = True
        self.setupUi(self)

        self.setWindowTitle(f"{self.room}. {self.name}")
        self.textEdit.append('Добро пожаловать в игру!\n'
                             'Условия для начала игры:\n'
                             '1. Количество игроков >= 2\n'
                             '2. Все игроки нажали на кнопку "Ready"\n')
        self.lineEdit.setPlaceholderText("Введите сообщение...")
        self.pushButton.clicked.connect(self.exit)
        self.pushButton_2.clicked.connect(self.send)
        self.pushButton_3.clicked.connect(self.ready)

        self.comm.game_updater.connect(self.update_game)
        self.comm.chat_updater.connect(self.update_chat)
        self.comm.start_game.connect(self.start_game)
        self.comm.end_game.connect(self.end_game)
        self.comm.continue_game.connect(self.continue_game)
        self.comm.exit_app.connect(self.exit_app)
        self.comm.update_timer.connect(self.update_timer)

        self.buttons_map = {}

        for x in range(25):
            for y in range(25):
                cell = QPushButton()
                cell.setMaximumSize(25, 25)
                cell.setMinimumSize(25, 25)
                cell.clicked.connect(lambda clicked, X=x, Y=y: self.game_clicker(X, Y))
                cell.setStyleSheet('background-color: white; border: 1px solid black; padding: 0;')
                cell.setEnabled(False)
                self.gridLayout_3.addWidget(cell, x, y, 1, 1)
                self.buttons_map[(x, y)] = cell

        self.show()

    def ready(self):
        self.client.send_message(dict(data='',
                                      msgtype='ready'))
        self.pushButton_3.setEnabled(False)

    @pyqtSlot(str)
    def start_game(self, message):
        self.textEdit.append(message)
        for x in range(25):
            for y in range(25):
                cell = self.buttons_map[(x, y)]
                cell.setEnabled(True)

    @pyqtSlot(dict)
    def continue_game(self, data):
        self.textEdit.append("Игра уже идет!")

        for (x, y), color in data.items():
            cell = self.buttons_map[(x, y)]
            cell.setStyleSheet(f'background-color: {color}; border: 1px solid black; padding: 0;')
            cell.setEnabled(False)

        for (x, y), cell in self.buttons_map.items():
            if (x, y) not in data:
                cell.setEnabled(True)

    def send(self):
        message = self.lineEdit.text()
        self.client.send_message(dict(data=f'{message}',
                                      msgtype='chat'))
        self.lineEdit.clear()

    def exit(self):
        self.client.send_message(dict(data='',
                                      msgtype='exit'))

    def end_game(self):
        try:
            self.textEdit.append('Игра завершена! Чтобы начать новую игру, все '
                                 'должны быть к ней готовы :)\n')
            path = self.save_field_as_image()
            if path and os.path.exists(path):
                self.image_window = ImageWindow(QPixmap(path), self.name)
            else:
                print("Failed to save or locate the image. No window will be shown.")
            for x in range(25):
                for y in range(25):
                    cell = self.buttons_map[(x, y)]
                    cell.setStyleSheet('background-color: white; border: 1px solid black; padding: 0;')
                    cell.setEnabled(False)
            self.pushButton_3.setEnabled(True)
            self.field_is_empty = True

        except Exception as e:
            print(f"Error in end_game: {e}")

    def game_clicker(self, X, Y):
        self.client.send_message(dict(data=f'{X} {Y} {self.color}',
                                      msgtype='game'))

    @pyqtSlot(int)
    def update_timer(self, new_time):
        self.label.setText(f'You have {new_time} seconds')

    @pyqtSlot(str)
    def update_game(self, coordinates):
        self.field_is_empty = False
        x, y, color = tuple(coordinates.split())
        print(x, y, color)
        cell: QPushButton = self.buttons_map[(int(x), int(y))]
        cell.setStyleSheet(f'background-color: {color}; border: 1px solid black; padding: 0;')
        cell.setEnabled(False)

    @pyqtSlot(str)
    def update_chat(self, message):
        self.textEdit.append(message)

    @pyqtSlot()
    def closeEvent(self, event):
        self.exit()

    @pyqtSlot()
    def exit_app(self):
        self.deleteLater()
        if not self.field_is_empty:
            path = self.save_field_as_image()
            self.image_window = ImageWindow(QPixmap(path), self.name, self.choose_room_window)
        else:
            self.choose_room_window.show()

    def save_field_as_image(self):
        width = 25 * 25
        height = 25 * 25

        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.white)

        painter = QPainter(image)
        for y in range(25):
            for x in range(25):
                cell: QPushButton = self.buttons_map[(x, y)]
                rect = QRect(y * 25, x * 25, 25, 25)
                pixmap = cell.grab()
                painter.drawPixmap(rect, pixmap)
        painter.end()

        image_path = f"{self.name}.png"
        success = image.save(image_path)

        if success:
            return image_path
        else:
            print("Ошибка сохранения изображения.")
            return None


class ImageWindow(QWidget):
    def __init__(self, pixmap: QPixmap, name, next_window=None):
        super().__init__()
        self.next_window = next_window
        self.name = name
        self.setWindowTitle(f"Просмотр изображения: {self.name}")

        self.image_label = QLabel(self)
        self.image_label.setPixmap(pixmap)

        self.image_label.setScaledContents(True)
        self.resize(pixmap.width(), pixmap.height())

        layout = QVBoxLayout()
        layout.addWidget(self.image_label)
        self.setLayout(layout)

        self.show()

    @pyqtSlot()
    def closeEvent(self, event):
        self.deleteLater()
        if self.next_window:
            self.next_window.show()

def main():
    app = QApplication([])

    start_window = Registration()
    start_window.show()

    app.exec()


if __name__ == "__main__":
    main()