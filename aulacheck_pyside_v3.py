import sys
import csv
from datetime import datetime
import requests

from PySide6.QtCore import Qt, QTime
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QComboBox, QSpinBox, QTimeEdit, QMessageBox, QAbstractItemView,
    QFileDialog, QStackedWidget
)

API_BASE = "http://127.0.0.1:8000"


class ApiError(Exception):
    pass


class AulaCheckApp(QMainWindow):
    """Interfaz PySide6 conectada al backend FastAPI de AulaCheck."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AulaCheck | Sistema de asistencia académica")
        self.resize(1360, 860)
        self.setMinimumSize(1120, 720)

        self.classes = []
        self.current_class_index = 0
        self.current_session_id = None
        self.session_active = False
        self.roster = []
        self.records = []

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
                padding:10px 13px; font-weight:800; }
            QLineEdit, QComboBox, QSpinBox, QTimeEdit {
                background:white; border:1px solid #D8DFEA; border-radius:7px; padding:8px; min-height:18px;
            }
            QTableWidget { background:white; border:1px solid #D9E0EA; gridline-color:#C9D2E0;
                selection-background-color:#E8EEFF; selection-color:#172033; }
            QHeaderView::section { background:#F7F9FC; color:#53627A; border:1px solid #C9D2E0;
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
        for text, index in [
            ("▦   Panel de asistencia", 0),
            ("▣   Gestión de clases", 1),
            ("◷   Historial", 2),
            ("ⓘ   Acerca de", 3),
        ]:
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
        self.device_status = QLabel("●  ESP32-CAM no conectada")
        self.device_status.setStyleSheet("color:#F6D98B;font-size:12px;font-weight:700;")
        d2 = QLabel("Backend conectado por HTTP")
        d2.setStyleSheet("color:#D8E1EF;font-size:11px;")
        dv.addWidget(d1)
        dv.addWidget(self.device_status)
        dv.addWidget(d2)
        side.addWidget(device)

        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.build_dashboard())
        self.stack.addWidget(self.build_classes_page())
        self.stack.addWidget(self.build_history_page())
        self.stack.addWidget(self.build_about_page())
        main_layout.addWidget(self.stack)
        root_layout.addWidget(sidebar)
        root_layout.addWidget(main_area, 1)
        self.setCentralWidget(root)

        self.load_classes(show_errors=False)
        self.refresh_history()

    # ---------- API helpers ----------
    def api(self, method, path, **kwargs):
        try:
            response = requests.request(method, f"{API_BASE}{path}", timeout=5, **kwargs)
        except requests.RequestException as exc:
            raise ApiError(
                "No se pudo conectar con FastAPI.\n"
                "Comprueba que el backend esté ejecutándose en http://127.0.0.1:8000.\n\n"
                f"Detalle: {exc}"
            )
        if not response.ok:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ApiError(f"Error HTTP {response.status_code}: {detail}")
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def run_action(self, action, success_message=None):
        try:
            result = action()
            if success_message:
                QMessageBox.information(self, "AulaCheck", success_message)
            return result
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo completar la operación", str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            QMessageBox.critical(self, "Error inesperado", str(exc))
        return None

    def current_class(self):
        if not self.classes:
            return None
        self.current_class_index = max(0, min(self.current_class_index, len(self.classes) - 1))
        return self.classes[self.current_class_index]

    def current_nrc(self):
        c = self.current_class()
        return c["nrc"] if c else None

    # ---------- UI helpers ----------
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
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setWordWrap(False)

    # ---------- Pages ----------
    def build_dashboard(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(self.page_header("Panel de asistencia", "Sesiones reales guardadas en MySQL mediante FastAPI."))

        config = self.panel()
        cg = QGridLayout(config)
        cg.setContentsMargins(16, 13, 16, 13)
        cg.setSpacing(10)
        cg.addWidget(self.section_label("INFORMACIÓN DE LA CLASE"), 0, 0, 1, 5)
        self.course_combo = QComboBox()
        self.course_combo.currentIndexChanged.connect(self.on_dashboard_class_changed)
        self.start_time_label = QLabel("—")
        self.start_time_label.setStyleSheet("font-size:14px;font-weight:700;color:#344054;padding:7px;")
        self.tolerance = QSpinBox()
        self.tolerance.setRange(0, 180)
        self.tolerance.setSuffix(" min")
        cg.addWidget(QLabel("Asignatura / NRC"), 1, 0)
        cg.addWidget(self.course_combo, 2, 0, 1, 2)
        cg.addWidget(QLabel("Hora de inicio (solo lectura)"), 1, 2)
        cg.addWidget(self.start_time_label, 2, 2)
        cg.addWidget(QLabel("Tolerancia ajustable"), 1, 3)
        cg.addWidget(self.tolerance, 2, 3)
        self.save_config_btn = QPushButton("Guardar tolerancia")
        self.save_config_btn.setObjectName("Secondary")
        self.save_config_btn.clicked.connect(self.save_tolerance)
        cg.addWidget(self.save_config_btn, 2, 4)
        layout.addWidget(config)

        cards = QHBoxLayout()
        self.metric_total = self.metric_card("Estudiantes de la clase", 0)
        self.metric_present = self.metric_card("Asistencia válida", 0)
        self.metric_late = self.metric_card("Tarde / ausente", 0)
        self.metric_pending = self.metric_card("Pendientes", 0)
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
        self.search_attendance.textChanged.connect(self.render_attendance_table)
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
        self.refresh_btn = QPushButton("↻ Actualizar")
        self.refresh_btn.setObjectName("Secondary")
        self.refresh_btn.clicked.connect(self.refresh_dashboard_data)
        for b in [self.start_btn, self.finish_btn, self.manual_btn, self.export_btn, self.refresh_btn]:
            actions.addWidget(b)
        tp.addLayout(actions)
        layout.addWidget(table_panel, 1)
        return page

    def build_classes_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(self.page_header("Gestión de clases", "Crea clases en MySQL y vincula estudiantes existentes por correo institucional."))

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
        create_btn = QPushButton("Crear clase y generar NRC")
        create_btn.setObjectName("Primary")
        create_btn.clicked.connect(self.create_class)
        grid.addWidget(create_btn, 2, 4)
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
        self.classes_table.itemSelectionChanged.connect(self.refresh_roster_for_selected_class)
        cl.addWidget(self.classes_table)
        layout.addWidget(classes_panel, 1)

        roster_panel = self.panel()
        rl = QVBoxLayout(roster_panel)
        rl.setContentsMargins(16, 14, 16, 14)
        self.roster_heading = QLabel("Estudiantes vinculados a la clase seleccionada")
        self.roster_heading.setStyleSheet("font-size:15px;font-weight:800;color:#17365D;")
        rl.addWidget(self.roster_heading)
        note = QLabel("Solo se vinculan correos que ya existan en la tabla estudiantes de MySQL.")
        note.setObjectName("Muted")
        rl.addWidget(note)
        addrow = QHBoxLayout()
        self.student_email_input = QLineEdit()
        self.student_email_input.setPlaceholderText("nombre.apellido@utb.edu.co")
        self.student_email_input.returnPressed.connect(self.enroll_student)
        self.add_student_btn = QPushButton("＋ Añadir por correo")
        self.add_student_btn.setObjectName("Secondary")
        self.add_student_btn.clicked.connect(self.enroll_student)
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
        layout.addLayout(self.page_header("Historial de asistencia", "Sesiones consultadas directamente desde FastAPI y MySQL."))
        panel = self.panel()
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(16, 16, 16, 16)
        pl.addWidget(self.section_label("SESIONES REGISTRADAS"))
        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(["ID sesión", "NRC", "Inicio", "Finalización", "Estado"])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.setup_table(self.history_table)
        pl.addWidget(self.history_table)
        refresh = QPushButton("↻ Actualizar historial")
        refresh.setObjectName("Secondary")
        refresh.clicked.connect(self.refresh_history)
        pl.addWidget(refresh, alignment=Qt.AlignRight)
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
        pl.addWidget(self.section_label("INTEGRANTES"))
        for name in ["Fredy Jarava Chavez", "Jerry Buelvas Mejia", "Juan Caicedo Gomez", "Rafael Villero Castillo"]:
            pl.addWidget(QLabel("•  " + name))
        pl.addStretch()
        layout.addWidget(panel, 1)
        return page

    # ---------- Data loading ----------
    def load_classes(self, show_errors=True):
        try:
            self.classes = self.api("GET", "/classes")
        except ApiError as exc:
            if show_errors:
                QMessageBox.warning(self, "Error al cargar clases", str(exc))
            self.classes = []
        if self.current_class_index >= len(self.classes):
            self.current_class_index = max(0, len(self.classes) - 1)
        self.populate_class_selectors()
        self.populate_classes_table()
        if self.classes:
            self.load_dashboard_class()
            self.refresh_roster_for_selected_class()
        else:
            self.roster = []
            self.records = []
            self.render_attendance_table()
            self.class_roster_table.setRowCount(0)
            self.start_time_label.setText("—")
            self.session_label.setText("● Crea o selecciona una clase")
        self.refresh_history()

    def populate_class_selectors(self):
        self.course_combo.blockSignals(True)
        self.course_combo.clear()
        for c in self.classes:
            self.course_combo.addItem(f'{c["name"]} · NRC {c["nrc"]}')
        if self.classes:
            self.course_combo.setCurrentIndex(self.current_class_index)
        self.course_combo.blockSignals(False)

    def populate_classes_table(self):
        self.classes_table.blockSignals(True)
        self.classes_table.setRowCount(len(self.classes))
        for r, c in enumerate(self.classes):
            values = [c["nrc"], c["name"], str(c["start_time"])[:5], f'{c["tolerance_minutes"]} min', str(c["student_count"])]
            for col, value in enumerate(values):
                self.classes_table.setItem(r, col, QTableWidgetItem(value))
        if self.classes:
            self.classes_table.selectRow(self.current_class_index)
        self.classes_table.blockSignals(False)

    def load_dashboard_class(self):
        c = self.current_class()
        if not c:
            return
        self.start_time_label.setText(str(c["start_time"])[:5])
        self.tolerance.setValue(int(c["tolerance_minutes"]))
        self.load_roster_and_records()

    def load_roster_and_records(self):
        c = self.current_class()
        if not c:
            self.roster, self.records = [], []
            self.render_attendance_table()
            return
        try:
            self.roster = self.api("GET", f'/classes/{c["nrc"]}/students')
            self.records = []
            if self.current_session_id is not None:
                self.records = self.api("GET", f"/sessions/{self.current_session_id}/attendance")
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudieron cargar los datos", str(exc))
            self.roster, self.records = [], []
        self.render_attendance_table()

    def refresh_dashboard_data(self):
        self.load_classes()
        if self.current_session_id is not None:
            self.load_roster_and_records()

    def navigate(self, index):
        if self.session_active and index == 1:
            QMessageBox.information(self, "Sesión activa", "Finaliza la sesión antes de gestionar las clases.")
            return
        self.stack.setCurrentIndex(index)
        for i, b in enumerate(self.nav_buttons):
            b.setChecked(i == index)
        if index == 0:
            self.load_classes()
        elif index == 1:
            self.load_classes()
        elif index == 2:
            self.refresh_history()

    def on_dashboard_class_changed(self, index):
        if index < 0 or index >= len(self.classes):
            return
        if self.session_active:
            QMessageBox.warning(self, "Sesión activa", "Finaliza la sesión antes de cambiar de clase.")
            self.course_combo.blockSignals(True)
            self.course_combo.setCurrentIndex(self.current_class_index)
            self.course_combo.blockSignals(False)
            return
        self.current_class_index = index
        self.current_session_id = None
        self.session_label.setText("● Sesión no iniciada")
        self.session_label.setStyleSheet("color:#6B778C;font-weight:700;")
        self.start_btn.setText("▶  Iniciar asistencia")
        self.start_btn.setObjectName("Success")
        self.start_btn.setStyleSheet("")
        self.start_btn.setEnabled(True)
        self.finish_btn.setEnabled(False)
        self.load_dashboard_class()
        self.populate_classes_table()
        self.refresh_roster_for_selected_class()

    def selected_class_table_index(self):
        row = self.classes_table.currentRow()
        if row < 0 or row >= len(self.classes):
            return None
        return row

    def refresh_roster_for_selected_class(self):
        if not hasattr(self, "classes_table"):
            return
        row = self.selected_class_table_index()
        if row is None:
            self.class_roster_table.setRowCount(0)
            return
        c = self.classes[row]
        self.roster_heading.setText(f'Estudiantes vinculados · {c["name"]} · NRC {c["nrc"]}')
        try:
            students = self.api("GET", f'/classes/{c["nrc"]}/students')
        except ApiError as exc:
            QMessageBox.warning(self, "Error al consultar estudiantes", str(exc))
            return
        self.class_roster_table.setRowCount(len(students))
        for r, student in enumerate(students):
            self.class_roster_table.setItem(r, 0, QTableWidgetItem(student["full_name"]))
            self.class_roster_table.setItem(r, 1, QTableWidgetItem(student["email"]))
        self.populate_classes_table_counts(students, row)

    def populate_classes_table_counts(self, students, row):
        # El endpoint /classes ya trae student_count; refrescar por coherencia tras altas.
        try:
            self.classes = self.api("GET", "/classes")
            self.populate_class_selectors()
            self.classes_table.blockSignals(True)
            self.classes_table.setRowCount(len(self.classes))
            for r, c in enumerate(self.classes):
                values = [c["nrc"], c["name"], str(c["start_time"])[:5], f'{c["tolerance_minutes"]} min', str(c["student_count"])]
                for col, value in enumerate(values):
                    self.classes_table.setItem(r, col, QTableWidgetItem(value))
            self.classes_table.selectRow(min(row, len(self.classes)-1) if self.classes else -1)
            self.classes_table.blockSignals(False)
        except ApiError:
            pass

    # ---------- Actions ----------
    def create_class(self):
        name = self.new_class_name.text().strip()
        if len(name) < 2:
            QMessageBox.warning(self, "Nombre inválido", "Escribe un nombre para la clase.")
            return
        payload = {
            "name": name,
            "start_time": self.new_class_start.time().toString("HH:mm:ss"),
            "tolerance_minutes": self.new_class_tolerance.value(),
        }
        try:
            created = self.api("POST", "/classes", json=payload)
            self.new_class_name.clear()
            self.load_classes()
            # Select the class that was just created.
            for i, c in enumerate(self.classes):
                if c["nrc"] == created["nrc"]:
                    self.current_class_index = i
                    break
            self.populate_class_selectors()
            self.load_dashboard_class()
            self.populate_classes_table()
            QMessageBox.information(
                self, "Clase creada",
                f'La clase «{created["name"]}» se guardó en MySQL con NRC {created["nrc"]}.\n'
                "Ahora puedes vincular estudiantes por correo institucional."
            )
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo crear la clase", str(exc))

    def enroll_student(self):
        row = self.selected_class_table_index()
        if row is None:
            QMessageBox.warning(self, "Selecciona una clase", "Selecciona una clase en la tabla antes de añadir estudiantes.")
            return
        c = self.classes[row]
        email = self.student_email_input.text().strip().lower()
        if not email:
            QMessageBox.warning(self, "Correo requerido", "Escribe el correo institucional del estudiante.")
            return
        try:
            result = self.api("POST", f'/classes/{c["nrc"]}/students', json={"email": email})
            self.student_email_input.clear()
            self.load_classes()
            QMessageBox.information(self, "Estudiante añadido", f'{result["student"]} fue vinculado a la clase NRC {c["nrc"]}.')
            # Keep the selected class in both screens.
            for i, item in enumerate(self.classes):
                if item["nrc"] == c["nrc"]:
                    self.current_class_index = i
                    break
            self.populate_class_selectors()
            self.populate_classes_table()
            self.refresh_roster_for_selected_class()
            self.load_dashboard_class()
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo añadir el estudiante", str(exc))

    def save_tolerance(self):
        c = self.current_class()
        if not c:
            QMessageBox.warning(self, "Sin clase", "Primero crea o selecciona una clase.")
            return
        try:
            updated = self.api(
                "PATCH",
                f'/classes/{c["nrc"]}/tolerance',
                params={"tolerance_minutes": self.tolerance.value()},
            )
            self.load_classes()
            QMessageBox.information(
                self, "Tolerancia guardada",
                f'La tolerancia de «{updated["name"]}» (NRC {updated["nrc"]}) ahora es '
                f'{updated["tolerance_minutes"]} minutos.'
            )
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo guardar la tolerancia", str(exc))

    def start_session(self):
        if self.session_active:
            return
        c = self.current_class()
        if not c:
            QMessageBox.warning(self, "Sin clase", "Primero crea o selecciona una clase.")
            return
        try:
            self.roster = self.api("GET", f'/classes/{c["nrc"]}/students')
            if not self.roster:
                QMessageBox.warning(self, "Clase vacía", "Añade estudiantes desde Gestión de clases antes de iniciar.")
                return
            session = self.api("POST", f'/classes/{c["nrc"]}/sessions/start')
            self.current_session_id = session["id"]
            self.session_active = True
            self.session_label.setText(f'● ASISTENCIA EN CURSO · SESIÓN {session["id"]} · NRC {c["nrc"]}')
            self.session_label.setStyleSheet("color:#18794E;font-weight:800;")
            self.start_btn.setText("●  Asistencia en curso")
            self.start_btn.setObjectName("Running")
            self.start_btn.setStyleSheet("background:#18794E;color:white;border:none;border-radius:8px;padding:10px 13px;font-weight:800;")
            self.start_btn.setEnabled(False)
            self.finish_btn.setEnabled(True)
            self.course_combo.setEnabled(False)
            self.tolerance.setEnabled(False)
            self.save_config_btn.setEnabled(False)
            self.device_status.setText("●  Backend activo · ESP32-CAM pendiente")
            self.device_status.setStyleSheet("color:#8DE0B0;font-size:12px;font-weight:700;")
            self.load_roster_and_records()
            self.refresh_history()
            QMessageBox.information(
                self, "Asistencia iniciada",
                f'Se creó la sesión {session["id"]} en MySQL para la clase NRC {c["nrc"]}.\n'
                "La conexión física con el ESP32-CAM todavía no está implementada."
            )
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo iniciar asistencia", str(exc))

    def finish_session(self):
        if not self.session_active or self.current_session_id is None:
            return
        answer = QMessageBox.question(
            self, "Finalizar clase", "¿Deseas finalizar la sesión y marcar ausentes a quienes no registraron?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return
        try:
            finished = self.api("POST", f"/sessions/{self.current_session_id}/finish")
            self.session_active = False
            self.session_label.setText(f'● Sesión finalizada · ID {finished["id"]}')
            self.session_label.setStyleSheet("color:#B42318;font-weight:800;")
            self.device_status.setText("●  Sesión cerrada · ESP32-CAM pendiente")
            self.device_status.setStyleSheet("color:#F6D98B;font-size:12px;font-weight:700;")
            self.start_btn.setText("▶  Iniciar asistencia")
            self.start_btn.setObjectName("Success")
            self.start_btn.setStyleSheet("")
            self.start_btn.setEnabled(True)
            self.finish_btn.setEnabled(False)
            self.course_combo.setEnabled(True)
            self.tolerance.setEnabled(True)
            self.save_config_btn.setEnabled(True)
            self.load_roster_and_records()
            self.refresh_history()
            QMessageBox.information(
                self, "Clase finalizada",
                "La sesión se cerró en MySQL. Los estudiantes sin registro quedaron marcados como ausentes."
            )
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo finalizar la clase", str(exc))

    def manual_attendance(self):
        if self.current_session_id is None or not self.session_active:
            QMessageBox.warning(self, "No hay sesión activa", "Primero pulsa «Iniciar asistencia».")
            return
        row = self.attendance_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selecciona un estudiante", "Selecciona un estudiante de la tabla.")
            return
        email_item = self.attendance_table.item(row, 1)
        email = email_item.text() if email_item else ""
        try:
            result = self.api(
                "POST",
                f"/sessions/{self.current_session_id}/attendance/manual",
                json={"email": email},
            )
            self.load_roster_and_records()
            QMessageBox.information(
                self, "Asistencia añadida",
                f'{result["student_name"]} quedó registrado manualmente en MySQL.'
            )
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo añadir la asistencia", str(exc))

    def render_attendance_table(self, *_):
        if not hasattr(self, "attendance_table"):
            return
        record_by_email = {r["student_email"].lower(): r for r in self.records}
        rows = []
        for student in self.roster:
            email = student["email"]
            record = record_by_email.get(email.lower())
            if record:
                status_map = {
                    "present": "Presente",
                    "manual": "Manual",
                    "tardy": "Tarde",
                    "absent": "Ausente",
                }
                state = status_map.get(record["status"], record["status"])
                time_value = record["registered_at"]
                if time_value:
                    time_value = time_value.replace("T", " ")[:16]
                    time_value = time_value[-5:]
                else:
                    time_value = "—"
            else:
                state = "Pendiente"
                time_value = "—"
            rows.append({
                "name": student["full_name"],
                "email": email,
                "time": time_value,
                "status": state,
            })

        term = self.search_attendance.text().lower().strip() if hasattr(self, "search_attendance") else ""
        shown = [r for r in rows if term in r["name"].lower() or term in r["email"].lower()]
        colors = {
            "Presente": ("#DDF7E8", "#18794E"),
            "Manual": ("#DDF7E8", "#18794E"),
            "Tarde": ("#FCE8E7", "#B42318"),
            "Ausente": ("#FCE8E7", "#B42318"),
            "Pendiente": ("#EDF0F5", "#596579"),
        }
        self.attendance_table.setRowCount(len(shown))
        for r, student in enumerate(shown):
            bg, fg = colors.get(student["status"], ("#EDF0F5", "#596579"))
            for col, value in enumerate([student["name"], student["email"], student["time"], student["status"]]):
                item = QTableWidgetItem(value)
                item.setBackground(QColor(bg))
                if col == 3:
                    item.setForeground(QColor(fg))
                    item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.attendance_table.setItem(r, col, item)

        present = sum(r["status"] in ("Presente", "Manual") for r in rows)
        late_absent = sum(r["status"] in ("Tarde", "Ausente") for r in rows)
        pending = sum(r["status"] == "Pendiente" for r in rows)
        self.metric_total.value_label.setText(str(len(rows)))
        self.metric_present.value_label.setText(str(present))
        self.metric_late.value_label.setText(str(late_absent))
        self.metric_pending.value_label.setText(str(pending))

    def refresh_history(self):
        if not hasattr(self, "history_table"):
            return
        try:
            sessions = self.api("GET", "/sessions")
        except ApiError as exc:
            # At construction time don't spam a dialog if server hasn't started.
            if self.isVisible():
                QMessageBox.warning(self, "No se pudo cargar historial", str(exc))
            return
        self.history_table.setRowCount(len(sessions))
        for r, session in enumerate(sessions):
            values = [
                str(session["id"]),
                session["nrc"],
                str(session["started_at"]).replace("T", " ")[:19],
                str(session["finished_at"]).replace("T", " ")[:19] if session["finished_at"] else "—",
                "Activa" if session["status"] == "active" else "Finalizada",
            ]
            for col, value in enumerate(values):
                self.history_table.setItem(r, col, QTableWidgetItem(value))

    def export_attendance(self):
        if not self.roster:
            QMessageBox.information(self, "Sin estudiantes", "No hay estudiantes para exportar en esta clase.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar asistencia", "asistencia.csv", "CSV (*.csv)")
        if not path:
            return
        record_by_email = {r["student_email"].lower(): r for r in self.records}
        c = self.current_class()
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["NRC", "Asignatura", "Nombre", "Correo institucional", "Hora de registro", "Estado", "Origen"])
                status_map = {"present": "Presente", "manual": "Manual", "tardy": "Tarde", "absent": "Ausente"}
                for student in self.roster:
                    record = record_by_email.get(student["email"].lower())
                    if record:
                        registered = record["registered_at"] or "—"
                        state = status_map.get(record["status"], record["status"])
                        source = record["source"]
                    else:
                        registered, state, source = "—", "Pendiente", "—"
                    writer.writerow([c["nrc"], c["name"], student["full_name"], student["email"], registered, state, source])
            QMessageBox.information(self, "Exportación completada", f"Se guardó el CSV en:\n{path}")
        except OSError as exc:
            QMessageBox.critical(self, "Error al exportar", str(exc))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = AulaCheckApp()
    window.show()
    sys.exit(app.exec())
