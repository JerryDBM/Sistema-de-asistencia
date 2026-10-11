import sys
import csv
from datetime import datetime
from PySide6.QtCore import Qt, QTime
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QComboBox, QSpinBox, QTimeEdit, QMessageBox, QAbstractItemView,
    QFileDialog, QStackedWidget
)


class AttendanceApp(QMainWindow):
    """
    Prototipo de interfaz PySide6 para AulaCheck.
    Los datos de estudiantes/clases son de demostración: todavía no consulta MySQL
    ni activa físicamente el ESP32-CAM.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AulaCheck | Sistema de asistencia académica")
        self.resize(1360, 860)
        self.setMinimumSize(1120, 720)
        self.session_active = False
        self.next_nrc = 10002

        # Simulación de la tabla ESTUDIANTES de MySQL.
        # En la versión conectada, esta consulta se hará a través de FastAPI.
        self.student_registry = {
            "ana.martinez@utb.edu.co": {"name": "Ana Martínez", "email": "ana.martinez@utb.edu.co", "nrcs": []},
            "carlos.perez@utb.edu.co": {"name": "Carlos Pérez", "email": "carlos.perez@utb.edu.co", "nrcs": []},
            "laura.gomez@utb.edu.co": {"name": "Laura Gómez", "email": "laura.gomez@utb.edu.co", "nrcs": []},
            "andres.torres@utb.edu.co": {"name": "Andrés Torres", "email": "andres.torres@utb.edu.co", "nrcs": []},
            "valentina.ruiz@utb.edu.co": {"name": "Valentina Ruiz", "email": "valentina.ruiz@utb.edu.co", "nrcs": []},
            "daniel.herrera@utb.edu.co": {"name": "Daniel Herrera", "email": "daniel.herrera@utb.edu.co", "nrcs": []},
            "sofia.castro@utb.edu.co": {"name": "Sofía Castro", "email": "sofia.castro@utb.edu.co", "nrcs": []},
            "mateo.diaz@utb.edu.co": {"name": "Mateo Díaz", "email": "mateo.diaz@utb.edu.co", "nrcs": []},
        }

        self.classes = [{
            "nrc": "10001",
            "name": "Computación e Interfaces",
            "start": "08:00",
            "tolerance": 10,
            "students": [
                "ana.martinez@utb.edu.co",
                "carlos.perez@utb.edu.co",
                "laura.gomez@utb.edu.co",
                "andres.torres@utb.edu.co",
                "valentina.ruiz@utb.edu.co",
                "daniel.herrera@utb.edu.co",
                "sofia.castro@utb.edu.co",
                "mateo.diaz@utb.edu.co",
            ],
        }]
        self.current_class = 0
        for c in self.classes:
            for email in c["students"]:
                if email in self.student_registry and c["nrc"] not in self.student_registry[email]["nrcs"]:
                    self.student_registry[email]["nrcs"].append(c["nrc"])
        self.students = []
        self.load_roster_for_current_class()

        self.setStyleSheet("""
            QMainWindow, QWidget { background:#F4F7FB; color:#172033; font-family:'Segoe UI'; }
            QFrame#Sidebar { background:#152238; border-radius:16px; }
            QLabel#Brand { color:white; font-size:23px; font-weight:800; }
            QLabel#SideCaption { color:#9FAFC6; font-size:10px; font-weight:800; }
            QPushButton#Nav { text-align:left; color:#D8E1EF; background:transparent; border:none;
                padding:12px 13px; border-radius:9px; font-size:13px; }
            QPushButton#Nav:hover, QPushButton#Nav:checked { background:#263B59; color:white; }
            QLabel#PageTitle { font-size:27px; font-weight:800; color:#172033; }
            QLabel#Muted { color:#6B778C; font-size:12px; }
            QFrame#Card, QFrame#Panel { background:white; border:1px solid #E5EAF2; border-radius:14px; }
            QLabel#MetricTitle { color:#6B778C; font-size:12px; }
            QLabel#MetricValue { color:#172033; font-size:27px; font-weight:800; }
            QPushButton#Primary { background:#3867E8; color:white; border:none; border-radius:8px;
                padding:10px 14px; font-weight:700; }
            QPushButton#Primary:hover { background:#2C54C5; }
            QPushButton#Secondary { background:#EAF0FF; color:#315BD0; border:none; border-radius:8px;
                padding:9px 12px; font-weight:700; }
            QPushButton#Danger { background:#FCE8E7; color:#B42318; border:none; border-radius:8px;
                padding:10px 13px; font-weight:700; }
            QPushButton#Success { background:#DDF7E8; color:#18794E; border:none; border-radius:8px;
                padding:10px 13px; font-weight:700; }
            QPushButton#Running { background:#18794E; color:white; border:none; border-radius:8px;
                padding:10px 13px; font-weight:700; }
            QLineEdit, QComboBox, QSpinBox, QTimeEdit {
                background:white; border:1px solid #D8DFEA; border-radius:7px; padding:8px; min-height:18px;
            }
            QTableWidget { background:white; border:1px solid #D9E0EA; gridline-color:#D9E0EA;
                selection-background-color:#E8EEFF; selection-color:#172033; }
            QHeaderView::section { background:#F7F9FC; color:#53627A; border:1px solid #D9E0EA;
                padding:11px; font-weight:700; }
        """)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(18)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(228)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 22, 16, 18)
        side.setSpacing(8)
        brand = QLabel("◈ AulaCheck")
        brand.setObjectName("Brand")
        side.addWidget(brand)
        tagline = QLabel("ASISTENCIA ACADÉMICA")
        tagline.setObjectName("SideCaption")
        side.addWidget(tagline)
        side.addSpacing(20)
        side.addWidget(self.section_label("MENÚ PRINCIPAL"))

        self.nav_buttons = []
        nav_items = [
            ("▦   Panel de asistencia", 0),
            ("▣   Gestión de clases", 1),
            ("◷   Historial", 2),
            ("ⓘ   Acerca de", 3),
        ]
        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("Nav")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, i=index: self.navigate(i))
            side.addWidget(btn)
            self.nav_buttons.append(btn)
        self.nav_buttons[0].setChecked(True)
        side.addStretch()

        device = QFrame()
        device.setStyleSheet("QFrame {background:#203550; border-radius:11px;}")
        dv = QVBoxLayout(device)
        dv.setContentsMargins(12, 12, 12, 12)
        d1 = QLabel("ESTACIÓN DE LECTURA")
        d1.setStyleSheet("color:#9FAFC6;font-size:10px;font-weight:800;")
        self.device_status = QLabel("●  ESP32-CAM en espera")
        self.device_status.setStyleSheet("color:#F6D98B;font-size:12px;font-weight:700;")
        d2 = QLabel("Estado de demostración")
        d2.setStyleSheet("color:#D8E1EF;font-size:11px;")
        dv.addWidget(d1)
        dv.addWidget(self.device_status)
        dv.addWidget(d2)
        side.addWidget(device)

        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(14)
        self.stack = QStackedWidget()
        self.pages = [
            self.build_dashboard(),
            self.build_classes_page(),
            self.build_history_page(),
            self.build_about_page(),
        ]
        for page in self.pages:
            self.stack.addWidget(page)
        main_layout.addWidget(self.stack)
        root_layout.addWidget(sidebar)
        root_layout.addWidget(main_area, 1)
        self.setCentralWidget(root)

        self.refresh_attendance_table()
        self.refresh_class_table()
        self.refresh_history_table()
        self.refresh_class_roster_table()

    def label(self, text, name=None):
        l = QLabel(text)
        if name:
            l.setObjectName(name)
        return l

    def section_label(self, text):
        l = QLabel(text)
        l.setStyleSheet("font-size:11px;font-weight:800;color:#6B778C;letter-spacing:1px;")
        return l

    def panel(self):
        f = QFrame()
        f.setObjectName("Panel")
        return f

    def page_header(self, title, subtitle):
        row = QHBoxLayout()
        col = QVBoxLayout()
        t = QLabel(title)
        t.setObjectName("PageTitle")
        s = QLabel(subtitle)
        s.setObjectName("Muted")
        col.addWidget(t)
        col.addWidget(s)
        row.addLayout(col)
        row.addStretch()
        row.addWidget(QLabel(datetime.now().strftime("%d/%m/%Y")))
        return row

    def metric_card(self, title, value):
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(15, 13, 15, 13)
        t = QLabel(title)
        t.setObjectName("MetricTitle")
        v = QLabel(str(value))
        v.setObjectName("MetricValue")
        lay.addWidget(t)
        lay.addWidget(v)
        card.value_label = v
        return card

    def setup_table(self, table):
        table.setShowGrid(True)
        table.setGridStyle(Qt.SolidLine)
        table.setAlternatingRowColors(False)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setWordWrap(False)

    def build_dashboard(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(self.page_header("Panel de asistencia", "Administra la sesión y consulta el estado de cada estudiante."))

        config = self.panel()
        cg = QGridLayout(config)
        cg.setContentsMargins(16, 13, 16, 13)
        cg.setSpacing(10)
        cg.addWidget(self.section_label("INFORMACIÓN DE LA CLASE"), 0, 0, 1, 5)
        self.course_combo = QComboBox()
        self.update_course_combo()
        self.course_combo.currentIndexChanged.connect(self.change_current_class)
        self.start_time_label = QLabel(self.classes[self.current_class]["start"])
        self.start_time_label.setStyleSheet("font-size:14px;font-weight:700;color:#344054;padding:7px;")
        self.start_time_label.setToolTip("La hora de inicio se define en Gestión de clases y no se modifica desde este panel.")
        self.tolerance = QSpinBox()
        self.tolerance.setRange(0, 180)
        self.tolerance.setValue(self.classes[self.current_class]["tolerance"])
        self.tolerance.setSuffix(" min")
        cg.addWidget(QLabel("Asignatura"), 1, 0)
        cg.addWidget(self.course_combo, 2, 0, 1, 2)
        cg.addWidget(QLabel("Hora de inicio (solo lectura)"), 1, 2)
        cg.addWidget(self.start_time_label, 2, 2)
        cg.addWidget(QLabel("Tolerancia ajustable"), 1, 3)
        cg.addWidget(self.tolerance, 2, 3)
        self.save_config_btn = QPushButton("Guardar tolerancia")
        self.save_config_btn.setObjectName("Secondary")
        self.save_config_btn.clicked.connect(self.save_current_config)
        cg.addWidget(self.save_config_btn, 2, 4)
        layout.addWidget(config)

        cards = QHBoxLayout()
        self.metric_total = self.metric_card("Estudiantes de la clase", len(self.students))
        self.metric_present = self.metric_card("Asistencia válida", 0)
        self.metric_late = self.metric_card("No válidas / sin registrar", 0)
        self.metric_pending = self.metric_card("Pendientes", len(self.students))
        for c in [self.metric_total, self.metric_present, self.metric_late, self.metric_pending]:
            cards.addWidget(c)
        layout.addLayout(cards)

        table_panel = self.panel()
        tp = QVBoxLayout(table_panel)
        tp.setContentsMargins(15, 13, 15, 14)
        header = QHBoxLayout()
        header.addWidget(self.section_label("LISTA DE ASISTENCIA"))
        header.addStretch()
        self.search_attendance = QLineEdit()
        self.search_attendance.setPlaceholderText("Buscar estudiante...")
        self.search_attendance.setMaximumWidth(220)
        self.search_attendance.textChanged.connect(self.filter_attendance)
        header.addWidget(self.search_attendance)
        tp.addLayout(header)

        self.attendance_table = QTableWidget(0, 4)
        self.attendance_table.setHorizontalHeaderLabels(["Nombre del estudiante", "Correo institucional", "Hora de registro", "Estado"])
        self.attendance_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.attendance_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.attendance_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.attendance_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.setup_table(self.attendance_table)
        tp.addWidget(self.attendance_table, 1)

        actions = QHBoxLayout()
        self.session_label = QLabel("● Sesión no iniciada")
        self.session_label.setStyleSheet("color:#6B778C;font-weight:700;")
        actions.addWidget(self.session_label)
        actions.addStretch()
        self.start_btn = QPushButton("▶  Iniciar asistencia")
        self.start_btn.setObjectName("Success")
        self.start_btn.clicked.connect(self.start_session)
        self.finish_btn = QPushButton("■  Finalizar clase")
        self.finish_btn.setObjectName("Danger")
        self.finish_btn.clicked.connect(self.finish_session)
        self.finish_btn.setEnabled(False)
        self.manual_btn = QPushButton("＋ Añadir asistencia")
        self.manual_btn.setObjectName("Secondary")
        self.manual_btn.clicked.connect(self.manual_attendance)
        self.export_btn = QPushButton("⇩  Guardar / exportar")
        self.export_btn.setObjectName("Primary")
        self.export_btn.clicked.connect(self.export_attendance)
        for b in [self.start_btn, self.finish_btn, self.manual_btn, self.export_btn]:
            actions.addWidget(b)
        tp.addLayout(actions)
        layout.addWidget(table_panel, 1)
        return page

    def build_classes_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(self.page_header("Gestión de clases", "Crea clases con NRC y administra los estudiantes vinculados por correo institucional."))

        form = self.panel()
        grid = QGridLayout(form)
        grid.setContentsMargins(18, 18, 18, 18)
        grid.setSpacing(10)
        grid.addWidget(self.section_label("CREAR NUEVA CLASE"), 0, 0, 1, 4)
        self.new_class_name = QLineEdit()
        self.new_class_name.setPlaceholderText("Ej. Computación e Interfaces")
        self.new_class_start = QTimeEdit()
        self.new_class_start.setDisplayFormat("HH:mm")
        self.new_class_start.setTime(QTime(8, 0))
        self.new_class_tolerance = QSpinBox()
        self.new_class_tolerance.setRange(0, 180)
        self.new_class_tolerance.setValue(10)
        self.new_class_tolerance.setSuffix(" min")
        grid.addWidget(QLabel("Nombre de la clase"), 1, 0)
        grid.addWidget(self.new_class_name, 2, 0, 1, 2)
        grid.addWidget(QLabel("Hora de inicio"), 1, 2)
        grid.addWidget(self.new_class_start, 2, 2)
        grid.addWidget(QLabel("Tolerancia inicial"), 1, 3)
        grid.addWidget(self.new_class_tolerance, 2, 3)
        add = QPushButton("Crear clase y generar NRC")
        add.setObjectName("Primary")
        add.clicked.connect(self.add_class)
        grid.addWidget(add, 2, 4)
        layout.addWidget(form)

        classes_panel = self.panel()
        cl = QVBoxLayout(classes_panel)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.addWidget(self.section_label("CLASES REGISTRADAS — SELECCIONA UNA PARA ADMINISTRAR SU LISTA"))
        self.classes_table = QTableWidget(0, 5)
        self.classes_table.setHorizontalHeaderLabels(["NRC", "Asignatura", "Hora de inicio", "Tolerancia", "Estudiantes"])
        self.classes_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.classes_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for i in [2, 3, 4]:
            self.classes_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.setup_table(self.classes_table)
        self.classes_table.itemSelectionChanged.connect(self.on_class_selected)
        self.classes_table.cellDoubleClicked.connect(lambda row, col: self.on_class_selected())
        cl.addWidget(self.classes_table)
        layout.addWidget(classes_panel, 1)

        roster_panel = self.panel()
        rl = QVBoxLayout(roster_panel)
        rl.setContentsMargins(16, 14, 16, 14)
        self.selected_class_heading = QLabel("Estudiantes vinculados a la clase seleccionada")
        self.selected_class_heading.setStyleSheet("font-size:15px;font-weight:800;color:#17365D;")
        rl.addWidget(self.selected_class_heading)
        note = QLabel("Escribe el correo institucional. El prototipo lo busca en un registro simulado de estudiantes; si existe, lo vincula al NRC seleccionado.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        rl.addWidget(note)
        addrow = QHBoxLayout()
        self.student_email_input = QLineEdit()
        self.student_email_input.setPlaceholderText("nombre.apellido@utb.edu.co")
        self.student_email_input.returnPressed.connect(self.add_student_to_class)
        self.add_student_btn = QPushButton("＋ Añadir por correo")
        self.add_student_btn.setObjectName("Secondary")
        self.add_student_btn.clicked.connect(self.add_student_to_class)
        addrow.addWidget(self.student_email_input, 1)
        addrow.addWidget(self.add_student_btn)
        rl.addLayout(addrow)
        self.class_roster_table = QTableWidget(0, 2)
        self.class_roster_table.setHorizontalHeaderLabels(["Nombre del estudiante", "Correo institucional"])
        self.class_roster_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.class_roster_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setup_table(self.class_roster_table)
        rl.addWidget(self.class_roster_table)
        layout.addWidget(roster_panel, 1)
        return page

    def build_history_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(self.page_header("Historial de asistencia", "Vista demostrativa de sesiones y registros anteriores."))
        panel = self.panel()
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(16, 16, 16, 16)
        pl.addWidget(self.section_label("REGISTROS RECIENTES"))
        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(["NRC / Clase", "Fecha", "Estudiantes registrados", "Estado"])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 4):
            self.history_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.setup_table(self.history_table)
        pl.addWidget(self.history_table)
        info = QLabel("Datos ilustrativos. Al conectar FastAPI y MySQL, aquí se consultarán las sesiones guardadas.")
        info.setObjectName("Muted")
        pl.addWidget(info)
        layout.addWidget(panel, 1)
        return page

    def build_about_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(self.page_header("Acerca del proyecto", "Quiénes somos, qué hacemos y qué valor aportamos."))
        panel = self.panel()
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(26, 24, 26, 24)
        pl.setSpacing(12)
        title = QLabel("AulaCheck · Asistencia académica mediante QR dinámicos")
        title.setStyleSheet("font-size:20px;font-weight:800;color:#17365D;")
        pl.addWidget(title)
        desc = QLabel(
            "Somos un equipo de estudiantes que integra programación, interfaces y electrónica para facilitar "
            "el registro de asistencia. La propuesta combina Flutter para mostrar el QR dinámico, ESP32-CAM "
            "para capturarlo, FastAPI para validar la solicitud, MySQL para almacenar los datos y PySide6 "
            "para que el profesor gestione las clases y consulte los resultados."
        )
        desc.setWordWrap(True)
        pl.addWidget(desc)
        pl.addWidget(self.section_label("¿QUÉ APORTAMOS?"))
        value = QLabel(
            "Buscamos reducir tareas manuales, centralizar los registros y dar retroalimentación al estudiante "
            "y al profesor. El sistema considera la identidad, la vigencia del token, el NRC de la clase y la "
            "tolerancia configurada."
        )
        value.setWordWrap(True)
        pl.addWidget(value)
        pl.addWidget(self.section_label("INTEGRANTES"))
        for name in ["Fredy Jarava Chavez", "Jerry Buelvas Mejia", "Juan Caicedo Gomez", "Rafael Villero Castillo"]:
            pl.addWidget(QLabel("•  " + name))
        pl.addStretch()
        layout.addWidget(panel, 1)
        return page

    def update_course_combo(self):
        if not hasattr(self, "course_combo"):
            return
        self.course_combo.blockSignals(True)
        self.course_combo.clear()
        for c in self.classes:
            self.course_combo.addItem(f'{c["name"]} · NRC {c["nrc"]}')
        if self.classes:
            self.course_combo.setCurrentIndex(min(self.current_class, len(self.classes) - 1))
        self.course_combo.blockSignals(False)

    def load_roster_for_current_class(self):
        if not self.classes:
            self.students = []
            return
        c = self.classes[self.current_class]
        self.students = []
        for email in c["students"]:
            profile = self.student_registry.get(email.lower())
            if profile:
                self.students.append({
                    "name": profile["name"],
                    "email": profile["email"],
                    "time": "—",
                    "status": "Pendiente",
                })

    def navigate(self, index):
        if self.session_active and index == 1:
            QMessageBox.information(self, "Sesión activa", "Finaliza la sesión antes de cambiar la configuración de clases.")
            return
        self.stack.setCurrentIndex(index)
        for i, b in enumerate(self.nav_buttons):
            b.setChecked(i == index)
        if index == 0:
            self.refresh_attendance_table()
        elif index == 1:
            self.refresh_class_table()
            self.refresh_class_roster_table()
        elif index == 2:
            self.refresh_history_table()

    def change_current_class(self, index):
        if index < 0 or index >= len(self.classes):
            return
        if self.session_active:
            QMessageBox.warning(self, "Sesión activa", "Finaliza la sesión antes de cambiar de clase.")
            self.course_combo.blockSignals(True)
            self.course_combo.setCurrentIndex(self.current_class)
            self.course_combo.blockSignals(False)
            return
        self.current_class = index
        c = self.classes[index]
        self.start_time_label.setText(c["start"])
        self.tolerance.setValue(c["tolerance"])
        self.load_roster_for_current_class()
        self.refresh_attendance_table()
        self.refresh_class_table()
        self.refresh_class_roster_table()
        self.refresh_history_table()

    def save_current_config(self):
        c = self.classes[self.current_class]
        c["tolerance"] = self.tolerance.value()
        self.refresh_class_table()
        QMessageBox.information(
            self, "Tolerancia guardada",
            f'Se actualizó la tolerancia de «{c["name"]}» (NRC {c["nrc"]}) a {c["tolerance"]} minutos.\n'
            "La hora de inicio no se puede cambiar desde el panel de asistencia."
        )

    def add_class(self):
        name = self.new_class_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Falta el nombre", "Escribe el nombre de la clase.")
            return
        if any(c["name"].lower() == name.lower() for c in self.classes):
            QMessageBox.warning(self, "Clase existente", "Ya hay una clase con ese nombre.")
            return
        nrc = str(self.next_nrc)
        self.next_nrc += 1
        new_class = {
            "nrc": nrc,
            "name": name,
            "start": self.new_class_start.time().toString("HH:mm"),
            "tolerance": self.new_class_tolerance.value(),
            "students": [],
        }
        self.classes.append(new_class)
        self.current_class = len(self.classes) - 1
        self.update_course_combo()
        self.new_class_name.clear()
        self.refresh_class_table()
        self.refresh_class_roster_table()
        QMessageBox.information(
            self, "Clase creada",
            f'La clase «{name}» fue creada con NRC {nrc}.\nLa lista está vacía y ya puedes añadir estudiantes por correo institucional.'
        )

    def refresh_class_table(self):
        if not hasattr(self, "classes_table"):
            return
        self.classes_table.setRowCount(len(self.classes))
        for r, c in enumerate(self.classes):
            vals = [c["nrc"], c["name"], c["start"], f'{c["tolerance"]} min', str(len(c["students"]))]
            for col, val in enumerate(vals):
                self.classes_table.setItem(r, col, QTableWidgetItem(val))
        if self.classes:
            self.classes_table.selectRow(self.current_class)

    def on_class_selected(self):
        row = self.classes_table.currentRow()
        if row < 0 or row >= len(self.classes):
            return
        self.current_class = row
        c = self.classes[row]
        self.selected_class_heading.setText(f'Estudiantes vinculados · {c["name"]} · NRC {c["nrc"]}')
        self.refresh_class_roster_table()

    def add_student_to_class(self):
        row = self.classes_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selecciona una clase", "Selecciona primero la clase a la que quieres añadir el estudiante.")
            return
        c = self.classes[row]
        email = self.student_email_input.text().strip().lower()
        if not email or "@" not in email:
            QMessageBox.warning(self, "Correo inválido", "Escribe un correo institucional válido.")
            return
        # Simula una consulta SELECT a la tabla ESTUDIANTES por correo institucional.
        profile = self.student_registry.get(email)
        if profile is None:
            QMessageBox.warning(
                self, "Estudiante no encontrado",
                "Ese correo no existe en el registro de estudiantes de demostración.\n"
                "En la versión final, FastAPI consultará la tabla ESTUDIANTES de MySQL."
            )
            return
        if email in c["students"]:
            QMessageBox.information(self, "Ya está vinculado", "Este estudiante ya pertenece a la clase seleccionada.")
            return
        c["students"].append(email)
        if c["nrc"] not in profile["nrcs"]:
            profile["nrcs"].append(c["nrc"])
        self.student_email_input.clear()
        self.refresh_class_table()
        self.refresh_class_roster_table()
        if row == self.current_class:
            self.load_roster_for_current_class()
            self.refresh_attendance_table()
        QMessageBox.information(
            self, "Estudiante añadido",
            f'{profile["name"]} fue vinculado a «{c["name"]}» con NRC {c["nrc"]}.\n'
            "En esta demo, el NRC también se añade al registro del estudiante."
        )

    def refresh_class_roster_table(self):
        if not hasattr(self, "class_roster_table"):
            return
        row = self.classes_table.currentRow() if hasattr(self, "classes_table") else self.current_class
        if row < 0 or row >= len(self.classes):
            row = self.current_class
        c = self.classes[row]
        self.selected_class_heading.setText(f'Estudiantes vinculados · {c["name"]} · NRC {c["nrc"]}')
        self.class_roster_table.setRowCount(len(c["students"]))
        for r, email in enumerate(c["students"]):
            profile = self.student_registry.get(email, {"name": "Desconocido", "email": email})
            self.class_roster_table.setItem(r, 0, QTableWidgetItem(profile["name"]))
            self.class_roster_table.setItem(r, 1, QTableWidgetItem(profile["email"]))

    def refresh_attendance_table(self, rows=None):
        if not hasattr(self, "attendance_table"):
            return
        shown = rows if rows is not None else self.students
        colors = {
            "Presente": ("#DDF7E8", "#18794E"),
            "Manual": ("#DDF7E8", "#18794E"),
            "Tarde": ("#FCE8E7", "#B42318"),
            "Sin registrar": ("#FCE8E7", "#B42318"),
            "Pendiente": ("#EDF0F5", "#596579"),
        }
        self.attendance_table.setRowCount(len(shown))
        for r, s in enumerate(shown):
            values = [s["name"], s["email"], s["time"], s["status"]]
            bg, fg = colors.get(s["status"], ("#EDF0F5", "#596579"))
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setBackground(QColor(bg))
                if col == 3:
                    item.setForeground(QColor(fg))
                    item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.attendance_table.setItem(r, col, item)

        present = sum(s["status"] in ("Presente", "Manual") for s in self.students)
        late = sum(s["status"] in ("Tarde", "Sin registrar") for s in self.students)
        pending = sum(s["status"] == "Pendiente" for s in self.students)
        self.metric_total.value_label.setText(str(len(self.students)))
        self.metric_present.value_label.setText(str(present))
        self.metric_late.value_label.setText(str(late))
        self.metric_pending.value_label.setText(str(pending))

    def filter_attendance(self, text):
        term = text.lower().strip()
        self.refresh_attendance_table([
            s for s in self.students
            if term in s["name"].lower() or term in s["email"].lower()
        ])

    def start_session(self):
        if self.session_active:
            return
        if not self.students:
            QMessageBox.warning(self, "Clase vacía", "No hay estudiantes vinculados a esta clase. Añádelos desde Gestión de clases.")
            return
        self.session_active = True
        c = self.classes[self.current_class]
        self.session_label.setText(f'● ASISTENCIA EN CURSO · NRC {c["nrc"]}')
        self.session_label.setStyleSheet("color:#18794E;font-weight:800;")
        self.start_btn.setText("●  Asistencia en curso")
        self.start_btn.setObjectName("Running")
        self.start_btn.setStyleSheet("background:#18794E;color:white;border:none;border-radius:8px;padding:10px 13px;font-weight:800;")
        self.start_btn.setEnabled(False)
        self.finish_btn.setEnabled(True)
        self.course_combo.setEnabled(False)
        self.tolerance.setEnabled(False)
        self.save_config_btn.setEnabled(False)
        self.device_status.setText("●  ESP32-CAM habilitado (simulado)")
        self.device_status.setStyleSheet("color:#8DE0B0;font-size:12px;font-weight:700;")
        QMessageBox.information(
            self, "Asistencia iniciada",
            "La sesión está en curso. El botón ahora indica el estado para evitar confusiones.\n"
            "La activación física del ESP32-CAM se conectará mediante FastAPI."
        )

    def finish_session(self):
        if not self.session_active:
            return
        answer = QMessageBox.question(
            self, "Finalizar clase", "¿Deseas finalizar la sesión de asistencia?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return
        self.session_active = False
        for s in self.students:
            if s["status"] == "Pendiente":
                s["status"] = "Sin registrar"
        self.session_label.setText("● Sesión finalizada")
        self.session_label.setStyleSheet("color:#B42318;font-weight:800;")
        self.device_status.setText("●  ESP32-CAM en espera")
        self.device_status.setStyleSheet("color:#F6D98B;font-size:12px;font-weight:700;")
        self.start_btn.setText("▶  Iniciar asistencia")
        self.start_btn.setObjectName("Success")
        self.start_btn.setStyleSheet("background:#DDF7E8;color:#18794E;border:none;border-radius:8px;padding:10px 13px;font-weight:700;")
        self.start_btn.setEnabled(True)
        self.finish_btn.setEnabled(False)
        self.course_combo.setEnabled(True)
        self.tolerance.setEnabled(True)
        self.save_config_btn.setEnabled(True)
        self.refresh_attendance_table()
        self.refresh_history_table()
        QMessageBox.information(self, "Clase finalizada", "La sesión se cerró en modo demostración. Puedes guardar o exportar la lista.")

    def manual_attendance(self):
        row = self.attendance_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selecciona un estudiante", "Selecciona una fila de la tabla antes de añadir asistencia.")
            return
        email_item = self.attendance_table.item(row, 1)
        email = email_item.text() if email_item else ""
        student = next((s for s in self.students if s["email"] == email), None)
        if not student:
            return
        if student["status"] in ("Presente", "Manual", "Tarde"):
            QMessageBox.information(self, "Ya tiene registro", "Este estudiante ya tiene un registro en la sesión.")
            return
        now = datetime.now().strftime("%H:%M")
        student["time"] = now
        student["status"] = "Manual"
        self.refresh_attendance_table()
        QMessageBox.information(self, "Asistencia manual", f'Se añadió asistencia manual para {student["name"]} a las {now}.')

    def export_attendance(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar asistencia", "asistencia.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            c = self.classes[self.current_class]
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["NRC", "Asignatura", "Nombre", "Correo institucional", "Hora de registro", "Estado", "Origen"])
                for s in self.students:
                    origin = "Manual" if s["status"] == "Manual" else "Automático (demostración)"
                    writer.writerow([c["nrc"], c["name"], s["name"], s["email"], s["time"], s["status"], origin])
            QMessageBox.information(
                self, "Exportación completada",
                f"Se guardó el CSV en:\n{path}\n\nLa escritura en MySQL se añadirá al conectar FastAPI."
            )
        except OSError as e:
            QMessageBox.critical(self, "Error al exportar", str(e))

    def refresh_history_table(self):
        if not hasattr(self, "history_table"):
            return
        c = self.classes[self.current_class]
        registered = sum(s["status"] in ("Presente", "Manual", "Tarde") for s in self.students)
        self.history_table.setRowCount(1)
        values = [f'{c["nrc"]} · {c["name"]}', datetime.now().strftime("%d/%m/%Y"), str(registered), "Demostración"]
        for col, val in enumerate(values):
            self.history_table.setItem(0, col, QTableWidgetItem(val))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = AttendanceApp()
    window.show()
    sys.exit(app.exec())
